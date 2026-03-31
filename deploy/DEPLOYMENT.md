# Deployment Guide

## Automated Deployment via GitHub Actions

### Prerequisites

**1. Create deploy user on server:**
```bash
# On server
sudo adduser github-deploy
sudo usermod -aG docker github-deploy
```

**2. Generate SSH key:**
```bash
# On your machine
ssh-keygen -t ed25519 -C "github-deploy@pondmobile" -f ~/.ssh/github_deploy_pond
ssh-copy-id -i ~/.ssh/github_deploy_pond.pub github-deploy@your-server-ip

# Test connection
ssh -i ~/.ssh/github_deploy_pond github-deploy@your-server-ip "docker ps"
```

### Required GitHub Secrets

Configure these secrets in: `Repository Settings > Secrets and variables > Actions`

**Note:** All secrets use `POND_PAYMENT_` prefix to avoid conflicts with other repositories.

| Secret | Description | Example |
|--------|-------------|---------|
| `POND_PAYMENT_SERVER_HOST` | Server IP or domain | `123.45.67.89` or `payment.pondmobile.com` |
| `POND_PAYMENT_SERVER_USER` | SSH user | `github-deploy` |
| `POND_PAYMENT_SERVER_SSH_KEY` | Private SSH key | Copy contents of `~/.ssh/id_rsa` |
| `POND_PAYMENT_SERVER_PORT` | SSH port (optional) | `22` (default) |
| `POND_PAYMENT_DEPLOY_PATH` | Deployment directory | `/opt/pondmobile-payment` |
| `POND_PAYMENT_REPO_URL` | Git repository URL | `git@github.com:bpdu/PondMobilePaymentPage.git` |
| `POND_PAYMENT_AUTHORIZE_API_LOGIN_ID` | Authorize.net API Login ID | Your actual ID |
| `POND_PAYMENT_AUTHORIZE_TRANSACTION_KEY` | Authorize.net Transaction Key | Your actual key |

### Setting up SSH Key

```bash
# Generate SSH key on your machine
ssh-keygen -t ed25519 -C "github-deploy" -f ~/.ssh/github_deploy

# Copy PUBLIC key to server
ssh-copy-id -i ~/.ssh/github_deploy.pub user@your-server.com

# Copy PRIVATE key content to GitHub Secret POND_PAYMENT_SERVER_SSH_KEY
cat ~/.ssh/github_deploy
```

### Environment Configuration

**Application configuration** (managed in repository):
```bash
# config/config.txt - Application URLs
APP_BASE_URL=https://www.pondmobile.com
ALLOWED_ORIGINS=https://www.pondmobile.com,https://pondmobile.com,http://localhost:5001,http://127.0.0.1:5001
```

**Secrets** (managed in GitHub Secrets):
- `POND_PAYMENT_AUTHORIZE_API_LOGIN_ID` - Authorize.net credentials
- `POND_PAYMENT_AUTHORIZE_TRANSACTION_KEY` - Authorize.net transaction key

**Note:** ALLOWED_ORIGINS includes localhost for testing. You can test the deployed API from your local machine.

**Production features (always enabled):**
- Dual logging: files (logs/*.log) + stdout (docker logs)
- Security headers: HSTS, CSP, X-Frame-Options, etc.

### Manual Deployment Trigger

1. Go to `Actions` tab in GitHub
2. Select `Deploy to Production`
3. Click `Run workflow` button

**Automatic deployment:** Every push to `main` branch triggers deployment.

---

## Manual Deployment

### Prerequisites

- Docker installed on server
- Git access to repository
- GitHub Secrets configured with Authorize.net credentials
- `config/config.txt` contains application URLs (defaults are production-ready)

### Manual Docker Commands

```bash
# Build image with version
docker build \
  -f deploy/Dockerfile \
  --build-arg BUILD_VERSION=$(git rev-parse --short HEAD) \
  -t pondmobile-payment:latest \
  .

# Run container with secrets from environment
docker run -d \
  --name pondmobile-payment \
  --restart unless-stopped \
  -p 5001:5001 \
  -v pondmobile-logs:/app/logs \
  -e AUTHORIZE_API_LOGIN_ID=your-api-login-id \
  -e AUTHORIZE_TRANSACTION_KEY=your-transaction-key \
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

**Testing from your local machine:**
```bash
curl http://your-server-ip:5001/health
```

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
  -e AUTHORIZE_API_LOGIN_ID=your-api-login-id \
  -e AUTHORIZE_TRANSACTION_KEY=your-transaction-key \
  pondmobile-payment:abc1234
```
