#!/usr/bin/env bash
set -e

echo "=================================================="
echo "    Installing Docker & Docker Compose on Kali    "
echo "=================================================="

# Check if running as root or via sudo
if [ "$EUID" -ne 0 ]; then
    echo "This script requires superuser privileges to install Docker packages."
    echo "Running with sudo..."
    exec sudo bash "$0" "$@"
fi

TARGET_USER="${SUDO_USER:-$USER}"

echo "[1/4] Updating package index..."
apt-get update

echo "[2/4] Installing docker.io and docker-compose..."
apt-get install -y docker.io docker-compose

echo "[3/4] Enabling and starting Docker service..."
systemctl enable docker
systemctl start docker

echo "[4/4] Adding user '${TARGET_USER}' to 'docker' and 'render' groups..."
usermod -aG docker "${TARGET_USER}"
usermod -aG render "${TARGET_USER}" || true

echo "=================================================="
echo " Docker installation complete!"
echo " Note: Group changes take effect on your next login"
echo " or by running: newgrp docker"
echo "=================================================="
