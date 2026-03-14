# 🚀 Getting Started with WAN Bot

## Quick Start (3 Steps)

### 1. Double-Click to Start
```
WAN Bot.app
```

That's it! The bot will start automatically.

### 2. First Time Setup

If this is your first time:

1. **Install dependencies** (automatic on first run)
2. **Configure Discord token** in `.env` file
3. **Restart the app**

### 3. Test in Discord

```
/badge              - View your badge
/roblox-link Test   - Link Roblox account
/web                - Open web dashboard
```

## Manual Start

If you prefer terminal:

```bash
./start_bot.sh
```

## Configuration

Edit `.env` file:

```env
# Required
DISCORD_TOKEN=your_token_here

# Optional (for real Roblox data)
ROBLOX_API_KEY=your_key
ROBLOX_UNIVERSE_ID=your_id
ROBLOX_PLACE_ID=your_id
```

## Features

✅ Badge system for role identification
✅ Roblox integration (demo mode)
✅ Web dashboard at http://localhost:5000
✅ Economy, leveling, moderation
✅ Music, tickets, fun commands
✅ And much more!

## Commands

See `README.md` for complete command list.

## Troubleshooting

**Bot won't start?**
- Check `.env` has your Discord token
- Run `./test_bot.sh` to diagnose issues

**Commands not showing?**
- Wait 1-2 minutes after bot starts
- Check bot permissions in Discord

**Need help?**
- Check `README.md`
- Review `docs/` folder
- Check bot logs in terminal

## Documentation

- `README.md` - Complete guide
- `docs/ROBLOX_SETUP.md` - Roblox integration
- `docs/BADGE_GUIDE.md` - Badge system

## Support

Check logs: `tail -f bot.log`
Run tests: `./test_bot.sh`

---

**Ready?** Double-click `WAN Bot.app` to start! 🎉
