#!/bin/bash
set -e

# Configuration
REPO_URL="${REPO_URL:-git@github.com:bpdu/PondMobilePaymentPage.git}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/pondmobile-payment}"
IMAGE_NAME="pondmobile-payment"
CONTAINER_NAME="pondmobile-payment"
VERSION=$(git rev-parse --short HEAD 2>/dev/null || echo "manual-$(date +%s)")

echo "🚀 Deploying POND Mobile Payment Gateway"
echo "Version: $VERSION"

# Clone or update repository
if [ -d "$DEPLOY_PATH/.git" ]; then
  echo "📦 Pulling latest changes..."
  cd "$DEPLOY_PATH"
  git fetch --all
  git reset --hard origin/main
  git clean -fd
else
  echo "📦 Cloning repository..."
  sudo rm -rf "$DEPLOY_PATH"
  sudo mkdir -p "$(dirname "$DEPLOY_PATH")"
  git clone --depth 1 --branch main "$REPO_URL" "$DEPLOY_PATH"
  cd "$DEPLOY_PATH"
fi

# Build new image with version
echo "🔨 Building Docker image..."
docker build \
  -f deploy/Dockerfile \
  --build-arg BUILD_VERSION="$VERSION" \
  -t "$IMAGE_NAME:$VERSION" \
  -t "$IMAGE_NAME:latest" \
  .

# Stop and remove old container
echo "🛑 Stopping old container..."
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# Remove old images (keep last 2 versions for rollback)
echo "🧹 Cleaning old images..."
docker images --format '{{.Repository}}:{{.Tag}}' | grep "$IMAGE_NAME" | tail -n +3 | xargs -r docker rmi -f || true

# Run new container
echo "🚀 Starting new container..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p 5001:5001 \
  -v pondmobile-logs:/app/logs \
  --env-file deploy/.env.example \
  "$IMAGE_NAME:$VERSION"

# Wait for health check
echo "⏳ Waiting for health check..."
sleep 10

# Verify deployment
HEALTH=$(curl -s http://localhost:5001/health || echo "failed")
echo "🏥 Health check: $HEALTH"

if echo "$HEALTH" | grep -q "healthy \[$VERSION\]"; then
  echo "✅ Deployment successful! Version: $VERSION"
else
  echo "❌ Health check failed!"
  docker logs "$CONTAINER_NAME" --tail 50
  exit 1
fi

# Show running containers
echo "📊 Running containers:"
docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
