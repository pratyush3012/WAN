#!/bin/bash

# WAN Bot Startup Script
# This script handles everything needed to start the bot

set -e  # Exit on error

echo "🤖 WAN Discord Bot - Starting..."
echo "================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC}  $1"
}

print_info() {
    echo -e "${BLUE}ℹ️${NC}  $1"
}

# Check Python 3
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed!"
    echo "Please install Python 3.8 or higher from https://www.python.org/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
print_status "Python $PYTHON_VERSION found"

# Check if .env exists
if [ ! -f ".env" ]; then
    print_error ".env file not found!"
    echo ""
    echo "Creating .env from .env.example..."
    cp .env.example .env
    print_warning "Please edit .env and add your DISCORD_TOKEN"
    echo ""
    echo "Open .env in a text editor and add your bot token:"
    echo "DISCORD_TOKEN=your_token_here"
    echo ""
    exit 1
fi

# Check if Discord token is set
if grep -q "your_discord_bot_token_here" .env || ! grep -q "DISCORD_TOKEN=" .env; then
    print_error "Discord token not configured!"
    echo ""
    echo "Please edit .env and add your DISCORD_TOKEN"
    echo "DISCORD_TOKEN=your_actual_token_here"
    echo ""
    exit 1
fi

print_status "Configuration file found"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    print_info "Creating virtual environment..."
    python3 -m venv venv
    print_status "Virtual environment created"
else
    print_status "Virtual environment exists"
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_info "Upgrading pip..."
pip install --upgrade pip --quiet

# Install/update dependencies
print_info "Installing dependencies..."
pip install -r requirements.txt --quiet

print_status "All dependencies installed"

# Check if bot.py exists
if [ ! -f "bot.py" ]; then
    print_error "bot.py not found!"
    exit 1
fi

# Create logs directory
mkdir -p logs

# Clear old logs (keep last 5)
if [ -d "logs" ]; then
    ls -t logs/bot_*.log 2>/dev/null | tail -n +6 | xargs -r rm
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
print_status "Starting WAN Discord Bot..."
echo ""
print_info "Bot will start in a few seconds..."
print_info "Web Dashboard: http://localhost:5000"
print_info "Press Ctrl+C to stop the bot"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start the bot
python3 bot.py

# If bot exits, show message
echo ""
print_warning "Bot has stopped"
echo ""
