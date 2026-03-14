# ✅ Roblox Integration Setup Checklist

Follow this checklist to connect your Discord bot to your Wizard West Roblox game.

## 🎯 Quick Setup (15 minutes)

### Part 1: Roblox Game Setup

- [ ] **Get Place ID**
  - Open game in Roblox Studio
  - Go to Game Settings
  - Note down the Place ID from URL
  - Example: `123456789`

- [ ] **Get Universe ID**
  - Visit: `https://apis.roblox.com/universes/v1/places/YOUR_PLACE_ID/universe`
  - Replace YOUR_PLACE_ID with your actual Place ID
  - Copy the `universeId` from the response
  - Example: `987654321`

- [ ] **Create API Key**
  - Go to [Roblox Creator Dashboard](https://create.roblox.com/)
  - Select your game → Open Cloud → API Keys
  - Click "Create API Key"
  - Name: `WAN Bot Discord Integration`
  - Permissions: DataStore → Read Entry
  - Add your game as the experience
  - Save and copy the API key (you won't see it again!)

- [ ] **Install Game Scripts**
  - Open Roblox Studio with your game
  - Go to ServerScriptService
  - Create new Script named `PlayerStatsManager`
  - Copy code from `roblox_game_scripts/PlayerStatsManager.lua`
  - Paste into the script

- [ ] **Enable API Services**
  - Game Settings → Security
  - Enable "Enable Studio Access to API Services"
  - Enable "Allow HTTP Requests"
  - Save settings

- [ ] **Publish Game**
  - File → Publish to Roblox
  - This updates the live version

### Part 2: Discord Bot Configuration

- [ ] **Update .env file**
  - Open `.env` in your bot directory
  - Add these three lines:
    ```env
    ROBLOX_API_KEY=your_api_key_here
    ROBLOX_UNIVERSE_ID=your_universe_id_here
    ROBLOX_PLACE_ID=your_place_id_here
    ```
  - Replace with your actual values
  - Save the file

- [ ] **Restart Bot**
  - Stop the bot if running (Ctrl+C)
  - Start it again: `python3 bot.py`
  - Look for: `✅ Roblox API configured - will fetch real game data`

### Part 3: Testing

- [ ] **Test in Roblox Game**
  - Join your Wizard West game
  - Play for a few minutes
  - Collect coins, get kills, level up
  - Leave the game properly (don't just close)
  - Wait 1-2 minutes for DataStore to save

- [ ] **Test in Discord**
  - Link your account: `/roblox-link YourRobloxUsername`
  - View stats: `/roblox-stats`
  - Check if stats show real data (not zeros)

- [ ] **Test Web Dashboard**
  - Open dashboard: `/web`
  - Navigate to "Roblox Stats" section
  - Verify leaderboards show real data
  - Check member list displays correctly

### Part 4: Bulk Setup (Optional)

- [ ] **Auto-link all members**
  - Run: `/roblox-sync-bloxlink` (requires Bloxlink bot)
  - This links all members who verified with Bloxlink
  - Check how many members were synced

- [ ] **Verify leaderboards**
  - Run: `/roblox-leaderboard playtime`
  - Check if multiple players show up
  - Try different categories (coins, kills, level)

## 🔍 Verification

### Expected Results:

✅ **Bot Startup:**
```
✅ Roblox API configured - will fetch real game data
[Stats] Player Stats Manager initialized!
```

✅ **Discord Commands:**
- `/roblox-stats` shows real playtime, coins, kills
- `/roblox-leaderboard` displays sorted player data
- `/clan-stats` shows aggregate statistics

✅ **Web Dashboard:**
- Roblox Stats section loads without errors
- Leaderboards show real player data
- Member avatars display correctly
- Stats update every 5 minutes

### Common Issues:

❌ **Still showing zeros?**
- Player hasn't played the game yet
- DataStore hasn't saved yet (wait 1-2 minutes)
- Check bot logs for API errors

❌ **"Invalid API key" error?**
- Double-check API key in `.env`
- Verify no extra spaces or line breaks
- Make sure key hasn't expired

❌ **"No game data found"?**
- Normal for new players
- Have them play the game first
- Ensure they leave properly (triggers save)

## 📊 What Gets Tracked

Your bot now tracks:
- ⏱️ **Playtime** - Total time in game (hours/minutes)
- 💰 **Coins** - Total coins collected
- ⚔️ **Kills** - Total player kills
- 💀 **Deaths** - Total deaths
- ⭐ **Level** - Current player level
- 📅 **Last Played** - When they last played

## 🎮 Using Stats in Your Game

Add to your game scripts:

```lua
-- Give coins
_G.AddCoins(player, 100)

-- Record kill
_G.AddKill(player)

-- Record death
_G.AddDeath(player)

-- Set level
_G.SetLevel(player, 25)

-- Get all stats
local stats = _G.GetPlayerStats(player)
```

See `roblox_game_scripts/ExampleUsage.lua` for more examples!

## 🚀 Next Steps

Once everything is working:

1. **Customize stats tracking** in your game
2. **Add more stat types** (quests, bosses, pets, etc.)
3. **Create custom leaderboards** for specific stats
4. **Set up webhooks** for real-time updates (optional)
5. **Monitor API usage** in Creator Dashboard

## 📚 Documentation

- **Full Setup Guide:** `ROBLOX_API_SETUP.md`
- **Integration Guide:** `ROBLOX_GAME_INTEGRATION.md`
- **Quick Start:** `ROBLOX_WEB_QUICKSTART.md`
- **Game Scripts:** `roblox_game_scripts/` folder

## 🆘 Need Help?

1. Check bot logs for error messages
2. Verify all checklist items are complete
3. Review `ROBLOX_API_SETUP.md` for detailed troubleshooting
4. Test with a fresh player account
5. Check Roblox Studio output for save messages

## ✨ Success Indicators

You'll know it's working when:
- ✅ Bot logs show "Roblox API configured"
- ✅ Discord commands show real stats (not zeros)
- ✅ Web dashboard displays player data
- ✅ Leaderboards update automatically
- ✅ New players appear after playing

---

**Estimated Setup Time:** 15-20 minutes
**Difficulty:** Easy (just copy/paste and configure)
**Result:** Fully integrated Discord bot with live Roblox stats!

🎉 **You're all set!** Your Discord bot now has real-time integration with your Roblox game!
