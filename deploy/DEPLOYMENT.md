# Deployment Guide

## Automated Deployment via GitHub Actions

### Required GitHub Secrets

Configure these secrets in: `Repository Settings > Secrets and variables > Actions`

**Note:** All secrets use `POND_PAYMENT_` prefix to avoid conflicts with other repositories.

| Secret | Description | Example |
|--------|-------------|---------|
| `POND_PAYMENT_SERVER_HOST` | Server IP or domain | `123.45.67.89` or `payment.example.com` |
| `POND_PAYMENT_SERVER_USER` | SSH user | `root` or `deploy` |
| `POND_PAYMENT_SERVER_SSH_KEY` | Private SSH key | Copy contents of `~/.ssh/id_rsa` |
| `POND_PAYMENT_SERVER_PORT` | SSH port (optional) | `22` (default) |
| `POND_PAYMENT_DEPLOY_PATH` | Deployment directory | `/opt/pondmobile-payment` |
| `POND_PAYMENT_REPO_URL` | Git repository URL | `git@github.com:bpdu/PondMobilePaymentPage.git` |

### Setting up SSH Key

```bash
# Generate SSH key on your machine
ssh-keygen -t ed25519 -C "github-deploy" -f ~/.ssh/github_deploy

# Copy PUBLIC key to server
ssh-copy-id -i ~/.ssh/github_deploy.pub user@your-server.com

# Copy PRIVATE key content to GitHub Secret SERVER_SSH_KEY
cat ~/.ssh/github_deploy
```

### Environment Configuration

Before deploying, configure `deploy/.env` on the server:

```bash
# On the server
cd /opt/pondmobile-payment
cp deploy/.env.example deploy/.env
nano deploy/.env
```

**Critical settings for production:**

```bash
# Authorize.net credentials (required)
AUTHORIZE_API_LOGIN_ID=your-actual-api-login-id
AUTHORIZE_TRANSACTION_KEY=your-actual-transaction-key

# ⚠️ IMPORTANT: Use public domain/IP, NOT localhost
# This URL is used for payment return after Authorize.net checkout
APP_BASE_URL=https://www.pondmobile.com

# CORS origins - must match where users access the payment form
ALLOWED_ORIGINS=https://www.pondmobile.com,https://pondmobile.com

# Production mode
FLASK_ENV=production
DOCKER_ENV=true
```

**Why NOT localhost?**
- `APP_BASE_URL`: After payment, user is redirected to this URL. If `localhost`, they'll go to their own machine, not your server.
- `ALLOWED_ORIGINS`: Browser blocks requests from different origins. If `localhost`, external users can't access your form.
```

### Manual Deployment Trigger

1. Go to `Actions` tab in GitHub
2. Select `Deploy to Production`
3. Click `Run workflow` button

---

## Manual Deployment

### Prerequisites

- Docker installed on server
- Git access to repository
- `deploy/.env` configured with production values (⚠️ **NOT localhost**)

### Quick Deploy

```bash
# Clone repo
git clone git@github.com:bpdu/PondMobilePaymentPage.git
cd PondMobilePaymentPage

# Run deploy script
cd deploy
./deploy.sh
```

### Manual Docker Commands

```bash
# Build image with version
docker build \
  -f deploy/Dockerfile \
  --build-arg BUILD_VERSION=$(git rev-parse --short HEAD) \
  -t pondmobile-payment:latest \
  .

# Run container
docker run -d \
  --name pondmobile-payment \
  --restart unless-stopped \
  -p 5001:5001 \
  -v pondmobile-logs:/app/logs \
  --env-file deploy/.env \
  pondmobile-payment:latest
```

---

## Health Check

After deployment, verify the service:

```bash
curl http://localhost:5001/health
# Response: {"status": "healthy [abc1234]"}
```

The response includes:
- `healthy` - service status
- `[abc1234]` - short SHA of deployed commit

---

## Logs

View application logs:

```bash
# Docker logs
docker logs -f pondmobile-payment

# Persistent logs (in volume)
docker exec pondmobile-payment tail -f /app/logs/access.log
docker exec pondmobile-payment tail -f /app/logs/security.log
```

---

## Rollback

To rollback to previous version:

```bash
# List available versions
docker images pondmobile-payment

# Run specific version
docker stop pondmobile-payment
docker rm pondmobile-payment
docker run -d \
  --name pondmobile-payment \
  --restart unless-stopped \
  -p 5001:5001 \
  -v pondmobile-logs:/app/logs \
  --env-file deploy/.env \
  pondmobile-payment:abc1234
```
