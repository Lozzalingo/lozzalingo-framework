# Lozzalingo Deployment Guide

Production deployment reference for Lozzalingo-powered sites. Written for both humans and Claude.

---

## 1. Architecture Overview

```
                    ┌─────────────┐
                    │   Internet  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │     DNS     │
                    │  (A record) │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │    Nginx    │
                    │  (SSL/TLS)  │
                    │  port 80/443│
                    └──────┬──────┘
                           │ proxy_pass
                    ┌──────▼──────┐
                    │   Docker    │
                    │  Container  │
                    │  ┌────────┐ │
                    │  │Gunicorn│ │
                    │  │ Flask  │ │
                    │  │Lozzalng│ │
                    │  └───┬────┘ │
                    │      │      │
                    │  ┌───▼────┐ │
                    │  │ SQLite │ │
                    │  │  DBs   │ │
                    │  └────────┘ │
                    └─────────────┘
```

**Stack:** Nginx (reverse proxy + SSL) → Docker (Gunicorn + Flask + Lozzalingo) → SQLite

**Why this stack:**
- Nginx handles SSL termination, static files, and reverse proxy
- Docker isolates the app and makes deploys reproducible
- Gunicorn is the production WSGI server (replaces Flask's dev server)
- SQLite keeps things simple — no separate database server to manage

---

## 2. Server Provisioning

**Recommended:** DigitalOcean droplet, Ubuntu 22.04 LTS

| Size | vCPUs | RAM | Disk | Cost | Good for |
|------|-------|-----|------|------|----------|
| Basic $6/mo | 1 | 1GB | 25GB | $6/mo | Single site |
| Basic $12/mo | 1 | 2GB | 50GB | $12/mo | 2-3 sites |
| Basic $24/mo | 2 | 4GB | 80GB | $24/mo | 4+ sites |

**Current server:** 143.110.152.203 (hosts laurencedotcomputer, crowd_sauced, product-gap)

### Creating a New Droplet
1. Go to cloud.digitalocean.com → Create → Droplets
2. Choose Ubuntu 22.04 LTS
3. Select size (start with $6/mo, resize later if needed)
4. Choose datacenter region closest to your audience
5. Add your SSH key (Authentication → SSH keys)
6. Create droplet
7. Note the IP address

### Initial SSH Access
```bash
# Add your SSH key to the agent
ssh-add ~/.ssh/id_ed25519_droplet

# Connect
ssh root@<SERVER_IP>
```

---

## 3. Server Hardening

Run the Lozzalingo server setup script. It's idempotent — safe to run multiple times.

```bash
# On the server:
curl -fsSL https://raw.githubusercontent.com/Lozzalingo/lozzalingo-framework/main/scripts/server-setup.sh | sudo bash
```

Or copy and run manually:
```bash
# From your local machine:
scp /path/to/lozzalingo-framework/scripts/server-setup.sh root@<SERVER_IP>:/tmp/
ssh root@<SERVER_IP> "bash /tmp/server-setup.sh"
```

**What it does:**
1. Creates 2GB swap file (vm.swappiness=10) — prevents OOM on small droplets
2. Installs weekly Docker cleanup cron (Sundays 3AM) — reclaims disk from old images
3. Configures Docker log rotation (10MB max, 3 files) — prevents log bloat
4. Installs unattended-upgrades — automatic security patches

### UFW Firewall Setup
Run this manually after the setup script:

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh          # Port 22
ufw allow http         # Port 80
ufw allow https        # Port 443
ufw --force enable
ufw status
```

**Important:** Do NOT open your app ports (5000, 5001, etc.) in UFW. Nginx proxies traffic internally — the app ports should only be accessible from localhost.

---

## 4. Docker Installation

If Docker isn't already installed:

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose plugin
apt-get update
apt-get install -y docker-compose-plugin

# Verify
docker --version
docker compose version
```

---

## 5. Nginx Setup

### Install Nginx
```bash
apt-get install -y nginx
systemctl enable nginx
systemctl start nginx
```

### Site Configuration
Create a config file for each site:

```bash
cat > /etc/nginx/sites-available/<site_slug> << 'EOF'
server {
    listen 80;
    server_name <DOMAIN>;

    # Redirect to HTTPS (added by certbot, but include as fallback)
    # return 301 https://$host$request_uri;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:<PORT>;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }

    # Serve static files directly (bypasses app for performance)
    location /static/ {
        alias /var/www/<site_slug>/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Block sensitive paths
    location ~ /\. {
        deny all;
    }
    location ~ \.db$ {
        deny all;
    }
}
EOF
```

### Enable the Site
```bash
ln -sf /etc/nginx/sites-available/<site_slug> /etc/nginx/sites-enabled/

# Test config
nginx -t

# Reload
systemctl reload nginx
```

### Nginx for Multiple Sites
Each site gets its own config file in `/etc/nginx/sites-available/`. They can all coexist — Nginx routes by `server_name`.

**Current Nginx configs on 143.110.152.203:**
```
/etc/nginx/sites-available/
├── crowdsauced           # crowdsauced.laurence.computer → 127.0.0.1:5001
├── laurence.computer     # laurence.computer → 127.0.0.1:5002
├── product-gap           # productgap.laurence.computer → 127.0.0.1:5020
└── default               # catch-all
```

---

## 6. SSL with Let's Encrypt

### Install Certbot
```bash
apt-get install -y certbot python3-certbot-nginx
```

### Obtain Certificate
```bash
certbot --nginx -d <DOMAIN> --non-interactive --agree-tos -m <ADMIN_EMAIL>
```

For multiple domains on one cert:
```bash
certbot --nginx -d example.com -d www.example.com --non-interactive --agree-tos -m admin@example.com
```

### Verify Auto-Renewal
```bash
certbot renew --dry-run
```

Certbot installs a systemd timer that auto-renews certificates before they expire. Verify it's active:
```bash
systemctl status certbot.timer
```

---

## 7. Application Deployment

### Directory Convention
All Lozzalingo apps live under `/var/www/`:

```
/var/www/
├── crowd-sauced/          # Port 5001
│   ├── lozzalingo-repo/   # Framework clone
│   ├── lozzalingo -> lozzalingo-repo/lozzalingo  # Symlink
│   ├── main.py
│   ├── databases/
│   └── docker-compose.yml
├── laurence.computer/     # Port 5002
│   ├── lozzalingo-repo/
│   ├── lozzalingo -> lozzalingo-repo/lozzalingo
│   ├── main.py
│   ├── databases/
│   └── docker-compose.yml
├── product-gap/           # Port 5020
│   └── ...
└── <your-new-site>/       # Port <PORT>
    └── ...
```

### Deployment Steps

#### 1. Create app directory
```bash
ssh root@<SERVER_IP> "mkdir -p /var/www/<site_slug>"
```

#### 2. Get the code onto the server

**Option A: Git clone (preferred)**
```bash
ssh root@<SERVER_IP> "cd /var/www/<site_slug> && git clone <REPO_URL> ."
```

**Option B: SCP (if not in git yet)**
```bash
scp -r ./* root@<SERVER_IP>:/var/www/<site_slug>/
```

Do NOT scp `.env` or `databases/` — those are created separately on the server.

#### 3. Clone the framework
```bash
ssh root@<SERVER_IP> "cd /var/www/<site_slug> && git clone https://github.com/Lozzalingo/lozzalingo-framework.git lozzalingo-repo"
```

If the framework repo is already cloned for another site, you can share it:
```bash
# Option: Symlink to another site's framework clone (saves disk)
ssh root@<SERVER_IP> "cd /var/www/<site_slug> && ln -sf /var/www/laurence.computer/lozzalingo-repo lozzalingo-repo"
```

#### 4. Create the framework symlink
```bash
ssh root@<SERVER_IP> "cd /var/www/<site_slug> && ln -sf lozzalingo-repo/lozzalingo lozzalingo"
```

#### 5. Create production `.env`
```bash
ssh root@<SERVER_IP> "cat > /var/www/<site_slug>/.env << 'EOF'
FLASK_ENV=production
SECRET_KEY=<generate: python3 -c 'import secrets; print(secrets.token_hex(32))'>
RESEND_API_KEY=<your-key>
EMAIL_ADDRESS=noreply@<domain>
EMAIL_PROVIDER=resend
GOOGLE_CLIENT_ID=<your-id>
GOOGLE_CLIENT_SECRET=<your-secret>
EOF"
```

#### 6. Create databases directory
```bash
ssh root@<SERVER_IP> "mkdir -p /var/www/<site_slug>/databases"
```

#### 7. Build and start
```bash
ssh root@<SERVER_IP> "cd /var/www/<site_slug> && docker compose up -d --build"
```

#### 8. Verify container is running
```bash
ssh root@<SERVER_IP> "docker ps | grep <site_slug>"
ssh root@<SERVER_IP> "curl -s http://localhost:<PORT>/health | python3 -m json.tool"
```

---

## 8. DNS Configuration

### For *.laurence.computer Subdomains
A wildcard A record `*.laurence.computer` already points to `143.110.152.203`. Just pick a subdomain and configure Nginx — no DNS changes needed.

To add a specific subdomain (if no wildcard exists):
1. Go to DigitalOcean → Networking → Domains → laurence.computer
2. Add A record: hostname = `<subdomain>`, value = `143.110.152.203`, TTL = 3600

### For External Domains
1. At your domain registrar, add an A record:
   - Type: A
   - Host: `@` (or `www`)
   - Value: `<SERVER_IP>`
   - TTL: 3600
2. Wait for DNS propagation (usually 5-30 minutes, can take up to 48 hours)
3. Verify: `dig +short <domain>`

### Verifying DNS
```bash
# Check A record
dig +short <domain>

# Check from multiple locations
nslookup <domain>

# Should return your server IP
```

---

## 9. Monitoring & Maintenance

### Built-in Health Check
Every Lozzalingo app exposes `GET /health` (no auth required):
```bash
curl -s https://<domain>/health | python3 -m json.tool
```

Returns:
```json
{
  "status": "healthy",
  "checks": {
    "disk": {"percent": 45, "status": "ok"},
    "memory": {"percent": 62, "status": "ok"},
    "uptime": {"seconds": 86400, "status": "ok"}
  },
  "issues": []
}
```

### Docker Commands
```bash
# View running containers
docker ps

# View logs (last 100 lines)
docker logs --tail 100 <container_name>

# Follow logs in real time
docker logs -f <container_name>

# Restart a container
docker compose restart

# Rebuild and restart (after code changes)
docker compose up -d --build

# Stop
docker compose down

# Shell into container
docker exec -it <container_name> bash
```

### Disk Management
```bash
# Check disk usage
df -h /

# Find large files
du -sh /var/www/*/databases/*

# Docker disk usage
docker system df

# Clean up (removes unused images, containers, networks)
docker system prune -af --filter 'until=72h'
```

### Log Review
```bash
# App logs (via Docker)
docker logs --tail 50 <container_name>

# Nginx access logs
tail -50 /var/log/nginx/access.log

# Nginx error logs
tail -50 /var/log/nginx/error.log

# System logs
journalctl -u nginx --since "1 hour ago"
```

---

## 10. Updating the Framework

### Symlink Pattern (laurencedotcomputer, crowd_sauced)
The app symlinks to a local clone of the framework. To update:

```bash
# On the server:
cd /var/www/<site_slug>/lozzalingo-repo
git pull

# Rebuild the container (framework code is COPY'd into image at build time)
cd /var/www/<site_slug>
docker compose up -d --build
```

**Important:** If multiple sites share the same `lozzalingo-repo` clone, pulling once updates all of them. But each site needs its own `docker compose up -d --build` to pick up the changes.

**All symlink sites on the DigitalOcean droplet:**
```bash
# Update framework for all sites at once
for site in laurence.computer crowd-sauced product-gap; do
    cd /var/www/$site/lozzalingo-repo && git pull
    cd /var/www/$site && docker compose up -d --build
done
```

### Pip Pattern (Mario Pinto)
The framework is installed via pip inside the container:

```bash
docker compose exec -T web pip install --no-cache-dir --force-reinstall git+https://github.com/Lozzalingo/lozzalingo-framework.git@main
docker compose restart web
```

### Updating App Code
```bash
cd /var/www/<site_slug>
git pull
docker compose up -d --build
```

---

## 11. Backup Strategy

### Database Backup (Manual)
```bash
# Copy databases to local machine
scp -r root@<SERVER_IP>:/var/www/<site_slug>/databases/ ./backups/<site_slug>-$(date +%Y%m%d)/
```

### Database Backup (Automated — Cron)
Add to server crontab (`crontab -e`):

```bash
# Daily backup at 2AM — copy databases to /root/backups/
0 2 * * * for site in /var/www/*/databases; do sitename=$(basename $(dirname $site)); mkdir -p /root/backups/$sitename && cp -r $site/* /root/backups/$sitename/; done
```

### Optional: Offsite Backup to DigitalOcean Spaces
```bash
# Install s3cmd
apt-get install -y s3cmd

# Configure (one-time)
s3cmd --configure  # Enter DO Spaces credentials

# Backup script
#!/bin/bash
DATE=$(date +%Y%m%d)
for site_dir in /var/www/*/databases; do
    site=$(basename $(dirname $site_dir))
    tar czf /tmp/${site}-${DATE}.tar.gz -C $site_dir .
    s3cmd put /tmp/${site}-${DATE}.tar.gz s3://your-space/backups/${site}/
    rm /tmp/${site}-${DATE}.tar.gz
done
```

---

## 12. Troubleshooting

### Container Won't Start
```bash
# Check logs
docker logs <container_name>

# Common causes:
# - Missing .env file → create one
# - Port conflict → change port in docker-compose.yml
# - Missing framework symlink → recreate it
# - Python syntax error → check docker logs for traceback
```

### 502 Bad Gateway
Nginx can reach the port but the app isn't responding.

```bash
# Is the container running?
docker ps | grep <site_slug>

# Is it healthy?
docker inspect <container_name> --format='{{.State.Health.Status}}'

# Check app logs
docker logs --tail 50 <container_name>

# Test from inside the server
curl -s http://localhost:<PORT>/health
```

Common fixes:
- Container crashed → `docker compose up -d`
- Wrong port in Nginx config → check `proxy_pass` matches Docker port
- Gunicorn timeout → increase `--timeout` in Dockerfile CMD

### Static Files Return 404
```bash
# Check Nginx alias path matches actual directory
ls -la /var/www/<site_slug>/static/

# Verify Nginx config
grep -A3 'location /static' /etc/nginx/sites-available/<site_slug>

# The alias path must end with / and match the real path
```

### SSL Certificate Issues
```bash
# Check certificate status
certbot certificates

# Force renewal
certbot renew --force-renewal

# Test auto-renewal
certbot renew --dry-run

# Check Nginx SSL config
nginx -t
```

### Database Locked
SQLite can lock if multiple processes write simultaneously. Gunicorn with multiple workers can cause this.

```bash
# Fix: Reduce workers to 2 (default in our Dockerfile)
# In Dockerfile CMD:
CMD ["gunicorn", "--bind", "0.0.0.0:<PORT>", "--workers", "2", "--timeout", "120", "main:app"]
```

For high-traffic sites, consider switching to PostgreSQL (`DATABASE_URL` env var).

### Disk Full
```bash
# Check disk usage
df -h /

# Docker is usually the culprit
docker system df
docker system prune -af --filter 'until=72h'

# Check database sizes
du -sh /var/www/*/databases/*

# Check Docker logs
ls -lh /var/lib/docker/containers/*/

# Nuclear option: remove all stopped containers and unused images
docker system prune -af
```

---

## 13. Quick Reference Card

### SSH
```bash
ssh-add ~/.ssh/id_ed25519_droplet
ssh root@143.110.152.203
```

### Deploy New Code
```bash
ssh root@<SERVER_IP> "cd /var/www/<site_slug> && git pull && docker compose up -d --build"
```

### Update Framework
```bash
ssh root@<SERVER_IP> "cd /var/www/<site_slug>/lozzalingo-repo && git pull && cd .. && docker compose up -d --build"
```

### View Logs
```bash
ssh root@<SERVER_IP> "docker logs --tail 100 <container_name>"
```

### Restart App
```bash
ssh root@<SERVER_IP> "cd /var/www/<site_slug> && docker compose restart"
```

### Health Check
```bash
curl -s https://<domain>/health | python3 -m json.tool
```

### Backup Databases
```bash
scp -r root@<SERVER_IP>:/var/www/<site_slug>/databases/ ./backups/
```

### Add New Nginx Site
```bash
# 1. Create config
nano /etc/nginx/sites-available/<site_slug>

# 2. Enable
ln -sf /etc/nginx/sites-available/<site_slug> /etc/nginx/sites-enabled/

# 3. Test & reload
nginx -t && systemctl reload nginx

# 4. SSL
certbot --nginx -d <domain>
```

### Port Allocation Table
| Port | App | Domain | Status |
|------|-----|--------|--------|
| 5000 | starter-template | (local dev only) | Dev |
| 5001 | crowd_sauced | crowdsauced.laurence.computer | Live |
| 5002 | laurencedotcomputer | laurence.computer | Live |
| 5003 | (next available) | — | — |
| 5010 | Mario Pinto | mariopinto.co.uk | Live (AWS) |
| 5020 | product-gap | productgap.laurence.computer | Live |

### Auto-Generated Scripts
New sites created via site-launcher include:
- `scripts/deploy.sh` — rsync + Docker deploy (run locally, deploys to server)
- `scripts/<site_slug>.nginx.conf` — Nginx reverse proxy config with SSL + security

### Post-Deploy Configuration
After deploying a new site:
1. Create admin: `https://<domain>/admin/create-admin`
2. Visit **`/admin/settings/`** to configure API keys, email, and Stripe via the UI
3. Check the **Setup Status** banner for missing configuration items
4. Register Stripe webhook: `https://<domain>/stripe/webhook` in the Stripe dashboard
5. Test email connection via the Settings page "Test Resend Connection" button
