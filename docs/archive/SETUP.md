# 🚀 Detailed Setup Guide

## Step-by-Step Installation

### 1. System Requirements

- Python 3.10 or higher
- pip (Python package manager)
- FFmpeg (for music playback)
- 2GB RAM minimum
- Stable internet connection

### 2. Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Install FFmpeg

#### Windows
1. Download from https://ffmpeg.org/download.html
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to PATH environment variable

#### macOS
```bash
brew install ffmpeg
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install ffmpeg
```

Verify installation:
```bash
ffmpeg -version
```

### 4. Create Discord Bot

1. Go to https://discord.com/developers/applications
2. Click "New Application"
3. Give it a name (e.g., "Gaming Bot")
4. Go to "Bot" tab
5. Click "Add Bot"
6. Under "Privileged Gateway Intents", enable:
   - ✅ Presence Intent
   - ✅ Server Members Intent
   - ✅ Message Content Intent
7. Click "Reset Token" and copy the token
8. Save this token securely

### 5. Get Your Discord User ID

1. Enable Developer Mode in Discord:
   - User Settings → Advanced → Developer Mode (ON)
2. Right-click your username
3. Click "Copy ID"
4. This is your OWNER_ID

### 6. Get API Keys (Optional but Recommended)

#### Google Translate API
1. Go to https://console.cloud.google.com/
2. Create a new project
3. Enable "Cloud Translation API"
4. Create credentials (API Key)
5. Copy the API key

#### YouTube Data API
1. In Google Cloud Console
2. Enable "YouTube Data API v3"
3. Use the same API key or create a new one

### 7. Configure Environment Variables

Create `.env` file in project root:

```env
# Required
DISCORD_TOKEN=your_bot_token_here
OWNER_ID=your_discord_user_id

# Optional (but recommended for full features)
GOOGLE_TRANSLATE_API_KEY=your_google_api_key
YOUTUBE_API_KEY=your_youtube_api_key

# Database (default is fine)
DATABASE_URL=sqlite:///bot.db

# Logging
LOG_LEVEL=INFO
```

### 8. Invite Bot to Your Server

1. Go to Discord Developer Portal → Your Application → OAuth2 → URL Generator
2. Select scopes:
   - ✅ bot
   - ✅ applications.commands
3. Select bot permissions:
   - ✅ Administrator (or select specific permissions)
4. Copy the generated URL
5. Open URL in browser and invite bot to your server

Minimum required permissions:
- Manage Roles
- Manage Channels
- Kick Members
- Ban Members
- Manage Messages
- Read Messages/View Channels
- Send Messages
- Embed Links
- Attach Files
- Read Message History
- Add Reactions
- Connect (voice)
- Speak (voice)
- Use Slash Commands

### 9. Initialize Database

The database will be created automatically on first run, but you can initialize it manually:

```bash
python -c "import asyncio; from utils.database import Database; asyncio.run(Database().init_db())"
```

### 10. Run the Bot

```bash
python bot.py
```

You should see:
```
INFO - Loaded cogs.moderation
INFO - Loaded cogs.music
INFO - Loaded cogs.automation
INFO - Loaded cogs.translation
INFO - Loaded cogs.youtube
INFO - Loaded cogs.gaming
INFO - Loaded cogs.admin
INFO - Loaded cogs.logging
INFO - YourBotName#1234 is now online!
INFO - Connected to X guilds
INFO - Slash commands synced
```

### 11. Initial Server Setup

In your Discord server, run these commands:

```
/setlogchannel #logs
/setwelcome #welcome
/setautorole @Member
/setdjrole @DJ
```

### 12. Test the Bot

Try these commands:
- `/config` - View configuration
- `/play never gonna give you up` - Test music
- `/rank` - Test XP system
- Type a message and react with 🌐 - Test translation

## 🔧 Advanced Configuration

### Using PostgreSQL Instead of SQLite

1. Install PostgreSQL
2. Create a database
3. Update `.env`:
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname
```
4. Install additional dependency:
```bash
pip install asyncpg
```

### Running as a Service (Linux)

Create `/etc/systemd/system/discord-bot.service`:

```ini
[Unit]
Description=Discord Gaming Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/bot
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable discord-bot
sudo systemctl start discord-bot
sudo systemctl status discord-bot
```

### Using PM2 (Node.js Process Manager)

```bash
npm install -g pm2
pm2 start bot.py --name discord-bot --interpreter python3
pm2 save
pm2 startup
```

### Docker Deployment

Create `Dockerfile`:
```dockerfile
FROM python:3.10-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
```

Build and run:
```bash
docker build -t discord-bot .
docker run -d --name discord-bot --env-file .env discord-bot
```

### Railway Deployment

1. Create account on https://railway.app
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Add environment variables in Railway dashboard
5. Railway will auto-detect Python and deploy

### Heroku Deployment

1. Create `Procfile`:
```
worker: python bot.py
```

2. Create `runtime.txt`:
```
python-3.10.12
```

3. Deploy:
```bash
heroku create your-bot-name
heroku config:set DISCORD_TOKEN=your_token
heroku config:set OWNER_ID=your_id
git push heroku main
heroku ps:scale worker=1
```

## 🐛 Common Issues

### "Module not found" error
```bash
pip install -r requirements.txt --upgrade
```

### "FFmpeg not found"
- Verify FFmpeg is in PATH: `ffmpeg -version`
- Restart terminal after installing FFmpeg

### "Privileged intent not enabled"
- Enable intents in Discord Developer Portal
- Restart bot

### Commands not appearing
- Wait 5-10 minutes for Discord to sync
- Kick and re-invite bot with correct permissions
- Check bot has `applications.commands` scope

### Music playback issues
- Ensure bot has Connect and Speak permissions
- Check FFmpeg installation
- Try updating yt-dlp: `pip install -U yt-dlp`

### Database locked error
- Close any other processes using the database
- Delete `bot.db` and restart (will reset all data)

## 📊 Monitoring

### View Logs
```bash
tail -f bot.log
```

### Check Bot Status
```bash
# If using systemd
sudo systemctl status discord-bot

# If using PM2
pm2 status
pm2 logs discord-bot
```

## 🔄 Updating the Bot

```bash
git pull origin main
pip install -r requirements.txt --upgrade
# Restart bot
```

## 🎯 Next Steps

1. Customize welcome messages
2. Set up reaction roles
3. Configure YouTube notifications
4. Create custom announcements
5. Set up XP role rewards
6. Configure anti-spam settings

For more help, check README.md or open an issue on GitHub.
