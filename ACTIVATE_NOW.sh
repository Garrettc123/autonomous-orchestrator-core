#!/bin/bash
# SYNCHRONICITY ACTIVATION SCRIPT
# Run this to start the entire 332-system harmonious flow

echo "🌈 ACTIVATING 332-SYSTEM SYNCHRONICITY..."

# Set environment variables
export GITHUB_TOKEN=${GITHUB_TOKEN}
export STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
export INITIAL_CAPITAL=100000
export HARMONY_THRESHOLD=0.88

echo "✅ Environment configured"

# Install dependencies
pip install -q fastapi uvicorn requests stripe pyyaml

echo "📦 Dependencies installed"

# Start the unified system runner
python3 run_all_systems.py &

echo "🚀 All 332 systems are now LIVE"
echo "💰 Prosperity Flow is ACTIVE"
echo "🎵 Synchronic Bridge is RESONATING"
echo ""
echo "Monitor at: http://localhost:8000/status"
echo "Prosperity: http://localhost:8000/prosperity"
