# 🎮 Roblox Game Integration Guide - Wizard West

This guide explains how to connect your Discord bot to your Roblox game (Wizard West) to fetch real player statistics.

## 📋 Current Status

✅ **Working:**
- Roblox account linking via `/roblox-link`
- Bloxlink integration via `/roblox-sync-bloxlink`
- Web dashboard with leaderboards
- Discord commands for viewing stats
- Automatic stat updates every 5 minutes

⚠️ **Needs Setup:**
- Connection to actual Wizard West game data
- Real-time stat fetching from your game

## 🔧 Setup Options

### Option 1: Roblox Open Cloud API (Recommended)

This is the official way to access DataStores from outside Roblox.

#### Step 1: Get API Key
1. Go to [Roblox Creator Dashboard](https://create.roblox.com/)
2. Select your game (Wizard West)
3. Go to "Open Cloud" → "API Keys"
4. Create a new API key with DataStore permissions
5. Copy the API key

#### Step 2: Configure Your Game
In your Wizard West game, create a DataStore to track player stats:

```lua
-- ServerScriptService/PlayerStatsManager.lua
local DataStoreService = game:GetService("DataStoreService")
local PlayerStats = DataStoreService:GetDataStore("PlayerStats")

-- Save player stats
local function savePlayerStats(userId, stats)
    local success, err = pcall(function()
        PlayerStats:SetAsync("Player_" .. userId, {
            playtime = stats.playtime,
            coins_collected = stats.coins,
            kills = stats.kills,
            deaths = stats.deaths,
            level = stats.level,
            last_played = os.time()
        })
    end)
    return success
end

-- Auto-save on player leaving
game.Players.PlayerRemoving:Connect(function(player)
    local stats = {
        playtime = player:GetAttribute("Playtime") or 0,
        coins = player:GetAttribute("Coins") or 0,
        kills = player:GetAttribute("Kills") or 0,
        deaths = player:GetAttribute("Deaths") or 0,
        level = player:GetAttribute("Level") or 1
    }
    savePlayerStats(player.UserId, stats)
end)
```

#### Step 3: Update Bot Configuration
Add to your `.env` file:

```env
# Roblox Integration
ROBLOX_API_KEY=your_api_key_here
ROBLOX_UNIVERSE_ID=your_universe_id
ROBLOX_GAME_ID=your_place_id
```

#### Step 4: Update the Bot Code
In `cogs/roblox.py`, update the `get_game_stats` method:

```python
async def get_game_stats(self, user_id: int, game_id: int) -> Optional[Dict]:
    """Get player's game statistics from Roblox DataStore"""
    try:
        api_key = os.getenv('ROBLOX_API_KEY')
        universe_id = os.getenv('ROBLOX_UNIVERSE_ID')
        
        if not api_key or not universe_id:
            print("⚠️ Roblox API credentials not configured")
            return self._get_mock_stats(user_id, game_id)
        
        # Fetch from Open Cloud API
        url = f"https://apis.roblox.com/datastores/v1/universes/{universe_id}/standard-datastores/datastore/entries/entry"
        params = {
            'datastoreName': 'PlayerStats',
            'entryKey': f'Player_{user_id}'
        }
        headers = {
            'x-api-key': api_key
        }
        
        async with self.session.get(url, params=params, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return {
                    'user_id': user_id,
                    'game_id': game_id,
                    'playtime': data.get('playtime', 0),
                    'coins_collected': data.get('coins_collected', 0),
                    'kills': data.get('kills', 0),
                    'deaths': data.get('deaths', 0),
                    'level': data.get('level', 1),
                    'last_played': data.get('last_played')
                }
            elif resp.status == 404:
                # Player hasn't played yet
                return self._get_mock_stats(user_id, game_id)
    except Exception as e:
        print(f"Error fetching game stats: {e}")
    
    return self._get_mock_stats(user_id, game_id)

def _get_mock_stats(self, user_id: int, game_id: int) -> Dict:
    """Return mock stats for testing"""
    return {
        'user_id': user_id,
        'game_id': game_id,
        'playtime': 0,
        'coins_collected': 0,
        'kills': 0,
        'deaths': 0,
        'level': 1,
        'last_played': None
    }
```

### Option 2: HTTP Service (In-Game Webhook)

If you want real-time updates, you can send data from your game to the bot.

#### Step 1: Set up a webhook endpoint in your bot
Add to `web_dashboard_enhanced.py`:

```python
@app.route('/api/roblox/webhook', methods=['POST'])
@limiter.limit("100 per minute")
def roblox_webhook():
    """Receive player stats from Roblox game"""
    try:
        # Verify webhook secret
        secret = request.headers.get('X-Webhook-Secret')
        if secret != os.getenv('ROBLOX_WEBHOOK_SECRET'):
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.json
        user_id = data.get('user_id')
        stats = data.get('stats')
        
        # Update cache
        roblox_cog = bot_instance.get_cog('RobloxIntegration')
        if roblox_cog and user_id:
            # Update player cache with new stats
            if user_id in roblox_cog.player_cache:
                roblox_cog.player_cache[user_id]['stats'] = stats
                roblox_cog.player_cache[user_id]['last_updated'] = datetime.utcnow().isoformat()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'error': 'Failed to process webhook'}), 500
```

#### Step 2: Send data from your game
In your Roblox game:

```lua
-- ServerScriptService/StatsWebhook.lua
local HttpService = game:GetService("HttpService")

local WEBHOOK_URL = "https://your-bot-domain.com/api/roblox/webhook"
local WEBHOOK_SECRET = "your_secret_key"

local function sendStatsUpdate(player)
    local stats = {
        user_id = player.UserId,
        stats = {
            playtime = player:GetAttribute("Playtime") or 0,
            coins_collected = player:GetAttribute("Coins") or 0,
            kills = player:GetAttribute("Kills") or 0,
            deaths = player:GetAttribute("Deaths") or 0,
            level = player:GetAttribute("Level") or 1,
            last_played = os.time()
        }
    }
    
    local success, response = pcall(function()
        return HttpService:PostAsync(
            WEBHOOK_URL,
            HttpService:JSONEncode(stats),
            Enum.HttpContentType.ApplicationJson,
            false,
            {["X-Webhook-Secret"] = WEBHOOK_SECRET}
        )
    end)
    
    if not success then
        warn("Failed to send stats update:", response)
    end
end

-- Send updates periodically
game.Players.PlayerRemoving:Connect(sendStatsUpdate)
```

### Option 3: Manual Data Entry (Testing)

For testing purposes, you can manually add test data:

```python
# In Discord, use Python console or create a test command
roblox_cog = bot.get_cog('RobloxIntegration')

# Add test data for a linked player
discord_id = 123456789  # Replace with actual Discord ID
roblox_cog.player_cache[discord_id] = {
    'discord_id': discord_id,
    'roblox_id': 987654321,
    'roblox_username': 'TestPlayer',
    'display_name': 'TestPlayer',
    'is_online': True,
    'currently_playing': True,
    'stats': {
        'playtime': 36000,  # 10 hours in seconds
        'coins_collected': 50000,
        'kills': 150,
        'deaths': 45,
        'level': 25,
        'last_played': datetime.utcnow().isoformat()
    },
    'last_updated': datetime.utcnow().isoformat()
}
```

## 🚀 Using the Integration

### Discord Commands

1. **Link Roblox Account:**
   ```
   /roblox-link username
   ```

2. **View Your Stats:**
   ```
   /roblox-stats
   ```

3. **View Leaderboard:**
   ```
   /roblox-leaderboard playtime
   /roblox-leaderboard coins
   /roblox-leaderboard kills
   ```

4. **View Clan Stats (Admin):**
   ```
   /clan-stats
   ```

5. **Sync with Bloxlink (Admin):**
   ```
   /roblox-sync-bloxlink
   ```

6. **Open Web Dashboard:**
   ```
   /web
   ```

### Web Dashboard

The web dashboard provides:
- 📊 Real-time clan statistics
- 🏆 Interactive leaderboards
- 👥 Member list with avatars
- 📈 Live stat updates
- 🎮 Online/playing status

Access it with `/web` command in Discord!

## 🔍 Troubleshooting

### Stats not updating?
1. Check if Roblox API key is configured in `.env`
2. Verify universe ID and game ID are correct
3. Check bot logs for API errors
4. Ensure DataStore is properly set up in your game

### Leaderboard empty?
1. Link accounts with `/roblox-link` or `/roblox-sync-bloxlink`
2. Wait 5 minutes for first stat update
3. Check if players have played the game recently

### Web dashboard not loading?
1. Ensure web dashboard is running (check bot logs)
2. Use `/web` command to get access link
3. Check if port 5000 is accessible

## 📚 Additional Resources

- [Roblox Open Cloud Documentation](https://create.roblox.com/docs/cloud/open-cloud)
- [DataStore Guide](https://create.roblox.com/docs/cloud-services/data-stores)
- [HttpService Documentation](https://create.roblox.com/docs/reference/engine/classes/HttpService)
- [Bloxlink Documentation](https://blox.link/developers)

## 💡 Tips

1. **Security:** Never share your API keys publicly
2. **Rate Limits:** Roblox API has rate limits, the bot respects them
3. **Testing:** Use mock data first to test the integration
4. **Monitoring:** Check bot logs regularly for errors
5. **Backups:** Keep backups of your DataStore data

## 🆘 Need Help?

If you need help setting this up:
1. Check the bot logs for error messages
2. Verify all environment variables are set
3. Test with mock data first
4. Review Roblox API documentation
5. Check if your game has HttpService enabled

---

**Note:** The bot currently uses mock data until you complete the setup above. All Discord commands and the web dashboard work perfectly - they just need real game data to display actual statistics!
