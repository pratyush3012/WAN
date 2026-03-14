#!/bin/bash

# WAN Bot - Start with Web Dashboard
# This script starts the bot and automatically opens the web dashboard

echo "🤖 Starting WAN Bot with Web Dashboard..."
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed!"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Check if requirements are installed
echo "📦 Checking dependencies..."
python3 -c "import flask" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Flask not installed. Installing web dashboard dependencies..."
    pip3 install flask flask-cors
fi

# Start the bot in background
echo "🚀 Starting bot..."
python3 bot.py &
BOT_PID=$!

# Wait for web dashboard to start
echo "⏳ Waiting for web dashboard to start..."
sleep 5

# Check if bot is running
if ps -p $BOT_PID > /dev/null; then
    echo "✅ Bot started successfully!"
    echo ""
    echo "🌐 Web Dashboard is now running!"
    echo "📊 Access it at: http://localhost:5000"
    echo ""
    echo "Opening web dashboard in your browser..."
    
    # Open browser based on OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        open http://localhost:5000
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        xdg-open http://localhost:5000 2>/dev/null || echo "Please open http://localhost:5000 in your browser"
    else
        echo "Please open http://localhost:5000 in your browser"
    fi
    
    echo ""
    echo "📝 Bot logs are being written to bot.log"
    echo "🛑 Press Ctrl+C to stop the bot"
    echo ""
    
    # Wait for bot process
    wait $BOT_PID
else
    echo "❌ Failed to start bot!"
    echo "Check bot.log for errors"
    exit 1
fi
