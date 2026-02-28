#!/bin/bash
# =============================================================================
# Lozzalingo Starter Template - Run Script
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}"
echo "=========================================="
echo "  Lozzalingo Starter Template"
echo "=========================================="
echo -e "${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -q -r requirements.txt

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}Note: Edit .env with your configuration${NC}"
fi

# Create databases directory
mkdir -p databases

echo ""
echo -e "${GREEN}=========================================="
echo "  Starting server..."
echo "==========================================${NC}"
echo ""
echo "  Homepage:      http://localhost:5000"
echo "  Admin Panel:   http://localhost:5000/admin"
echo "  Create Admin:  http://localhost:5000/admin/create-admin"
echo ""
echo -e "${YELLOW}  First time? Visit /admin/create-admin to set up your admin account${NC}"
echo ""

# Run the app
python main.py
