#!/bin/bash

# WAN Bot Test Script
# Tests all components before starting

echo "🧪 WAN Bot - Running Tests..."
echo "================================"
echo ""

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Test 1: Python syntax
echo "Test 1: Checking Python syntax..."
python3 -m py_compile bot.py web_dashboard_enhanced.py cogs/*.py utils/*.py 2>&1
if [ $? -eq 0 ]; then
    echo "✅ All Python files compile successfully"
else
    echo "❌ Syntax errors found"
    exit 1
fi
echo ""

# Test 2: Check required files
echo "Test 2: Checking required files..."
REQUIRED_FILES=(
    "bot.py"
    "web_dashboard_enhanced.py"
    ".env"
    "requirements.txt"
    "cogs/badges.py"
    "cogs/roblox.py"
    "cogs/webdashboard.py"
)

ALL_EXIST=true
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file exists"
    else
        echo "❌ $file missing"
        ALL_EXIST=false
    fi
done

if [ "$ALL_EXIST" = false ]; then
    echo ""
    echo "❌ Some required files are missing"
    exit 1
fi
echo ""

# Test 3: Check .env configuration
echo "Test 3: Checking configuration..."
if grep -q "DISCORD_TOKEN=" .env && ! grep -q "your_discord_bot_token_here" .env; then
    echo "✅ Discord token configured"
else
    echo "⚠️  Discord token not configured (add to .env)"
fi

if grep -q "DASHBOARD_URL=" .env; then
    echo "✅ Dashboard URL configured"
else
    echo "ℹ️  Dashboard URL using default"
fi
echo ""

# Test 4: Check dependencies (if venv exists)
if [ -d "venv" ]; then
    echo "Test 4: Checking dependencies..."
    if pip list | grep -q "discord.py"; then
        echo "✅ discord.py installed"
    else
        echo "⚠️  discord.py not installed (run: pip install -r requirements.txt)"
    fi
    
    if pip list | grep -q "flask"; then
        echo "✅ flask installed"
    else
        echo "⚠️  flask not installed (run: pip install -r requirements.txt)"
    fi
    echo ""
fi

# Test 5: Check cogs
echo "Test 5: Checking cogs..."
COG_COUNT=$(ls -1 cogs/*.py 2>/dev/null | wc -l)
echo "✅ Found $COG_COUNT cog files"
echo ""

# Test 6: Check documentation
echo "Test 6: Checking documentation..."
if [ -f "README.md" ]; then
    echo "✅ README.md exists"
fi
if [ -d "docs" ]; then
    DOC_COUNT=$(ls -1 docs/*.md 2>/dev/null | wc -l)
    echo "✅ Found $DOC_COUNT documentation files"
fi
echo ""

# Summary
echo "================================"
echo "✅ All tests passed!"
echo ""
echo "Ready to start the bot:"
echo "  ./start_bot.sh"
echo ""
echo "Or double-click: WAN Bot.app"
echo ""
