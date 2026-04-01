import os
import json
import logging
import time
from decimal import Decimal, InvalidOperation
from logging.handlers import RotatingFileHandler

import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from email_validator import validate_email as EmailValidator, EmailNotValidError

# Load environment variables from config/config.txt
# Secrets (AUTHORIZE_API_LOGIN_ID, AUTHORIZE_TRANSACTION_KEY) passed via Docker -e
load_dotenv(dotenv_path="config/config.txt", override=False)

# Environment variables (must be defined before Flask app)
AUTHORIZE_API_URL = "https://apitest.authorize.net/xml/v1/request.api"
AUTHORIZE_HOSTED_FORM_URL = "https://test.authorize.net/payment/payment"

API_LOGIN_ID = os.getenv("AUTHORIZE_API_LOGIN_ID", "").strip()
TRANSACTION_KEY = os.getenv("AUTHORIZE_TRANSACTION_KEY", "").strip()
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5001").rstrip("/")
BUILD_VERSION = os.getenv("BUILD_VERSION", "dev")

# CORS configuration
# Note: 'null' origin allows opening index.html directly from file:// (local files)
# This is a security consideration - null origin bypasses same-origin policy
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
if not ALLOWED_ORIGINS or ALLOWED_ORIGINS == [""]:
    ALLOWED_ORIGINS = ["http://localhost:5001", "http://127.0.0.1:5001", "null"]  # dev fallback

app = Flask(__name__, static_folder="static")
CORS(app, resources={
    r"/create-payment": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["POST"],
        "allow_headers": ["Content-Type"],
        "max_age": 3600
    },
    r"/*": {
        "origins": ALLOWED_ORIGINS
    }
})

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Bot detection patterns
BOT_PATTERNS = [
    "bot", "crawl", "spider", "scraper", "curl", "python-requests",
    "wget", "requests", "httpie", "postman", "insomnia", "httpclient"
]


def is_bot(user_agent: str) -> bool:
    """Check if User-Agent matches known bot patterns."""
    if not user_agent:
        return True  # No UA = suspicious
    ua_lower = user_agent.lower()
    return any(pattern in ua_lower for pattern in BOT_PATTERNS)


