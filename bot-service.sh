#!/bin/bash

# Discord Bot Service Manager
# Keeps your bot running 24/7 automatically

PLIST_FILE="com.discord.wanbot.plist"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_FILE"
BOT_DIR="$(pwd)"

case "$1" in
    install)
        echo "📦 Installing bot as a system service..."
        
        # Create LaunchAgents directory if it doesn't exist
        mkdir -p "$HOME/Library/LaunchAgents"
        
        # Copy plist file
        cp "$PLIST_FILE" "$PLIST_PATH"
        
        # Load the service
        launchctl load "$PLIST_PATH"
        
        echo "✅ Bot service installed!"
        echo "✅ Bot will now start automatically on login"
        echo "✅ Bot will restart automatically if it crashes"
        echo ""
        echo "Use './bot-service.sh status' to check if it's running"
        ;;
        
    uninstall)
        echo "🗑️  Uninstalling bot service..."
        
        # Unload the service
        launchctl unload "$PLIST_PATH" 2>/dev/null
        
        # Remove plist file
        rm -f "$PLIST_PATH"
        
        echo "✅ Bot service uninstalled"
        ;;
        
    start)
        echo "▶️  Starting bot service..."
        launchctl load "$PLIST_PATH"
        echo "✅ Bot service started"
        ;;
        
    stop)
        echo "⏹️  Stopping bot service..."
        launchctl unload "$PLIST_PATH"
        echo "✅ Bot service stopped"
        ;;
        
    restart)
        echo "🔄 Restarting bot service..."
        launchctl unload "$PLIST_PATH" 2>/dev/null
        sleep 2
        launchctl load "$PLIST_PATH"
        echo "✅ Bot service restarted"
        ;;
        
    status)
        echo "📊 Bot Service Status:"
        echo ""
        
        if launchctl list | grep -q "com.discord.wanbot"; then
            echo "✅ Service is RUNNING"
            echo ""
            echo "Process info:"
            ps aux | grep "python bot.py" | grep -v grep
            echo ""
            echo "Recent logs (last 10 lines):"
            tail -10 bot.log 2>/dev/null || echo "No logs yet"
        else
            echo "❌ Service is NOT running"
            echo ""
            echo "To start: ./bot-service.sh install"
        fi
        ;;
        
    logs)
        echo "📋 Bot Logs (last 50 lines):"
        echo "Press Ctrl+C to stop"
        echo ""
        tail -f bot.log
        ;;
        
    *)
        echo "🤖 Discord Bot Service Manager"
        echo ""
        echo "Usage: ./bot-service.sh [command]"
        echo ""
        echo "Commands:"
        echo "  install   - Install bot as a system service (auto-start on login)"
        echo "  uninstall - Remove bot service"
        echo "  start     - Start the bot service"
        echo "  stop      - Stop the bot service"
        echo "  restart   - Restart the bot service"
        echo "  status    - Check if bot is running"
        echo "  logs      - View bot logs in real-time"
        echo ""
        echo "Examples:"
        echo "  ./bot-service.sh install   # Set up auto-start"
        echo "  ./bot-service.sh status    # Check if running"
        echo "  ./bot-service.sh logs      # View logs"
        echo "  ./bot-service.sh restart   # Restart bot"
        ;;
esac
