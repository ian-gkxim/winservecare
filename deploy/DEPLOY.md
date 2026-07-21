# Deployment Guide

## Prerequisites (Manual Steps)

These steps require human interaction and cannot be automated:

### 1. Google Maps API Key
- Go to: https://console.cloud.google.com/google/maps-apis/credentials
- Create a project or select an existing one
- Enable billing (required for Maps API; $200/month free credit)
- Enable these APIs:
  - Distance Matrix API: https://console.cloud.google.com/apis/library/distance-matrix-backend.googleapis.com
  - Maps JavaScript API: https://console.cloud.google.com/apis/library/maps-backend.googleapis.com
- Create an API key and optionally restrict it to those two APIs

### 2. AWS Account & EC2
- Sign in to AWS Console: https://console.aws.amazon.com
- Go to EC2 → Launch Instance
- Settings:
  - **AMI**: Ubuntu 22.04 LTS (or Amazon Linux 2023)
  - **Instance type**: t3.small (2 vCPU, 2 GB RAM — sufficient for this prototype)
  - **Storage**: 20 GB gp3
  - **Security group**: Allow inbound on ports 22 (SSH), 80 (HTTP), 443 (HTTPS), 8000 (app)
  - **Key pair**: Create or select an SSH key pair
- Launch the instance and note the public IP

### 3. Domain (Optional)
- If you want HTTPS with a custom domain, point a DNS A record to your EC2 public IP
- Caddy (installed by the setup script) handles automatic Let's Encrypt certificates

---

## Deployment Steps

### Option A: Docker on EC2 (Recommended)

```bash
# 1. SSH into your EC2 instance
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>

# 2. Run the setup script (installs Docker + Caddy)
curl -sSL https://raw.githubusercontent.com/<your-repo>/main/deploy/ec2-setup.sh | bash
# Or copy and run manually

# 3. Clone your project
git clone <your-repo-url> winserve-care
cd winserve-care

# 4. Build the Docker image
docker build -t winserve-care .

# 5. Run the container
docker run -d \
  --name winserve \
  -p 8000:8000 \
  -v winserve-data:/app/data \
  -e CORS_ORIGIN=http://<EC2_PUBLIC_IP>:8000 \
  --restart unless-stopped \
  winserve-care

# 6. Verify it's running
curl http://localhost:8000/health
# Should return: {"status":"ok"}
```

Access at: `http://<EC2_PUBLIC_IP>:8000`

### Option B: Docker Compose

```bash
cd winserve-care/deploy
CORS_ORIGIN=http://<EC2_PUBLIC_IP>:8000 docker compose up -d --build
```

### Adding HTTPS (Optional)

If you have a domain pointing to the EC2 IP:

```bash
sudo tee /etc/caddy/Caddyfile <<EOF
yourdomain.com {
    reverse_proxy localhost:8000
}
EOF
sudo systemctl restart caddy
```

Caddy automatically obtains and renews Let's Encrypt certificates.

Update CORS:
```bash
docker rm -f winserve
docker run -d \
  --name winserve \
  -p 8000:8000 \
  -v winserve-data:/app/data \
  -e CORS_ORIGIN=https://yourdomain.com \
  --restart unless-stopped \
  winserve-care
```

---

## Post-Deployment Configuration

1. Open the app in your browser: `http://<EC2_PUBLIC_IP>:8000`
2. Navigate to **Configuration** (gear icon in sidebar)
3. Enter your Google Maps API key and click Save
4. Navigate to **Dashboard** and click **Run Optimisation**

---

## EC2 Cost Estimate

| Resource | Cost |
|----------|------|
| t3.small (on-demand) | ~$15/month |
| 20 GB gp3 storage | ~$1.60/month |
| Data transfer (light) | ~$1/month |
| **Total** | **~$18/month** |

Use a t3.micro ($8/month) for a minimal demo — it'll be a bit slower but functional.

---

## Monitoring & Maintenance

```bash
# View logs
docker logs winserve --tail 50

# Restart
docker restart winserve

# Update to latest code
cd winserve-care
git pull
docker build -t winserve-care .
docker rm -f winserve
docker run -d --name winserve -p 8000:8000 -v winserve-data:/app/data --restart unless-stopped winserve-care

# Backup SQLite database
docker cp winserve:/app/data/care_ops.db ./backup-$(date +%Y%m%d).db
```
