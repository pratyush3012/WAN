# 🎮 Roblox Integration Guide - Wizard West

Complete guide for connecting your Discord bot to Roblox Wizard West game to track player statistics!

## 📋 Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Setup Instructions](#setup-instructions)
- [Discord Commands](#discord-commands)
- [Web Dashboard](#web-dashboard)
- [API Endpoints](#api-endpoints)
- [Roblox Game Integration](#roblox-game-integration)
- [Troubleshooting](#troubleshooting)

---

## 🌟 Overview

The Roblox Integration connects your Discord server to the Wizard West game on Roblox, allowing you to:
- Track player statistics (playtime, coins, kills, deaths, level)
- View clan-wide leaderboards
- Monitor who's online and playing
- Display beautiful stats in Discord and web dashboard
- Auto-update stats every 5 minutes

---

## ✨ Features

### Discord Features
- **Account Linking**: Link Discord accounts to Roblox usernames
- **Player Stats**: View individual player statistics with beautiful embeds
- **Clan Stats**: See aggregated statistics for all clan members
- **Leaderboards**: Multiple leaderboard categories (playtime, coins, kills, level, K/D)
- **Real-time Status**: See who's online and currently playing
- **Auto-Updates**: Stats refresh automatically every 5 minutes

### Web Dashboard Features
- **Clan Overview**: Total members, online count, playing count, total coins
- **Clan Totals**: Total playtime, kills, average level, clan K/D ratio
- **Interactive Leaderboards**: Switch between different categories
- **Member Cards**: Beautiful cards showing each member's stats
- **Real-time Updates**: Live status indicators for online/playing members
- **Liquid Glass Theme**: Stunning visual design with animations

---

## 🚀 Setup Instructions

### 1. Bot Configuration

The Roblox cog is already loaded in `bot.py`:

```python
'cogs.roblox'  # Roblox Integration - Wizard West game stats tracking
```

### 2. Configure Game Settings

Edit `cogs/roblox.py` and set your Wizard West game details:

```python
self.game_settings = {
    'game_id': YOUR_GAME_ID,        # Your Wizard West place ID
    'universe_id': YOUR_UNIVERSE_ID, # Your universe ID
    'webhook_secret': 'your_secret'  # For secure data transmission
}
```

**How to find your Game ID:**
1. Go to your game on Roblox
2. Look at the URL: `roblox.com/games/GAME_ID/game-name`
3. The number after `/games/` is your Game ID

**How to find your Universe ID:**
1. Go to Roblox Creator Dashboard
2. Select your game
3. Universe ID is shown in the game details

### 3. Database Setup (Optional)

Currently, the integration stores data in memory. For production, implement database storage:

```python
# In cogs/roblox.py, replace in-memory storage with database calls
# Example:
async def link_account(self, discord_id, roblox_username, roblox_id):
    await self.bot.db.execute(
        "INSERT INTO roblox_links (discord_id, roblox_username, roblox_id) VALUES (?, ?, ?)",
        discord_id, roblox_username, roblox_id
    )
```

### 4. Roblox Game Integration

To send actual game data from Roblox to your bot, you have two options:

#### Option A: HTTP Requests (Recommended)
Create an API endpoint in your bot to receive data from Roblox:

```python
# Add to web_dashboard_enhanced.py
@app.route('/api/roblox/update-stats', methods=['POST'])
def update_roblox_stats():
    secret = request.headers.get('X-Webhook-Secret')
    if secret != os.getenv('ROBLOX_WEBHOOK_SECRET'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    # Update player stats in database
    # ...
    return jsonify({'success': True})
```

Then in your Roblox game (Lua):

```lua
local HttpService = game:GetService("HttpService")

local function sendStats(userId, stats)
    local url = "https://your-bot-domain.com/api/roblox/update-stats"
    local data = {
        user_id = userId,
        playtime = stats.Playtime,
        coins_collected = stats.Coins,
        kills = stats.Kills,
        deaths = stats.Deaths,
        level = stats.Level
    }
    
    local success, response = pcall(function()
        return HttpService:PostAsync(url, HttpService:JSONEncode(data), Enum.HttpContentType.ApplicationJson, false, {
            ["X-Webhook-Secret"] = "your_secret"
        })
    end)
end
```

#### Option B: Roblox Data Stores
Use Roblox's Data Store API to read player data:

```python
# Install roblox library: pip install roblox
from roblox import Client

async def get_game_stats(self, user_id: int, game_id: int):
    client = Client()
    # Read from your game's data store
    # This requires your game to have HTTP API enabled
```

---

## 💬 Discord Commands

### `/roblox-link <username>`
Link your Discord account to your Roblox username.

**Example:**
```
/roblox-link JohnDoe123
```

**Response:**
- ✅ Confirmation with Roblox profile picture
- Account details (username, ID)
- Next steps information

---

### `/roblox-stats [member]`
View Wizard West statistics for yourself or another member.

**Examples:**
```
/roblox-stats
/roblox-stats @JohnDoe
```

**Shows:**
- Online status (🟢 Online / ⚫ Offline)
- Currently playing status (🎮 Playing Now)
- Playtime (hours and minutes)
- Coins collected
- Level
- Kills and Deaths
- K/D Ratio
- Last played time

---

### `/clan-stats`
View aggregated statistics for all clan members.

**Requires:** `Manage Server` permission

**Shows:**
- Top 10 players by playtime
- Top 5 coin collectors
- Top 5 killers
- Currently playing count
- Clan totals (playtime, coins, kills)

---

### `/roblox-leaderboard <category>`
View leaderboards by different categories.

**Categories:**
- `playtime` - Most time played
- `coins` - Most coins collected
- `kills` - Most kills
- `level` - Highest level
- `kd` - Best K/D ratio

**Example:**
```
/roblox-leaderboard coins
```

**Shows:**
- Top 15 players with medals (🥇🥈🥉)
- Player names and values
- Online status indicators

---

### `/roblox-unlink`
Unlink your Roblox account from Discord.

**Example:**
```
/roblox-unlink
```

---

## 🌐 Web Dashboard

### Accessing Roblox Stats

1. Open the dashboard with `/web` command in Discord
2. Click on "Roblox Stats" in the sidebar
3. View comprehensive statistics and leaderboards

### Dashboard Sections

#### 1. Clan Overview
- **Linked Members**: Total members who linked accounts
- **Online Now**: Members currently online on Roblox
- **Playing Now**: Members currently playing Wizard West
- **Total Coins**: Sum of all coins collected by clan

#### 2. Clan Totals
- **Total Playtime**: Combined hours played
- **Total Kills**: All kills by clan members
- **Average Level**: Mean level across all members
- **Clan K/D Ratio**: Overall kill/death ratio

#### 3. Leaderboards
- Interactive dropdown to switch categories
- Top 20 players displayed
- Real-time online status indicators
- Beautiful medal system (🥇🥈🥉)

#### 4. Linked Members
- Grid of member cards
- Profile pictures from Roblox
- Individual stats for each member
- Online/playing status
- Detailed statistics (playtime, coins, kills, level, K/D)

---

## 🔌 API Endpoints

### GET `/api/roblox/linked-members`
Get all linked Roblox accounts.

**Response:**
```json
{
  "members": [
    {
      "discord_id": 123456789,
      "roblox_username": "JohnDoe",
      "roblox_id": 987654321,
      "is_online": true,
      "currently_playing": false,
      "stats": {
        "playtime": 36000,
        "coins_collected": 15000,
        "kills": 250,
        "deaths": 50,
        "level": 25
      }
    }
  ],
  "total": 1
}
```

---

### GET `/api/roblox/stats/<discord_id>`
Get individual player statistics.

**Response:**
```json
{
  "discord_id": 123456789,
  "roblox_id": 987654321,
  "roblox_username": "JohnDoe",
  "display_name": "John Doe",
  "is_online": true,
  "currently_playing": false,
  "stats": {
    "playtime": 36000,
    "coins_collected": 15000,
    "kills": 250,
    "deaths": 50,
    "level": 25
  },
  "last_updated": "2024-03-08T12:00:00"
}
```

---

### GET `/api/roblox/leaderboard/<category>`
Get leaderboard by category.

**Categories:** `playtime`, `coins`, `kills`, `level`, `kd`

**Response:**
```json
{
  "category": "coins",
  "leaderboard": [
    {
      "rank": 1,
      "discord_id": 123456789,
      "roblox_username": "JohnDoe",
      "display_name": "John Doe",
      "is_online": true,
      "value": 15000,
      "stats": { ... }
    }
  ],
  "total_players": 10
}
```

---

### GET `/api/roblox/clan-stats`
Get aggregated clan statistics.

**Response:**
```json
{
  "total_members": 10,
  "tracked_members": 8,
  "online_members": 3,
  "playing_now": 1,
  "totals": {
    "playtime": 360000,
    "playtime_hours": 100,
    "coins_collected": 150000,
    "kills": 2500,
    "deaths": 500,
    "kd_ratio": 5.0
  },
  "averages": {
    "level": 22.5,
    "playtime_per_member": 45000,
    "coins_per_member": 18750
  }
}
```

---

## 🎮 Roblox Game Integration

### Setting Up Data Tracking

1. **Create a Stats Module** in your Roblox game:

```lua
-- ServerScriptService/StatsManager
local StatsManager = {}
local DataStoreService = game:GetService("DataStoreService")
local PlayerStats = DataStoreService:GetDataStore("PlayerStats")

function StatsManager:GetPlayerStats(userId)
    local success, data = pcall(function()
        return PlayerStats:GetAsync(tostring(userId))
    end)
    
    if success and data then
        return data
    else
        return {
            Playtime = 0,
            Coins = 0,
            Kills = 0,
            Deaths = 0,
            Level = 1
        }
    end
end

function StatsManager:SavePlayerStats(userId, stats)
    pcall(function()
        PlayerStats:SetAsync(tostring(userId), stats)
    end)
end

return StatsManager
```

2. **Track Player Sessions**:

```lua
-- Track playtime
local Players = game:GetService("Players")
local StatsManager = require(game.ServerScriptService.StatsManager)

Players.PlayerAdded:Connect(function(player)
    local stats = StatsManager:GetPlayerStats(player.UserId)
    local joinTime = tick()
    
    player.AncestryChanged:Connect(function()
        if not player:IsDescendantOf(game) then
            local playtime = tick() - joinTime
            stats.Playtime = stats.Playtime + playtime
            StatsManager:SavePlayerStats(player.UserId, stats)
        end
    end)
end)
```

3. **Send Stats to Discord Bot**:

```lua
-- Send stats periodically
local HttpService = game:GetService("HttpService")
local BOT_URL = "https://your-bot-domain.com/api/roblox/update-stats"
local WEBHOOK_SECRET = "your_secret"

function sendStatsToBot(userId, stats)
    spawn(function()
        local data = HttpService:JSONEncode({
            user_id = userId,
            playtime = stats.Playtime,
            coins_collected = stats.Coins,
            kills = stats.Kills,
            deaths = stats.Deaths,
            level = stats.Level
        })
        
        pcall(function()
            HttpService:PostAsync(BOT_URL, data, Enum.HttpContentType.ApplicationJson, false, {
                ["X-Webhook-Secret"] = WEBHOOK_SECRET
            })
        end)
    end)
end
```

---

## 🔧 Troubleshooting

### "Roblox integration not loaded"
**Solution:** Make sure `cogs.roblox` is in the cogs list in `bot.py` and the bot has restarted.

### "Player not linked"
**Solution:** User needs to run `/roblox-link <username>` first.

### "Failed to fetch player data"
**Solution:** 
- Check if Roblox username is correct
- Verify Roblox API is accessible
- Check bot logs for detailed error messages

### Stats not updating
**Solution:**
- Verify the background task is running (check logs for "🔄 Updating stats")
- Ensure game_id and universe_id are set correctly
- Check if Roblox game is sending data to bot

### Dashboard shows "No data available"
**Solution:**
- Members need to link accounts with `/roblox-link`
- Wait for background task to fetch stats (runs every 5 minutes)
- Check browser console for API errors

---

## 📊 Data Flow

```
Roblox Game (Wizard West)
    ↓ (HTTP POST or Data Store API)
Discord Bot (Roblox Cog)
    ↓ (Stores in cache/database)
    ├→ Discord Commands (Beautiful embeds)
    └→ Web Dashboard (API endpoints)
        ↓ (Real-time updates via WebSocket)
    Web Browser (Liquid Glass UI)
```

---

## 🎯 Next Steps

1. **Configure Game IDs** in `cogs/roblox.py`
2. **Set up database storage** for persistent data
3. **Implement game-side tracking** in Roblox Lua
4. **Test with `/roblox-link`** command
5. **View stats** in Discord and web dashboard
6. **Monitor auto-updates** every 5 minutes

---

## 💡 Tips

- Encourage clan members to link accounts for better tracking
- Use `/clan-stats` regularly to monitor clan progress
- Check web dashboard for detailed analytics
- Set up webhooks from Roblox for real-time updates
- Consider adding achievements and milestones
- Create custom roles based on stats (top players, etc.)

---

## 🚀 Advanced Features (Future)

- **Achievements System**: Award badges for milestones
- **Stat Comparisons**: Compare two players side-by-side
- **Historical Data**: Track stats over time with charts
- **Notifications**: Alert when members reach milestones
- **Clan Wars**: Track stats during clan battles
- **Custom Leaderboards**: Create custom stat combinations

---

## 📝 Notes

- Stats update every 5 minutes automatically
- Roblox API has rate limits - be mindful of request frequency
- Player data is cached to reduce API calls
- Web dashboard uses caching (30-60 seconds) for performance
- All times are in UTC

---

## 🆘 Support

If you encounter issues:
1. Check bot logs for error messages
2. Verify all configuration settings
3. Test Roblox API connectivity
4. Check Discord bot permissions
5. Review browser console for dashboard errors

---

**Made with ❤️ for Wizard West clan members!**
