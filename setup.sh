#!/bin/bash

echo "🚀 Discord Bot Setup Script"
echo "=============================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if .env exists
if [ -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file already exists${NC}"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing .env file"
    else
        rm .env
    fi
fi

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${GREEN}📝 Creating .env file...${NC}"
    
    echo "Please enter your Discord Bot Token:"
    echo "(Get it from: https://discord.com/developers/applications)"
    read -p "DISCORD_TOKEN: " discord_token
    
    echo ""
    echo "Please enter your Discord User ID:"
    echo "(Enable Developer Mode in Discord, right-click your name, Copy ID)"
    read -p "OWNER_ID: " owner_id
    
    echo ""
    echo "Optional: Google Translate API Key (press Enter to skip)"
    read -p "GOOGLE_TRANSLATE_API_KEY: " translate_key
    
    echo ""
    echo "Optional: YouTube API Key (press Enter to skip)"
    read -p "YOUTUBE_API_KEY: " youtube_key
    
    # Create .env file
    cat > .env << EOF
# Discord Bot Configuration
DISCORD_TOKEN=${discord_token}
OWNER_ID=${owner_id}

# Optional API Keys
GOOGLE_TRANSLATE_API_KEY=${translate_key}
YOUTUBE_API_KEY=${youtube_key}

# Database
DATABASE_URL=sqlite+aiosqlite:///bot.db

# Logging
LOG_LEVEL=INFO
EOF
    
    echo -e "${GREEN}✅ .env file created!${NC}"
else
    echo -e "${GREEN}✅ .env file exists${NC}"
fi

echo ""
echo -e "${GREEN}🔧 Initializing database...${NC}"

# Activate virtual environment and initialize database
source venv/bin/activate
python3 -c "import asyncio; from utils.database import Database; asyncio.run(Database().init_db())" 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Database initialized successfully!${NC}"
else
    echo -e "${RED}❌ Database initialization failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Make sure FFmpeg is installed: brew install ffmpeg"
echo "2. Invite your bot to Discord server"
echo "3. Run the bot: ./run.sh"
echo ""
echo "For detailed instructions, see SETUP.md"
