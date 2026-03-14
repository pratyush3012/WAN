# 🤖 WAN Discord Bot - Complete Guide

## 🎉 Quick Start

### Launch the Bot (macOS)
Double-click `WAN Bot.app` to start everything automatically!

Or manually:
```bash
./start_bot.sh
```

The bot will:
- ✅ Start Discord bot
- ✅ Launch web dashboard at http://localhost:5000
- ✅ Load all features and commands

## 🎯 Features

### 🏅 Badge System
Automatic role identification with visual badges:
- 👑 Owner, ⚡ Admin, 🛡️ Manager, 🔨 Moderator, 💚 Helper
- ✅ Member, ⭐ VIP, 💎 Booster, ✓ Verified

**Commands:**
```
/badge                  - View your badge
/badges                 - View all badges
/assign-badge-role      - Create badge roles (Admin)
/auto-assign-badges     - Auto-assign to all (Admin)
```

### 🎮 Roblox Integration (Demo Mode)
Track game stats with realistic sample data:
- ⏱️ Playtime, 💰 Coins, ⚔️ Kills, 💀 Deaths, ⭐ Level

**Commands:**
```
/roblox-link <username>     - Link Roblox account
/roblox-stats [@user]       - View player stats
/roblox-leaderboard <cat>   - View leaderboards
/clan-stats                 - Clan overview (Admin)
/roblox-sync-bloxlink       - Auto-link via Bloxlink (Admin)
```

### 🌐 Web Dashboard
Beautiful web interface with:
- 📊 Server overview
- 🎮 Roblox stats & leaderboards
- 👥 Member management
- 📈 Real-time analytics

**Access:**
```
/web                - Open dashboard
/web-admin          - Admin panel (Admin)
```

### 💰 Economy System
```
/daily              - Daily reward
/work               - Work for coins
/balance [@user]    - Check balance
/give @user <amt>   - Give coins
/leaderboard-coins  - Richest users
```

### 🎮 Gaming & Leveling
```
/rank [@user]       - View rank card
/leaderboard        - XP leaderboard
```

### 🛡️ Moderation
```
/kick @user         - Kick member
/ban @user          - Ban member
/timeout @user      - Timeout member
/warn @user         - Warn member
/clear <amount>     - Clear messages
```

### 🎉 Fun & Social
```
/marry @user        - Propose marriage
/adopt              - Adopt a pet
/mypet              - View your pet
/achievements       - View achievements
```

### 🎵 Music
```
/play <song>        - Play music
/queue              - View queue
/skip               - Skip song
/volume <0-100>     - Set volume
```

### 🎫 Tickets
```
/ticket create      - Create ticket
/ticket close       - Close ticket
```

### 🔧 Utility
```
/serverinfo         - Server info
/userinfo [@user]   - User info
/avatar [@user]     - View avatar
/poll <q> <opts>    - Create poll
/remind <time>      - Set reminder
```

## ⚙️ Configuration

### Required Setup
1. Add your Discord bot token to `.env`:
   ```env
   DISCORD_TOKEN=your_token_here
   ```

2. Start the bot:
   ```bash
   ./start_bot.sh
   ```

### Optional: Real Roblox Data
To connect to actual game data, add to `.env`:
```env
ROBLOX_API_KEY=your_api_key
ROBLOX_UNIVERSE_ID=your_universe_id
ROBLOX_PLACE_ID=your_place_id
```

See `docs/ROBLOX_SETUP.md` for detailed instructions.

## 🚀 First Time Setup

### 1. Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Bot
Edit `.env` and add your Discord token.

### 3. Start Bot
```bash
./start_bot.sh
```

### 4. Set Up Badges (in Discord)
```
/assign-badge-role
/auto-assign-badges
```

### 5. Test Features
```
/badge
/roblox-link TestUser
/web
```

## 📊 Demo Mode

The bot runs in demo mode by default, using realistic sample data for Roblox features. This lets you test everything without needing access to a Roblox game.

**Demo features:**
- ✅ Realistic player stats (not zeros!)
- ✅ Working leaderboards
- ✅ Full web dashboard
- ✅ All commands functional

## 🌐 Web Dashboard

Access at: http://localhost:5000

Or use `/web` command in Discord for secure access link.

**Features:**
- 📊 Clan statistics
- 🏆 Interactive leaderboards
- 👥 Member list with avatars
- 📈 Real-time updates
- 🎨 Beautiful UI

## 🐛 Troubleshooting

### Bot won't start?
```bash
# Check Python version (need 3.8+)
python3 --version

# Reinstall dependencies
pip install -r requirements.txt

# Check logs
tail -f bot.log
```

### Commands not showing?
- Wait 1-2 minutes after bot starts
- Check bot has proper permissions
- Try `/help` to see available commands

### Web dashboard not loading?
```bash
# Check if port 5000 is available
lsof -i :5000

# Try different port in .env
DASHBOARD_PORT=5001
```

## 📚 Documentation

- `docs/ROBLOX_SETUP.md` - Connect to real Roblox game
- `docs/BADGE_GUIDE.md` - Badge system details
- `docs/COMMANDS.md` - Complete command list

## 🎯 Support

- Check bot logs: `tail -f bot.log`
- Review error messages in Discord
- Verify `.env` configuration
- Ensure bot has proper permissions

## ✨ Features Summary

✅ Badge system for role identification
✅ Roblox integration with demo mode
✅ Web dashboard with full features
✅ Economy and leveling system
✅ Moderation tools
✅ Music player
✅ Ticket system
✅ Fun commands
✅ And much more!

---

**Version:** 2.0.0
**Status:** Production Ready
**Last Updated:** 2024

Made with ❤️ for Discord communities
