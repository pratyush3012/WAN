#!/bin/bash

echo "🚀 WAN Bot - Quick Start Script"
echo "================================"
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed!"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

echo ""
echo "🔧 Activating virtual environment..."
source venv/bin/activate

echo ""
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✅ All dependencies installed!"
echo ""
echo "🎮 Starting bot in Demo Mode..."
echo "   (Using realistic sample data - no game access needed)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start the bot
python3 bot.py
