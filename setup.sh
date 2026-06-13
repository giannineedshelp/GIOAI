#!/bin/bash
# GIOAI Discord Bot Setup Script
# Run: bash setup.sh

set -e

echo "================================"
echo "  GIOAI Discord Bot Setup"
echo "================================"

# Create .env from example if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env from .env.example"
    echo "⚠️  Edit .env with your settings before running!"
else
    echo "✅ .env already exists"
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt 2>/dev/null || pip3 install -r requirements.txt 2>/dev/null

# Install system dependencies for playback/automation
if command -v pkg &> /dev/null; then
    echo "📱 Termux detected - installing system packages..."
    pkg install -y python rust binutils 2>/dev/null || true
fi

echo ""
echo "================================"
echo "  Setup Complete!"
echo "================================"
echo ""
echo "To run the bot:"
echo "  python GIOAI.py"
echo ""
echo "Or use the launcher:"
echo "  python launcher.py"
echo ""

