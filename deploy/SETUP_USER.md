# Server Setup for GitHub Actions Deployment

## Create Deploy User on Server

Run these commands on your server:

```bash
# 1. Create user
sudo adduser github-deploy

# 2. Add to docker group (required for container management)
sudo usermod -aG docker github-deploy

# 3. Verify docker access
su - github-deploy
docker ps
exit

# 4. (Optional) Setup passwordless sudo for docker operations
sudo visudo
# Add this line:
# github-deploy ALL=(ALL) NOPASSWD:/usr/bin/docker,/usr/bin/git
```

## Generate SSH Key for GitHub Actions

On your local machine:

```bash
# Generate dedicated SSH key
ssh-keygen -t ed25519 -C "github-deploy@pondmobile" -f ~/.ssh/github_deploy_pond

# Copy public key to server
ssh-copy-id -i ~/.ssh/github_deploy_pond.pub github-deploy@your-server-ip

# Test connection
ssh -i ~/.ssh/github_deploy_pond github-deploy@your-server-ip
```

## Configure GitHub Secrets

Add these secrets in `Repository Settings > Secrets and variables > Actions`:

| Secret | Value |
|--------|-------|
| `POND_PAYMENT_SERVER_HOST` | Your server IP or domain |
| `POND_PAYMENT_SERVER_USER` | `github-deploy` |
| `POND_PAYMENT_SERVER_SSH_KEY` | Contents of `~/.ssh/github_deploy_pond` |
| `POND_PAYMENT_SERVER_PORT` | `22` (default) |
| `POND_PAYMENT_DEPLOY_PATH` | `/opt/pondmobile-payment` |
| `POND_PAYMENT_REPO_URL` | `git@github.com:bpdu/PondMobilePaymentPage.git` |

**Note:** Copy the PRIVATE key (`github_deploy_pond`), not the `.pub` file!

## Verify Setup

```bash
# On your local machine, test SSH access
ssh -i ~/.ssh/github_deploy_pond github-deploy@your-server-ip "docker ps"

# Expected output: list of running containers (or empty list)
```

## Security Hardening (Optional)

### Restrict SSH user to docker only

Add to `/etc/ssh/sshd_config`:

```ssh
Match User github-deploy
    ForceCommand /usr/bin/docker
    PermitTTY no
    X11Forwarding no
```

Then restart SSH:
```bash
sudo systemctl restart sshd
```

### Setup fail2ban

```bash
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

## Deploy Directory Permissions

```bash
# On server, create deploy directory with correct permissions
sudo mkdir -p /opt/pondmobile-payment
sudo chown github-deploy:github-deploy /opt/pondmobile-payment
sudo chmod 755 /opt/pondmobile-payment
```

## Troubleshooting

### SSH connection fails
```bash
# Check SSH logs on server
sudo journalctl -u sshd -n 50

# Verify key is authorized
sudo cat /home/github-deploy/.ssh/authorized_keys
```

### Docker permission denied
```bash
# Verify user is in docker group
groups github-deploy

# Re-add to group if needed
sudo usermod -aG docker github-deploy
```

### Cannot write to deploy directory
```bash
# Fix permissions
sudo chown -R github-deploy:github-deploy /opt/pondmobile-payment
```
