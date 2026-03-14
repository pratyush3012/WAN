# 🎮 Roblox Integration Setup

## Current Status: Demo Mode

The bot is running in **demo mode** with realistic sample data. This works perfectly for testing without needing access to a Roblox game.

## To Enable Real Game Data

### Step 1: Get API Credentials

1. **Place ID:** From Roblox Studio → Game Settings
2. **Universe ID:** Visit `https://apis.roblox.com/universes/v1/places/YOUR_PLACE_ID/universe`
3. **API Key:** 
   - Go to https://create.roblox.com/
   - Select your game → Open Cloud → API Keys
   - Create key with DataStore Read permissions

### Step 2: Configure Bot

Add to `.env`:
```env
ROBLOX_API_KEY=your_api_key_here
ROBLOX_UNIVERSE_ID=your_universe_id_here
ROBLOX_PLACE_ID=your_place_id_here
```

### Step 3: Install Game Scripts

Copy `roblox_game_scripts/PlayerStatsManager.lua` to your game's ServerScriptService in Roblox Studio.

### Step 4: Restart Bot

```bash
./start_bot.sh
```

Bot will automatically switch to real data mode!

## Demo Mode Features

- ✅ Realistic stats (Level 1-50, coins, kills, etc.)
- ✅ Working leaderboards
- ✅ Full web dashboard
- ✅ All commands functional
- ✅ Consistent data per user

Perfect for testing and demonstration!
