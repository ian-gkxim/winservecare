#!/bin/bash
# EC2 Instance Setup Script
# Run this on a fresh Amazon Linux 2023 or Ubuntu 22.04 instance
# Usage: ssh into your instance and run: bash ec2-setup.sh

set -e

echo "=== WinServe Care AI Optimiser - EC2 Setup ==="

# Update system
sudo apt-get update && sudo apt-get upgrade -y 2>/dev/null || \
sudo yum update -y 2>/dev/null

# Install Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
    sudo systemctl enable docker
    sudo systemctl start docker
    echo "Docker installed. You may need to log out and back in for group membership."
fi

# Install Docker Compose (if not bundled)
if ! command -v docker compose &> /dev/null; then
    echo "Installing Docker Compose plugin..."
    sudo mkdir -p /usr/local/lib/docker/cli-plugins
    sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m) \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

# Install Caddy (reverse proxy with automatic HTTPS)
if ! command -v caddy &> /dev/null; then
    echo "Installing Caddy..."
    sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl 2>/dev/null && \
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg && \
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list && \
    sudo apt-get update && sudo apt-get install caddy -y 2>/dev/null || \
    echo "Caddy install skipped (install manually if needed for HTTPS)"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "1. Clone/copy your project to this instance"
echo "2. Run: docker build -t winserve-care ."
echo "3. Run: docker run -d -p 8000:8000 -v winserve-data:/app/data --name winserve winserve-care"
echo "4. Access the app at http://<your-ec2-public-ip>:8000"
echo ""
echo "For HTTPS with a domain, configure Caddy:"
echo "  sudo tee /etc/caddy/Caddyfile <<EOF"
echo "  yourdomain.com {"
echo "    reverse_proxy localhost:8000"
echo "  }"
echo "  EOF"
echo "  sudo systemctl restart caddy"
