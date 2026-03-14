#!/bin/bash

echo "🤖 Starting Discord Bot..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please run ./setup.sh first"
    exit 1
fi

# Check if venv exists
if [ ! -d venv ]; then
    echo "❌ Error: Virtual environment not found!"
    echo "Please run: python3 -m venv venv"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Set SSL certificate path (fixes SSL verification errors)
export SSL_CERT_FILE=$(python3 -c "import certifi; print(certifi.where())")
export REQUESTS_CA_BUNDLE=$(python3 -c "import certifi; print(certifi.where())")

# Check if dependencies are installed
python3 -c "import discord" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Error: Dependencies not installed!"
    echo "Please run: pip install -r requirements.txt"
    exit 1
fi

# Run the bot
echo "✅ Starting bot..."
echo "Press Ctrl+C to stop"
echo ""

python3 bot.py
