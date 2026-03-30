# WAN Bot - Installation Guide

**Quick Setup**: 10 minutes

---

## Prerequisites

- Python 3.8+
- Discord.py 2.0+
- Flask
- Git

---

## Step 1: Clone Repository

```bash
git clone <repo-url>
cd wan-bot
```

---

## Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

If `requirements.txt` doesn't exist, install manually:

```bash
pip install discord.py flask python-dotenv
```

---

## Step 3: Create Directories

```bash
mkdir -p ./data/watch_party
mkdir -p ./data/music
mkdir -p ./uploads/watch_party
mkdir -p ./logs
```

---

## Step 4: Setup Environment

Create `.env` file in project root:

```env
# Discord
DISCORD_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_guild_id

# Database
DB_PATH=./data
UPLOAD_PATH=./uploads/watch_party
MAX_UPLOAD_MB=10240

# Web Server
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False

# Features
ENABLE_WATCH_PARTY=True
ENABLE_MUSIC=True
ENABLE_CHAT=True
ENABLE_REQUESTS=True
ENABLE_SCHEDULING=True
```

---

## Step 5: Create bot.py

```python
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

bot = commands.Bot(command_prefix='/', intents=discord.Intents.all())

async def load_cogs():
    """Load all cogs"""
    cogs = [
        'cogs.music',
        'cogs.watch_party_enhanced',
        'cogs.roles',
        'cogs.automation',
        'cogs.leveling'
    ]
    
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"✅ Loaded {cog}")
        except Exception as e:
            print(f"❌ Failed to load {cog}: {e}")

@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}")
    await load_cogs()

# Run bot
bot.run(os.getenv('DISCORD_TOKEN'))
```

---

## Step 6: Create app.py (Flask Server)

```python
import os
from flask import Flask
from dotenv import load_dotenv
from watch_party_premium_api import register_premium_routes
from watch_party_api import register_watch_routes

load_dotenv()

app = Flask(__name__)

# Register routes
register_premium_routes(app)
register_watch_routes(app)

@app.route('/')
def index():
    return {'status': 'WAN Bot API Running'}

if __name__ == '__main__':
    app.run(
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG', 'False') == 'True'
    )
```

---

## Step 7: Start Services

### Terminal 1: Start Discord Bot

```bash
python bot.py
```

You should see:
```
✅ Bot logged in as WAN Bot#1234
✅ Loaded cogs.music
✅ Loaded cogs.watch_party_enhanced
✅ Loaded cogs.roles
✅ Loaded cogs.automation
✅ Loaded cogs.leveling
```

### Terminal 2: Start Flask Server

```bash
python app.py
```

You should see:
```
 * Running on http://0.0.0.0:5000
```

---

## Step 8: Verify Installation

### Check Bot is Online

In Discord, type:
```
/watchparty
```

You should see a setup message.

### Check API is Running

```bash
curl http://localhost:5000/
```

Response:
```json
{"status": "WAN Bot API Running"}
```

### Check Endpoints

```bash
# Get movies
curl http://localhost:5000/api/watch/movies/123456

# Get chat history
curl http://localhost:5000/api/watch/chat/room_uuid
```

---

## Step 9: Test Features

### Test Chat

1. Open watch party in browser
2. Type message
3. Click send
4. Message appears with your role color

### Test Requests

1. Click request button (⏭ Skip)
2. Owner sees request
3. Owner clicks approve/reject
4. Request updates

### Test Schedule

1. Click "📅 Schedule"
2. Select future date/time
3. Click set
4. Schedule displays

### Test Discord

1. Upload movie
2. Check Discord channel
3. See announcement
4. Click watch link
5. Owner gets approval request
6. React to approve/deny

---

## Troubleshooting

### Bot Won't Start

**Error**: `discord.errors.LoginFailure`

**Solution**: Check `DISCORD_TOKEN` in `.env`

```bash
# Get token from Discord Developer Portal
# https://discord.com/developers/applications
```

### Flask Won't Start

**Error**: `Address already in use`

**Solution**: Change port in `.env`

```env
FLASK_PORT=5001
```

### Directories Not Found

**Error**: `FileNotFoundError: [Errno 2] No such file or directory`

**Solution**: Create directories

```bash
mkdir -p ./data/watch_party
mkdir -p ./data/music
mkdir -p ./uploads/watch_party
```

### Permission Denied

**Error**: `PermissionError`

**Solution**: Fix permissions

```bash
chmod 755 ./data
chmod 755 ./data/watch_party
chmod 755 ./data/music
chmod 755 ./uploads
chmod 755 ./uploads/watch_party
```

### Cog Won't Load

**Error**: `discord.ext.commands.errors.ExtensionNotFound`

**Solution**: Check cog file exists

```bash
ls -la cogs/
# Should see: music.py, watch_party_enhanced.py, etc.
```

---

## File Structure After Installation

```
wan-bot/
├── bot.py                          ✅ Created
├── app.py                          ✅ Created
├── .env                            ✅ Created
├── requirements.txt                ✅ Exists
├── WAN_BOT_COMPLETE_DOCUMENTATION.md ✅ Reference
├── INSTALLATION.md                 ✅ This file
│
├── cogs/
│   ├── music.py                    ✅ Exists
│   ├── watch_party_enhanced.py     ✅ Exists
│   ├── roles.py                    ✅ Exists
│   ├── automation.py               ✅ Exists
│   └── leveling.py                 ✅ Exists
│
├── templates/
│   ├── watch_party_premium.html    ✅ Exists
│   └── watch_party.html            ✅ Exists
│
├── watch_party_enhanced.py         ✅ Exists
├── watch_party_premium_api.py      ✅ Exists
├── watch_party_api.py              ✅ Exists
├── watch_party_movies_db.py        ✅ Exists
├── watch_party_upload.py           ✅ Exists
├── music_db.py                     ✅ Exists
│
├── data/                           ✅ Created
│   ├── watch_party/
│   │   ├── movies.json             (auto-created)
│   │   ├── movie_rooms.json        (auto-created)
│   │   ├── enhanced.json           (auto-created)
│   │   ├── chat.json               (auto-created)
│   │   └── requests.json           (auto-created)
│   └── music/
│       ├── queues.json             (auto-created)
│       ├── settings.json           (auto-created)
│       └── history.json            (auto-created)
│
├── uploads/
│   └── watch_party/                ✅ Created
│
└── logs/
    └── watch_party.log             (auto-created)
```

---

## Next Steps

1. ✅ Installation complete
2. 📖 Read `WAN_BOT_COMPLETE_DOCUMENTATION.md` for full documentation
3. 🎮 Test all features
4. 🚀 Deploy to production

---

## Support

For issues, check:
1. `WAN_BOT_COMPLETE_DOCUMENTATION.md` - Troubleshooting section
2. `./logs/watch_party.log` - Error logs
3. Console output - Error messages

---

**Installation Complete!** 🎉

Your WAN Bot is now ready to use.
