#!/bin/bash
# 构建客户端交付包
# Usage: ./build-deploy.sh [version]

set -e
cd "$(dirname "$0")"

VERSION="${1:-$(date +%Y%m%d)}"
IMAGE_NAME="lingmo-app"
IMAGE="${IMAGE_NAME}:${VERSION}"
IMAGE_TAR="${IMAGE_NAME}-${VERSION}.tar"
PACKAGE="lingmo-deploy-${VERSION}"

echo "=== 灵墨交付包构建 ==="
echo "版本: ${VERSION}"

# 1. Build Docker image
echo "[1/4] 构建 Docker 镜像..."
docker build -t "${IMAGE}" .

# 2. Export image as tar
echo "[2/4] 导出镜像..."
docker save -o "${IMAGE_TAR}" "${IMAGE}"

# 3. Create deploy package
echo "[3/4] 打包交付文件..."
mkdir -p "${PACKAGE}"
cp .env.example DEPLOY.md "${PACKAGE}/"

# Create dedicated compose file for client
cat > "${PACKAGE}/docker-compose.yml" << COMPOSE
services:
  app:
    image: ${IMAGE}
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/status', timeout=5).read()"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
COMPOSE

tar czf "${PACKAGE}.tar.gz" "${PACKAGE}/"

# Cleanup
rm -rf "${PACKAGE}"

echo "[4/4] 完成"
echo ""
echo "交付文件:"
echo "  ${IMAGE_TAR}     (Docker 镜像)"
echo "  ${PACKAGE}.tar.gz (部署包：含 compose + .env + 说明)"
echo ""
echo "客户端操作:"
echo "  1. docker load -i ${IMAGE_TAR}"
echo "  2. tar xzf ${PACKAGE}.tar.gz && cd ${PACKAGE}"
echo "  3. cp .env.example .env && vi .env"
echo "  4. docker compose up -d"