def setup_logging():
    """Configure logging for access and security events."""
    log_dir = os.getenv("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Access logger
    access_handler = RotatingFileHandler(
        f"{log_dir}/access.log",
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    access_logger = logging.getLogger("access")
    access_logger.addHandler(access_handler)
    access_logger.setLevel(logging.INFO)

    # Security logger
    security_handler = RotatingFileHandler(
        f"{log_dir}/security.log",
        maxBytes=10485760,
        backupCount=10
    )
    security_logger = logging.getLogger("security")
    security_logger.addHandler(security_handler)
    security_logger.setLevel(logging.INFO)

    # Console logging for Docker (always enabled for production)
    import sys
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    return access_logger, security_logger


access_logger, security_logger = setup_logging()


def json_setting(name: str, value: dict) -> dict:
    return {
        "settingName": name,
        "settingValue": json.dumps(value)
    }


def validate_amount(value) -> str:
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError, TypeError):
        raise ValueError("Invalid amount")

    if amount <= 0:
        raise ValueError("Amount must be greater than zero")

    return f"{amount:.2f}"


def validate_email(value: str) -> str:
    email = str(value or "").strip()
    if not email:
        raise ValueError("Email is required")

    try:
        valid = EmailValidator(email, check_deliverability=False)
        return valid.email
    except EmailNotValidError:
        raise ValueError("Invalid email format")


def validate_reference(value: str) -> str:
    reference = str(value or "").strip()

    if not reference:
        raise ValueError("Reference required")

    if len(reference) > 20:
        raise ValueError("Reference too long (max 20 characters)")

    import re
    if not re.match(r'^[a-zA-Z0-9\s\-_\.]+$', reference):
        raise ValueError("Reference contains invalid characters")

    return reference


def parse_gateway_json(response: requests.Response) -> dict:
    raw = response.text.lstrip("\ufeff").strip()
    return json.loads(raw)


@app.before_request
def log_request():
    """Log incoming requests (skip health checks)."""
    if request.path == "/health":
        return
    access_logger.info(
        f"request: method={request.method} path={request.path} ip={request.remote_addr}"
    )


@app.after_request
def log_response(response):
    """Log responses (skip health checks)."""
    if request.path != "/health":
        access_logger.info(
            f"response: status={response.status_code} path={request.path}"
        )
    return response


@app.after_request
def set_security_headers(response):
    """Set security headers for production (always enabled)."""
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


@app.after_request
def handle_null_origin_cors(response):
    """
    Handle CORS for 'null' origin (local file:// access).

    Security consideration: Allowing 'null' origin permits opening index.html
    directly from the file system, bypassing normal same-origin policy.
    This is convenient for local testing but has security implications.
    """
    origin = request.headers.get("Origin")

    # Handle 'null' origin for local file access
    if origin == "null":
        response.headers["Access-Control-Allow-Origin"] = "null"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Max-Age"] = "3600"
        response.headers["Vary"] = "Origin"

    return response


@app.route("/health", methods=["GET"])
@limiter.exempt
def health_check():
    """Health check endpoint for monitoring and Docker."""
    if not API_LOGIN_ID or not TRANSACTION_KEY:
        return jsonify({"status": "down"}), 503
    return jsonify({"status": f"healthy [{BUILD_VERSION}]"}), 200


@app.route("/", methods=["GET"])
def index():
    return send_from_directory("static", "index.html")


@app.route("/create-payment", methods=["POST"])
@limiter.limit("10 per minute")
@limiter.limit("30 per hour")
def create_payment():
    if not API_LOGIN_ID or not TRANSACTION_KEY:
        return jsonify({"error": "Authorize.net credentials are missing"}), 500

    # Bot detection via User-Agent
    user_agent = request.headers.get("User-Agent", "")
    if is_bot(user_agent):
        security_logger.warning(f"bot_blocked: ip={request.remote_addr} ua={user_agent[:50]}")
        return jsonify({"error": "Bots not allowed"}), 403

    data = request.get_json(silent=True) or {}

    # Honeypot check - bots fill hidden fields
    if data.get("website"):
        security_logger.warning(f"honeypot_triggered: ip={request.remote_addr}")
        return jsonify({"error": "Suspicious request"}), 403

    try:
        reference = validate_reference(data.get("reference"))
        amount = validate_amount(data.get("amount"))
        email = validate_email(data.get("email"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    payload = {
        "getHostedPaymentPageRequest": {
            "merchantAuthentication": {
                "name": API_LOGIN_ID,
                "transactionKey": TRANSACTION_KEY
            },
            "transactionRequest": {
                "transactionType": "authCaptureTransaction",
                "amount": amount,
                "order": {
                    "invoiceNumber": reference[:20],
                    "description": f"Ref: {reference}"[:255]
                },
                "customer": {
                    "email": email
                }
            },
            "hostedPaymentSettings": {
                "setting": [
                    json_setting("hostedPaymentReturnOptions", {
                        "showReceipt": True,
                        "url": f"{APP_BASE_URL}/return",
                        "urlText": "Continue",
                        "cancelUrl": f"{APP_BASE_URL}/",
                        "cancelUrlText": "Cancel"
                    }),
                    json_setting("hostedPaymentOrderOptions", {
                        "show": True,
                        "merchantName": "POND mobile"
                    }),
                    json_setting("hostedPaymentButtonOptions", {
                        "text": "Pay"
                    }),
                    json_setting("hostedPaymentPaymentOptions", {
                        "cardCodeRequired": True,
                        "showCreditCard": True,
                        "showBankAccount": False
                    }),
                    json_setting("hostedPaymentCustomerOptions", {
                        "showEmail": False,
                        "requiredEmail": False
                    })
                ]
            }
        }
    }

    # Log payment initiation
    security_logger.info(
        f"payment_initiated: reference={reference[:10]}... amount={amount} ip={request.remote_addr}"
    )

    try:
        response = requests.post(
            AUTHORIZE_API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=(5, 25)
        )
    except requests.RequestException as e:
        security_logger.error(f"gateway_request_failed: reference={reference[:10]}... error={str(e)}")
        return jsonify({"error": "Gateway request failed"}), 502

    try:
        gateway_result = parse_gateway_json(response)
    except Exception as e:
        security_logger.error(f"gateway_parse_failed: reference={reference[:10]}... error={str(e)}")
        return jsonify({"error": "Failed to parse gateway response"}), 502

    messages = gateway_result.get("messages", {})
    result_code = messages.get("resultCode")

    if result_code != "Ok":
        security_logger.warning(
            f"gateway_error: reference={reference[:10]}... code={result_code}"
        )
        return jsonify({"error": "Authorize.net returned an error"}), 502

    token = gateway_result.get("token")
    if not token:
        security_logger.error(f"no_token_returned: reference={reference[:10]}...")
        return jsonify({"error": "No token returned by Authorize.net"}), 502

    security_logger.info(f"payment_token_created: reference={reference[:10]}...")

    return jsonify({
        "token": token,
        "url": AUTHORIZE_HOSTED_FORM_URL
    }), 200


@app.route("/return", methods=["GET"])
def payment_return():
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Thank You - POND Mobile</title>
  <meta http-equiv="refresh" content="5;url=https://www.pondmobile.com/">
  <style>
    body {
      font-family: Arial, sans-serif;
      text-align: center;
      margin: 0;
      background: linear-gradient(135deg, #c68157 0%, #6b87b7 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 32px 18px;
    }
    .box {
      background: white;
      padding: 40px;
      border-radius: 16px;
      box-shadow: 0 10px 30px rgba(0,0,0,.1);
      max-width: 500px;
    }
    h1 { color: #4a4a4a; margin: 0 0 16px; font-size: 32px; }
    p { color: #666; margin: 0 0 24px; font-size: 18px; }
    .timer { color: #6b87b7; font-weight: bold; }
  </style>
</head>
<body>
  <div class="box">
    <h1>Thank you for using Pond Mobile!</h1>
    <p>You will be redirected to <strong>pondmobile.com</strong> in <span class="timer">5 seconds</span>.</p>
  </div>
  <script>
    let seconds = 5;
    const timer = document.querySelector('.timer');
    setInterval(() => {
      seconds--;
      if (seconds > 0) timer.textContent = seconds + ' seconds';
    }, 1000);
  </script>
</body>
</html>
"""
