#!/bin/bash
# ==========================================
# 🚀 AUTONOMOUS ORCHESTRATOR - UNIVERSAL INSTALLER
# ==========================================
# Commander: Garrett Carroll
# Status:    Production Ready (Delegates to Bootloader)
# ==========================================

set -e

# 1. Environment Check
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed."
    exit 1
fi

# 2. Clone/Enter Repository
REPO_URL="https://github.com/Garrettc123/autonomous-orchestrator-core.git"
DIR_NAME="autonomous-orchestrator-core"

if [ -d "$DIR_NAME" ]; then
    echo "📂 Entering existing directory..."
    cd "$DIR_NAME"
    echo "🔄 Syncing latest protocols..."
    git pull
elif [ -d ".git" ] && grep -q "Garrettc123/autonomous-orchestrator-core" .git/config; then
    echo "✅ Already inside repository."
    git pull
else
    echo "⬇️  Cloning secure repository..."
    git clone "$REPO_URL"
    cd "$DIR_NAME"
fi

# 3. Handoff to Universal Bootloader
# This ensures we always use the latest logic in boot.sh
chmod +x boot.sh
exec ./boot.sh
