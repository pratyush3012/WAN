# WAN Bot - macOS Application

## Quick Start

1. **Double-click** `WAN Bot.app` to start the bot
2. The bot will automatically:
   - Start in the background
   - Open the web dashboard at http://localhost:5000
   - Show a notification when ready

## What You Get

- **Discord Bot**: Running with 90 slash commands
- **Web Dashboard**: Full server management at http://localhost:5000
- **Roblox Integration**: Demo mode with realistic sample data
- **Badge System**: Automatic role badges for members

## Available Commands (90 total)

### Essential Features
- **Admin** (8 commands): Bot management, settings, maintenance
- **Moderation** (8 commands): Kick, ban, mute, warn, timeout
- **Utility** (8 commands): Userinfo, serverinfo, poll, avatar
- **Economy** (9 commands): Balance, daily, shop, inventory
- **Social** (7 commands): Profile, adopt, streak, mypet
- **Roles** (17 commands): Role management, auto-roles, reaction roles
- **Badges** (5 commands): Badge system, auto-assign, badge stats
- **Fun** (5 commands): Memes, jokes, 8ball, dice
- **Tickets** (4 commands): Support ticket system
- **Birthdays** (5 commands): Birthday tracking and celebrations
- **Roblox** (6 commands): Game stats, leaderboards, clan tracking
- **Web Dashboard** (3 commands): `/web` to open dashboard

### Disabled Features (to stay under Discord's 100 command limit)
Music (30), Games (7), Minigames (6), AI (9), Server Analytics (7), Advanced (5), Custom Commands (5), Automation (4), Rewards (4), Temp Voice (5), Starboard (3), Voice Stats (3), Bump (3), YouTube (3), Translation (2)

## Web Dashboard Features

- **Server Overview**: Real-time stats, member count, online status
- **Roblox Leaderboards**: Top players by playtime, coins, kills, K/D
- **Clan Statistics**: Aggregated stats for all linked members
- **Member Management**: View all linked Roblox accounts
- **Export Data**: Download server data as CSV or JSON

## Roblox Integration (Demo Mode)

Since you don't own the Wizard West game, the bot uses realistic demo data:
- Generates consistent stats per user (based on Discord ID)
- Shows realistic levels (1-50), coins (1k-100k), kills (10-500)
- Demonstrates all features without needing actual game access

To connect a real game later, see `docs/ROBLOX_SETUP.md`

## Stopping the Bot

1. Close the Terminal window that opened with the app
2. Or run: `pkill -f "python.*bot.py"`

## Troubleshooting

### Bot won't start
- Check `.env` file has your Discord token
- Ensure Python 3.8+ is installed
- Run `pip install -r requirements.txt` manually

### Web dashboard not loading
- Wait 8-10 seconds after starting the app
- Check if port 5000 is available: `lsof -i :5000`
- Manually open http://localhost:5000

### Commands not showing in Discord
- Global commands take up to 1 hour to sync
- Try `/web` command to test if bot is responding

## Configuration

Edit `WAN Bot.app/Contents/Resources/.env` to configure:
- Discord token
- Dashboard settings
- Roblox API (optional)

## Support

For issues or questions, check:
- `README.md` - Full documentation
- `docs/BADGE_GUIDE.md` - Badge system guide
- `docs/ROBLOX_SETUP.md` - Roblox integration guide
