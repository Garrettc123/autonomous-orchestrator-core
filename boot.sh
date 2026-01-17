#!/bin/bash
# AUTONOMOUS SYSTEM BOOTLOADER v1.0
# "No Lies" Production Setup

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
    echo "   Current path: $(pwd)"
    echo "   Please ensure you have cloned the repo and entered the directory:"
    echo "   > git clone https://github.com/Garrettc123/autonomous-orchestrator-core"
    echo "   > cd autonomous-orchestrator-core"
    exit 1
fi

# 2. Package Initialization (Create __init__.py if missing)
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

# 5. Security Input
if [ -z "$COMMANDER_ONE_KEY" ]; then
    echo "🔑 ENTER COMMANDER ONE KEY (Input Hidden):"
    read -s COMMANDER_ONE_KEY
    export COMMANDER_ONE_KEY
fi

# 6. Execute
echo "🚀 Booting Orchestrator..."
python orchestrator.py
