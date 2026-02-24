#!/usr/bin/env bash
# =============================================================================
# Lozzalingo Server Setup Script
# =============================================================================
# Idempotent — safe to run multiple times. Run with: sudo bash scripts/server-setup.sh
#
# What it does:
# 1. Creates 2GB swap file if none exists (vm.swappiness=10)
# 2. Installs weekly Docker cleanup cron
# 3. Configures Docker log rotation (10MB max, 3 files)
# 4. Installs unattended-upgrades for automatic security updates
# =============================================================================

set -euo pipefail

echo "=== Lozzalingo Server Setup ==="
echo "Running as: $(whoami)"
echo "Date: $(date)"
echo ""

# ---------------------------------------------------------------------------
# 1. Swap Setup (2GB)
# ---------------------------------------------------------------------------
echo "--- Swap Setup ---"

if swapon --show | grep -q '/swapfile'; then
    echo "Swap already configured:"
    swapon --show
else
    echo "Creating 2GB swap file..."
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile

    # Add to fstab if not already there
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
        echo "Added swap to /etc/fstab"
    fi

    echo "Swap created and enabled:"
    swapon --show
fi

# Set swappiness
CURRENT_SWAPPINESS=$(cat /proc/sys/vm/swappiness)
if [ "$CURRENT_SWAPPINESS" != "10" ]; then
    sysctl vm.swappiness=10
    if ! grep -q 'vm.swappiness' /etc/sysctl.conf; then
        echo 'vm.swappiness=10' >> /etc/sysctl.conf
        echo "Set vm.swappiness=10 (was $CURRENT_SWAPPINESS)"
    fi
else
    echo "Swappiness already set to 10"
fi

echo ""

# ---------------------------------------------------------------------------
# 2. Docker Cleanup Cron (weekly)
# ---------------------------------------------------------------------------
echo "--- Docker Cleanup Cron ---"

CRON_CMD="docker system prune -af --filter 'until=72h'"
CRON_LINE="0 3 * * 0 $CRON_CMD >> /var/log/docker-cleanup.log 2>&1"

if crontab -l 2>/dev/null | grep -q 'docker system prune'; then
    echo "Docker cleanup cron already installed"
else
    (crontab -l 2>/dev/null || true; echo "$CRON_LINE") | crontab -
    echo "Installed weekly Docker cleanup cron (Sunday 3AM)"
fi

echo ""

# ---------------------------------------------------------------------------
# 3. Docker Log Rotation
# ---------------------------------------------------------------------------
echo "--- Docker Log Rotation ---"

DOCKER_DAEMON_JSON="/etc/docker/daemon.json"

if [ -f "$DOCKER_DAEMON_JSON" ] && grep -q 'max-size' "$DOCKER_DAEMON_JSON"; then
    echo "Docker log rotation already configured in $DOCKER_DAEMON_JSON"
else
    mkdir -p /etc/docker

    if [ -f "$DOCKER_DAEMON_JSON" ]; then
        # Merge with existing config using python
        python3 -c "
import json
with open('$DOCKER_DAEMON_JSON', 'r') as f:
    cfg = json.load(f)
cfg['log-driver'] = 'json-file'
cfg['log-opts'] = {'max-size': '10m', 'max-file': '3'}
with open('$DOCKER_DAEMON_JSON', 'w') as f:
    json.dump(cfg, f, indent=2)
print('Merged log rotation into existing daemon.json')
"
    else
        cat > "$DOCKER_DAEMON_JSON" << 'DAEMON_EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
DAEMON_EOF
        echo "Created $DOCKER_DAEMON_JSON with log rotation"
    fi

    # Restart Docker if it's running
    if systemctl is-active --quiet docker 2>/dev/null; then
        echo "Restarting Docker to apply log rotation..."
        systemctl restart docker
        echo "Docker restarted"
    fi
fi

echo ""

# ---------------------------------------------------------------------------
# 4. Unattended Upgrades
# ---------------------------------------------------------------------------
echo "--- Unattended Upgrades ---"

if dpkg -l | grep -q unattended-upgrades 2>/dev/null; then
    echo "unattended-upgrades already installed"
else
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq unattended-upgrades
    echo "Installed unattended-upgrades"
fi

# Enable automatic security updates
if [ -f /etc/apt/apt.conf.d/20auto-upgrades ]; then
    echo "Auto-upgrades already configured"
else
    cat > /etc/apt/apt.conf.d/20auto-upgrades << 'APT_EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
APT_EOF
    echo "Configured automatic security updates"
fi

echo ""
echo "=== Server Setup Complete ==="
echo ""
echo "Summary:"
free -h | head -3
echo ""
swapon --show
echo ""
df -h / | tail -1
