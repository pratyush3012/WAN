#!/bin/bash

# WAN Bot Installation Verification
# Checks everything is ready to run

echo "🔍 WAN Bot - Installation Verification"
echo "========================================"
echo ""

ERRORS=0
WARNINGS=0

# Check 1: Python
echo "Checking Python..."
if command -v python3 &> /dev/null; then
    VERSION=$(python3 --version)
    echo "✅ $VERSION"
else
    echo "❌ Python 3 not found"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check 2: Required files
echo "Checking required files..."
FILES=(
    "bot.py:Bot main file"
    "web_dashboard_enhanced.py:Web dashboard"
    ".env:Configuration"
    "requirements.txt:Dependencies"
    "start_bot.sh:Startup script"
    "WAN Bot.app:macOS app"
    "README.md:Documentation"
)

for item in "${FILES[@]}"; do
    IFS=':' read -r file desc <<< "$item"
    if [ -e "$file" ]; then
        echo "✅ $desc ($file)"
    else
        echo "❌ $desc missing ($file)"
        ERRORS=$((ERRORS + 1))
    fi
done
echo ""

# Check 3: Cogs
echo "Checking cogs..."
CRITICAL_COGS=(
    "cogs/badges.py:Badge system"
    "cogs/roblox.py:Roblox integration"
    "cogs/webdashboard.py:Web dashboard commands"
    "cogs/economy.py:Economy system"
    "cogs/moderation.py:Moderation tools"
)

for item in "${CRITICAL_COGS[@]}"; do
    IFS=':' read -r file desc <<< "$item"
    if [ -f "$file" ]; then
        echo "✅ $desc"
    else
        echo "❌ $desc missing"
        ERRORS=$((ERRORS + 1))
    fi
done
echo ""

# Check 4: Configuration
echo "Checking configuration..."
if [ -f ".env" ]; then
    if grep -q "DISCORD_TOKEN=" .env && ! grep -q "your_discord_bot_token_here" .env; then
        echo "✅ Discord token configured"
    else
        echo "⚠️  Discord token not set"
        WARNINGS=$((WARNINGS + 1))
    fi
    
    if grep -q "DASHBOARD_URL=" .env; then
        echo "✅ Dashboard URL configured"
    else
        echo "ℹ️  Dashboard URL using default"
    fi
else
    echo "❌ .env file missing"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check 5: Permissions
echo "Checking permissions..."
if [ -x "start_bot.sh" ]; then
    echo "✅ start_bot.sh is executable"
else
    echo "⚠️  start_bot.sh not executable (fixing...)"
    chmod +x start_bot.sh
    WARNINGS=$((WARNINGS + 1))
fi

if [ -x "WAN Bot.app/Contents/MacOS/WAN Bot" ]; then
    echo "✅ WAN Bot.app is executable"
else
    echo "⚠️  WAN Bot.app not executable (fixing...)"
    chmod +x "WAN Bot.app/Contents/MacOS/WAN Bot"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# Check 6: Python syntax
echo "Checking Python syntax..."
if python3 -m py_compile bot.py 2>/dev/null; then
    echo "✅ bot.py syntax valid"
else
    echo "❌ bot.py has syntax errors"
    ERRORS=$((ERRORS + 1))
fi

if python3 -m py_compile web_dashboard_enhanced.py 2>/dev/null; then
    echo "✅ web_dashboard_enhanced.py syntax valid"
else
    echo "❌ web_dashboard_enhanced.py has syntax errors"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Summary
echo "========================================"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "✅ Perfect! Everything is ready!"
    echo ""
    echo "Start the bot:"
    echo "  • Double-click: WAN Bot.app"
    echo "  • Or run: ./start_bot.sh"
    echo ""
elif [ $ERRORS -eq 0 ]; then
    echo "✅ Ready to run (with $WARNINGS warnings)"
    echo ""
    echo "Start the bot:"
    echo "  • Double-click: WAN Bot.app"
    echo "  • Or run: ./start_bot.sh"
    echo ""
else
    echo "❌ Found $ERRORS errors and $WARNINGS warnings"
    echo ""
    echo "Please fix the errors above before starting."
    echo ""
    exit 1
fi
