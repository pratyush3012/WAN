#!/bin/bash

# FFmpeg Installation Script for WAN Bot
# This script installs FFmpeg which is required for music playback

echo "🎵 Installing FFmpeg for WAN Bot Music Features"
echo "================================================"
echo ""

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "📱 Detected macOS"
    echo "Installing FFmpeg via Homebrew..."
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo "❌ Homebrew not found!"
        echo "Please install Homebrew first:"
        echo "/bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    
    brew install ffmpeg
    
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    echo "🐧 Detected Linux"
    
    # Check for package manager
    if command -v apt &> /dev/null; then
        echo "Installing FFmpeg via apt..."
        sudo apt update
        sudo apt install -y ffmpeg
    elif command -v yum &> /dev/null; then
        echo "Installing FFmpeg via yum..."
        sudo yum install -y ffmpeg
    elif command -v dnf &> /dev/null; then
        echo "Installing FFmpeg via dnf..."
        sudo dnf install -y ffmpeg
    elif command -v pacman &> /dev/null; then
        echo "Installing FFmpeg via pacman..."
        sudo pacman -S --noconfirm ffmpeg
    else
        echo "❌ Could not detect package manager"
        echo "Please install FFmpeg manually for your distribution"
        exit 1
    fi
    
else
    echo "❌ Unsupported OS: $OSTYPE"
    echo ""
    echo "For Windows:"
    echo "  1. Install Chocolatey: https://chocolatey.org/install"
    echo "  2. Run: choco install ffmpeg"
    echo ""
    echo "Or download from: https://ffmpeg.org/download.html"
    exit 1
fi

# Verify installation
echo ""
echo "🔍 Verifying FFmpeg installation..."
if command -v ffmpeg &> /dev/null; then
    echo "✅ FFmpeg installed successfully!"
    echo ""
    ffmpeg -version | head -n 1
    echo ""
    echo "🎉 You can now use music commands!"
    echo "Restart your bot: python3 bot.py"
else
    echo "❌ FFmpeg installation failed"
    echo "Please install manually: https://ffmpeg.org/download.html"
    exit 1
fi
