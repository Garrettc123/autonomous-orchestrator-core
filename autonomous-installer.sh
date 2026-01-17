#!/bin/bash
# ==========================================
# 🚀 AUTONOMOUS ORCHESTRATOR - UNIVERSAL INSTALLER
# ==========================================
# Commander: Garrett Carroll
# Clearance: Level 5 (Root)
# Status:    Production Ready
# ==========================================

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}"
echo "██████╗  ██████╗  ██████╗ ████████╗"
echo "██╔══██╗██╔═══██╗██╔═══██╗╚══██╔══╝"
echo "██████╔╝██║   ██║██║   ██║   ██║   "
echo "██╔══██╗██║   ██║██║   ██║   ██║   "
echo "██████╔╝╚██████╔╝╚██████╔╝   ██║   "
echo "╚═════╝  ╚═════╝  ╚═════╝    ╚═╝   "
echo "Autonomous Orchestrator Deployment Initiated..."
echo -e "${NC}"

# 1. Environment Check
echo "🔍 Checking environment..."
if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Git is not installed. Please install Git first.${NC}"
    exit 1
fi
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 is not installed. Please install Python3 first.${NC}"
    exit 1
fi

# 2. Clone Repository (if not already inside it)
REPO_URL="https://github.com/Garrettc123/autonomous-orchestrator-core.git"
DIR_NAME="autonomous-orchestrator-core"

if [ -d ".git" ] && grep -q "Garrettc123/autonomous-orchestrator-core" .git/config; then
    echo "✅ Already inside the correct repository."
else
    if [ -d "$DIR_NAME" ]; then
        echo "📂 Directory $DIR_NAME exists. Entering..."
        cd "$DIR_NAME"
        echo "🔄 Pulling latest protocols..."
        git pull
    else
        echo "⬇️  Cloning secure repository..."
        git clone "$REPO_URL"
        cd "$DIR_NAME"
    fi
fi

# 3. Setup Virtual Environment
if [ ! -d "venv" ]; then
    echo "📦 Creating isolated Python environment..."
    python3 -m venv venv
fi
source venv/bin/activate

# 4. Install Dependencies
echo "⬇️  Installing production dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet
else
    echo -e "${RED}❌ requirements.txt not found. Repository might be corrupt.${NC}"
    exit 1
fi

# 5. Verify Core Files
REQUIRED_FILES=("orchestrator.py" "security/one_key.py" "integrations/collaboration_mesh.py" "modules/market_intelligence.py")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ Critical file missing: $file${NC}"
        exit 1
    fi
done

# 6. Secure Key Injection
if [ -z "$COMMANDER_ONE_KEY" ]; then
    echo ""
    echo -e "${GREEN}🔐 SECURITY PROTOCOL: COMMANDER AUTHENTICATION${NC}"
    echo "Please enter your 256-bit Master Seed to unlock the enclave."
    echo -n "COMMANDER ONE KEY (Hidden): "
    read -s COMMANDER_ONE_KEY
    export COMMANDER_ONE_KEY
    echo ""
    echo "✅ Key stored in volatile memory."
fi

# 7. Launch
echo ""
echo -e "${GREEN}🚀 LAUNCHING ORCHESTRATOR IN PRODUCTION MODE...${NC}"
python orchestrator.py
