#!/bin/bash
# AUTONOMOUS SYSTEM BOOTLOADER v1.3
# "No Lies" Production Setup + Persistent Secrets + Fixes

set -e

echo "██████╗  ██████╗  ██████╗ ████████╗"
echo "██╔══██╗██╔═══██╗██╔═══██╗╚══██╔══╝"
echo "██████╔╝██║   ██║██║   ██║   ██║   "
echo "██╔══██╗██║   ██║██║   ██║   ██║   "
echo "██████╔╝╚██████╔╝╚██████╔╝   ██║   "
echo "╚═════╝  ╚═════╝  ╚═════╝    ╚═╝   "

# 1. Directory Check
if [ ! -f "orchestrator.py" ]; then
    echo "❌ ERROR: orchestrator.py not found in current directory."
    echo "   Please ensure you have cloned the repo and entered the directory:"
    echo "   > git clone https://github.com/Garrettc123/autonomous-orchestrator-core"
    echo "   > cd autonomous-orchestrator-core"
    exit 1
fi

# 2. Package Initialization
touch security/__init__.py
touch integrations/__init__.py
touch modules/__init__.py

# 3. Virtual Environment
if [ ! -d "venv" ]; then
    echo "📦 Creating isolated python environment..."
    python3 -m venv venv
fi
source venv/bin/activate

# 4. Dependencies
echo "⬇️  Installing production dependencies..."
pip install -r requirements.txt --quiet

# 5. Load Persistent Secrets
if [ -f "secrets.env" ]; then
    echo "🔓 Loading keys from secrets.env..."
    set -a
    source secrets.env
    set +a
fi

# 6. Security Input (Mandatory & Persistent)
if [ -z "$COMMANDER_ONE_KEY" ]; then
    echo "🔑 ENTER COMMANDER ONE KEY (Required):"
    read -s COMMANDER_ONE_KEY
    export COMMANDER_ONE_KEY
fi

# 7. Optional Real Integration (Persistent)
# Only ask if keys are missing from environment AND secrets.env
if [ -z "$LINEAR_API_KEY" ] && [ -z "$SLACK_BOT_TOKEN" ]; then
    echo ""
    echo "🔌 OPTIONAL: Connect Real Integrations? (y/n)"
    read -r CONNECT_REAL
    if [[ "$CONNECT_REAL" =~ ^[Yy]$ ]]; then
        echo "   Enter Linear API Key (Press Enter to skip):"
        read -r LIN_KEY
        if [ ! -z "$LIN_KEY" ]; then 
            export LINEAR_API_KEY="$LIN_KEY"
            echo "export LINEAR_API_KEY='$LIN_KEY'" >> secrets.env
            echo "   ✅ Linear Key saved to secrets.env"
        fi
        
        echo "   Enter Slack Bot Token (Press Enter to skip):"
        read -r SL_KEY
        if [ ! -z "$SL_KEY" ]; then 
            export SLACK_BOT_TOKEN="$SL_KEY"
            echo "export SLACK_BOT_TOKEN='$SL_KEY'" >> secrets.env
            echo "   ✅ Slack Token saved to secrets.env"
        fi
    fi
fi

# 8. Execute
echo "🚀 Booting Orchestrator..."
python orchestrator.py
