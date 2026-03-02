#!/bin/bash
# deploy.sh — Deploy <SITE_NAME> to the serving droplet
#
# Usage: ./scripts/deploy.sh
#
# Replace <PLACEHOLDER> values before first use.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVER="<SERVER_IP>"
SSH_KEY="$HOME/.ssh/id_ed25519_droplet"
REMOTE_DIR="/var/www/<SITE_SLUG>"
LOZZALINGO_DIR="/var/www/<SITE_SLUG>/lozzalingo-repo"

echo "[Deploy] Deploying <SITE_NAME> to $SERVER..."

# Ensure SSH agent has the key
ssh-add -l | grep -q "id_ed25519_droplet" || {
    echo "[Deploy] Adding SSH key..."
    ssh-add "$SSH_KEY"
}

SSH_CMD="ssh -i $SSH_KEY root@$SERVER"

# Create remote directories
$SSH_CMD "mkdir -p $REMOTE_DIR/databases $REMOTE_DIR/logs"

# Sync project files
echo "[Deploy] Syncing project files..."
rsync -avz --delete \
    --exclude '.env' \
    --exclude 'databases/' \
    --exclude '__pycache__/' \
    --exclude '.git/' \
    --exclude 'venv/' \
    --exclude 'lozzalingo' \
    --exclude 'node_modules/' \
    --exclude '.DS_Store' \
    -e "ssh -i $SSH_KEY" \
    "$PROJECT_DIR/" "root@$SERVER:$REMOTE_DIR/"

# Clone/update lozzalingo framework on server
echo "[Deploy] Setting up lozzalingo..."
$SSH_CMD "
    if [ ! -d $LOZZALINGO_DIR ]; then
        git clone https://github.com/lozzalingo/lozzalingo-framework.git $LOZZALINGO_DIR
    else
        cd $LOZZALINGO_DIR && git pull
    fi
    # Remove old symlink if present, copy real directory for Docker build context
    rm -f $REMOTE_DIR/lozzalingo
    cp -r $LOZZALINGO_DIR/lozzalingo $REMOTE_DIR/lozzalingo
"

# Build and start containers
echo "[Deploy] Building and starting containers..."
$SSH_CMD "cd $REMOTE_DIR && docker compose up -d --build"

# Verify
echo "[Deploy] Verifying..."
sleep 5
$SSH_CMD "docker compose -f $REMOTE_DIR/docker-compose.yml ps"

echo "[Deploy] Done! Check https://<DOMAIN>/health"
