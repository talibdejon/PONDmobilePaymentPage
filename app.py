import os
import json
from decimal import Decimal, InvalidOperation

import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

load_dotenv()

app = Flask(__name__, static_folder="static")
CORS(app)

AUTHORIZE_API_URL = "https://api.authorize.net/xml/v1/request.api"
AUTHORIZE_HOSTED_FORM_URL = "https://accept.authorize.net/payment/payment"

API_LOGIN_ID = os.getenv("AUTHORIZE_API_LOGIN_ID", "").strip()
TRANSACTION_KEY = os.getenv("AUTHORIZE_TRANSACTION_KEY", "").strip()
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5001").rstrip("/")


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
    if "@" not in email or "." not in email:
        raise ValueError("Invalid email")
    return email


def parse_gateway_json(response: requests.Response) -> dict:
    raw = response.text.lstrip("\ufeff").strip()
    return json.loads(raw)


@app.route("/", methods=["GET"])
def index():
    return send_from_directory("static", "index.html")


@app.route("/create-payment", methods=["POST"])
def create_payment():
    if not API_LOGIN_ID or not TRANSACTION_KEY:
        return jsonify({"error": "Authorize.net credentials are missing"}), 500

    data = request.get_json(silent=True) or {}

    reference = str(data.get("reference", "")).strip()
    amount_raw = data.get("amount")
    email_raw = data.get("email")

    if not reference:
        return jsonify({"error": "Reference required"}), 400

    try:
        amount = validate_amount(amount_raw)
        email = validate_email(email_raw)
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

    try:
        response = requests.post(
            AUTHORIZE_API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
    except requests.RequestException:
        return jsonify({"error": "Gateway request failed"}), 502

    try:
        gateway_result = parse_gateway_json(response)
    except Exception:
        return jsonify({"error": "Failed to parse gateway response"}), 502

    messages = gateway_result.get("messages", {})
    result_code = messages.get("resultCode")

    if result_code != "Ok":
        return jsonify({"error": "Authorize.net returned an error"}), 502

    token = gateway_result.get("token")
    if not token:
        return jsonify({"error": "No token returned by Authorize.net"}), 502

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
  <title>Payment Completed</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      text-align: center;
      margin: 0;
      background: #f5f5f5;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .box {
      background: white;
      width: 520px;
      max-width: calc(100% - 40px);
      padding: 40px;
      border-radius: 16px;
      box-shadow: 0 10px 30px rgba(0,0,0,.08);
    }
    a {
      display: inline-block;
      margin-top: 20px;
      text-decoration: none;
      background: #0f39ff;
      color: white;
      padding: 12px 24px;
      border-radius: 999px;
    }
  </style>
</head>
<body>
  <div class="box">
    <h1>Payment Completed</h1>
    <p>Your payment was submitted successfully.</p>
    <a href="/">Make another payment</a>
  </div>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(port=5001, debug=True)