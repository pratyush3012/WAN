#!/bin/bash

# Create a proper macOS application bundle
# This creates a standalone app that can be moved to Applications folder

echo "🔨 Creating WAN Bot Application..."
echo ""

APP_NAME="WAN Bot"
APP_DIR="$APP_NAME.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

# Clean up old app if exists
if [ -d "$APP_DIR" ]; then
    echo "Removing old application..."
    rm -rf "$APP_DIR"
fi

# Create directory structure
echo "Creating app structure..."
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

# Copy all bot files to Resources
echo "Copying bot files..."
cp -r bot.py web_dashboard_enhanced.py cogs utils templates static requirements.txt .env.example "$RESOURCES_DIR/"
cp -r roblox_game_scripts docs "$RESOURCES_DIR/" 2>/dev/null || true

# Create the main executable script
cat > "$MACOS_DIR/$APP_NAME" << 'SCRIPT_EOF'
#!/bin/bash

# Get the Resources directory
RESOURCES_DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
cd "$RESOURCES_DIR"

# Check if .env exists, if not create from example
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
    fi
fi

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate venv and install dependencies
source venv/bin/activate
pip install -r requirements.txt --quiet 2>/dev/null

# Start the bot in background
python3 bot.py &
BOT_PID=$!

# Wait a moment for bot to start
sleep 3

# Open web dashboard in default browser
open "http://localhost:5000"

# Show notification
osascript -e 'display notification "Bot is running! Web dashboard opened." with title "WAN Bot Started"'

# Keep the process alive
wait $BOT_PID
SCRIPT_EOF

chmod +x "$MACOS_DIR/$APP_NAME"

# Create Info.plist
cat > "$CONTENTS_DIR/Info.plist" << 'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>WAN Bot</string>
    <key>CFBundleIdentifier</key>
    <string>com.wanbot.discord</string>
    <key>CFBundleName</key>
    <string>WAN Bot</string>
    <key>CFBundleDisplayName</key>
    <string>WAN Bot</string>
    <key>CFBundleVersion</key>
    <string>2.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>WBOT</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
PLIST_EOF

# Create a simple icon (text-based)
# You can replace this with a proper .icns file later
cat > "$RESOURCES_DIR/icon.txt" << 'ICON_EOF'
🤖 WAN Bot
ICON_EOF

echo ""
echo "✅ Application created successfully!"
echo ""
echo "📦 Location: $APP_DIR"
echo ""
echo "To use:"
echo "  1. Double-click '$APP_DIR' to test"
echo "  2. Or drag to Applications folder"
echo "  3. Open from Applications"
echo ""
echo "The app will:"
echo "  • Start the Discord bot"
echo "  • Open web dashboard automatically"
echo "  • Run in the background"
echo ""
