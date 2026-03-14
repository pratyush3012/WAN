# 🚀 WAN Bot - Quick Start Guide

## ✅ Current Status: RUNNING

Your bot is currently running with the web dashboard accessible at:
**http://localhost:5000**

## 🎯 What You Have Now

### 1. Discord Bot (90 Commands)
The bot is online in your Discord server with these features:
- Admin & Moderation tools
- Economy system
- Social features (profiles, pets)
- Role management
- Badge system
- Roblox integration (demo mode)
- Ticket system
- Birthday tracking

### 2. Web Dashboard
Access at **http://localhost:5000**
- Login: `admin` / `admin`
- View server statistics
- Manage Roblox leaderboards
- Export data
- Real-time updates

### 3. macOS Application
`WAN Bot.app` - Double-click to start everything automatically

## 🎮 Try These Commands in Discord

```
/web                    - Open web dashboard
/badge                  - View your badge
/badges                 - See all badges
/roblox-stats          - Your Roblox stats (demo)
/roblox-leaderboard    - Top players
/userinfo @user        - User information
/serverinfo            - Server statistics
/balance               - Check your coins
/daily                 - Claim daily reward
/adopt                 - Adopt a virtual pet
/profile               - View your profile
```

## 🌐 Web Dashboard Access

1. Open http://localhost:5000 in your browser
2. Login with `admin` / `admin`
3. Explore:
   - Server overview
   - Roblox leaderboards
   - Member statistics
   - Export data

## 📱 Using the macOS App

### To Start:
1. Find `WAN Bot.app` in Finder
2. Double-click the app
3. Wait 8-10 seconds
4. Dashboard opens automatically

### To Stop:
- Close the Terminal window
- Or run: `pkill -f "python.*bot.py"`

### To Move to Applications:
```bash
# Drag WAN Bot.app to Applications folder
# Or use Terminal:
cp -r "WAN Bot.app" /Applications/
```

## 🎨 Badge System

The bot automatically assigns badges based on roles:
- 👑 Owner
- ⚡ Admin
- 🛡️ Manager
- 🔨 Moderator
- 💚 Helper
- ✅ Member
- ⭐ VIP
- 💎 Booster
- ✓ Verified
- 👤 Guest

Use `/auto-assign-badges` to assign badges to all members.

## 🎮 Roblox Integration (Demo Mode)

Currently using realistic demo data because you don't own the game:
- Generates consistent stats per user
- Shows realistic levels, coins, kills
- Fully functional leaderboards
- Clan statistics

**Commands:**
- `/roblox-stats` - View your stats
- `/roblox-leaderboard playtime` - Top by playtime
- `/roblox-leaderboard coins` - Top by coins
- `/roblox-leaderboard kills` - Top by kills
- `/roblox-leaderboard kd` - Top by K/D ratio
- `/roblox-clan-stats` - Overall clan statistics

## 🔧 Configuration

Edit `.env` file to customize:
```bash
# Discord
DISCORD_TOKEN=your_token_here
OWNER_ID=your_discord_id

# Dashboard
DASHBOARD_PORT=5000
DASHBOARD_SECRET_KEY=change_this_in_production

# Roblox (optional - for real game)
# ROBLOX_API_KEY=your_api_key
# ROBLOX_UNIVERSE_ID=your_universe_id
# ROBLOX_PLACE_ID=your_place_id
```

## 📊 What's Working

✅ Bot online with 90 commands
✅ Web dashboard at localhost:5000
✅ Roblox demo mode with realistic data
✅ Badge system ready
✅ All syntax errors fixed
✅ SSL certificates configured
✅ Database initialized
✅ macOS app bundle created

## 🚫 What's Disabled (To Stay Under 100 Command Limit)

These features are disabled but can be re-enabled if needed:
- Music commands (30)
- Advanced games (7)
- AI features (9)
- Server analytics (7)
- Minigames (6)
- Custom commands (5)
- Automation (4)
- Voice stats (3)
- YouTube (3)
- Translation (2)

## 📚 Documentation

- `README.md` - Complete documentation
- `APP_USAGE.md` - App usage guide
- `SETUP_COMPLETE.md` - Setup summary
- `docs/BADGE_GUIDE.md` - Badge system
- `docs/ROBLOX_SETUP.md` - Roblox setup

## 🎉 You're Ready!

Everything is set up and working. Start exploring:
1. Try commands in Discord
2. Open the web dashboard
3. Check out the Roblox leaderboards
4. Assign badges to members

**Have fun managing your Discord server!** 🚀
