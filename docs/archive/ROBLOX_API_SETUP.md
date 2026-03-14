# 🔑 Roblox API Setup Guide

This guide will walk you through setting up the Roblox Open Cloud API to connect your Discord bot to your Wizard West game.

## 📋 Prerequisites

- A Roblox account with access to your game
- Your game must be published (not just saved locally)
- Basic understanding of Roblox Studio

## 🎯 Step-by-Step Setup

### Step 1: Get Your Universe ID and Place ID

1. **Open your game in Roblox Studio**

2. **Get Place ID:**
   - Go to `Home` tab → `Game Settings`
   - Look at the URL or the settings window
   - Your Place ID is the number in the URL: `roblox.com/games/PLACE_ID/`
   - Example: `123456789`

3. **Get Universe ID:**
   - Method 1: Use this URL in your browser:
     ```
     https://apis.roblox.com/universes/v1/places/YOUR_PLACE_ID/universe
     ```
     Replace `YOUR_PLACE_ID` with your actual Place ID
   
   - Method 2: Go to [Roblox Creator Dashboard](https://create.roblox.com/)
     - Select your game
     - The Universe ID is in the URL: `create.roblox.com/dashboard/creations/experiences/UNIVERSE_ID/`

4. **Save these numbers** - you'll need them later!

### Step 2: Create Open Cloud API Key

1. **Go to Creator Dashboard:**
   - Visit [https://create.roblox.com/](https://create.roblox.com/)
   - Sign in with your Roblox account

2. **Navigate to API Keys:**
   - Click on your game (Wizard West)
   - In the left sidebar, click `Open Cloud`
   - Click `API Keys`

3. **Create New API Key:**
   - Click `Create API Key` button
   - Give it a name: `WAN Bot Discord Integration`

4. **Configure Permissions:**
   - **Access Permissions:** Select `DataStore`
   - **API System:** Check `DataStore`
   - **Operations:** Select:
     - ✅ Read Entry
     - ✅ List Entries (optional)
   
5. **Set Experience:**
   - Click `Add Experience`
   - Select your Wizard West game
   - This restricts the key to only your game (security best practice)

6. **Set Expiration:**
   - Choose `No Expiration` or set a long expiration date
   - You can always revoke and create a new key later

7. **Create and Copy:**
   - Click `Save and Generate Key`
   - **IMPORTANT:** Copy the API key immediately!
   - You won't be able to see it again
   - Store it securely

### Step 3: Install Game Scripts

1. **Open Roblox Studio** with your Wizard West game

2. **Add PlayerStatsManager:**
   - In Explorer, find `ServerScriptService`
   - Right-click → `Insert Object` → `Script`
   - Name it `PlayerStatsManager`
   - Copy the contents from `roblox_game_scripts/PlayerStatsManager.lua`
   - Paste into the script

3. **Add Example Usage (Optional):**
   - Create another Script in `ServerScriptService`
   - Name it `StatsExamples`
   - Copy contents from `roblox_game_scripts/ExampleUsage.lua`
   - Customize for your game's specific needs

4. **Enable API Services:**
   - Go to `Home` tab → `Game Settings`
   - Click `Security` tab
   - Enable `Enable Studio Access to API Services`
   - Enable `Allow HTTP Requests` (if using webhooks)
   - Click `Save`

5. **Publish Your Game:**
   - Click `File` → `Publish to Roblox`
   - This updates the live version with the new scripts

### Step 4: Configure Discord Bot

1. **Open your `.env` file** in the bot directory

2. **Add Roblox Configuration:**
   ```env
   # Roblox Integration
   ROBLOX_API_KEY=your_api_key_here
   ROBLOX_UNIVERSE_ID=your_universe_id_here
   ROBLOX_PLACE_ID=your_place_id_here
   ```

3. **Replace the values:**
   - `ROBLOX_API_KEY`: The API key you copied in Step 2
   - `ROBLOX_UNIVERSE_ID`: Your Universe ID from Step 1
   - `ROBLOX_PLACE_ID`: Your Place ID from Step 1

4. **Example:**
   ```env
   ROBLOX_API_KEY=rbxosk_1234567890abcdefghijklmnopqrstuvwxyz
   ROBLOX_UNIVERSE_ID=987654321
   ROBLOX_PLACE_ID=123456789
   ```

### Step 5: Test the Integration

1. **Restart your Discord bot:**
   ```bash
   python3 bot.py
   ```

2. **Check the startup logs:**
   - You should see: `✅ Roblox API configured - will fetch real game data`
   - If you see a warning, check your `.env` file

3. **Test in your Roblox game:**
   - Join your game
   - Collect some coins
   - Get some kills/deaths
   - Level up
   - Leave the game (this triggers save)

4. **Test in Discord:**
   ```
   /roblox-link YourRobloxUsername
   /roblox-stats
   ```

5. **Check the web dashboard:**
   ```
   /web
   ```
   Navigate to "Roblox Stats" section

## 🔍 Troubleshooting

### "Invalid API key" error
- **Solution:** Double-check your API key in `.env`
- Make sure there are no extra spaces
- Verify the key hasn't expired

### "API key doesn't have DataStore permissions"
- **Solution:** Recreate the API key with DataStore permissions
- Make sure you selected "Read Entry" operation

### Stats showing zeros
- **Possible causes:**
  1. Player hasn't played the game yet
  2. DataStore name mismatch (must be "PlayerStats")
  3. Stats not saving properly in game
  4. API key doesn't have access to the correct experience

- **Debug steps:**
  1. Check Roblox Studio output for save messages
  2. Test with a player who has definitely played
  3. Verify DataStore name matches in both game and bot
  4. Check API key is for the correct game

### "No game data found" message
- **Solution:** This is normal for players who haven't played yet
- Have the player join the game and play for a bit
- Make sure they leave properly (not just closing Roblox)
- Wait a few minutes for DataStore to update

### Bot still using mock data
- **Check:**
  1. `.env` file has all three variables set
  2. Bot was restarted after adding variables
  3. No typos in variable names
  4. API key is valid and not expired

## 🔒 Security Best Practices

1. **Never share your API key publicly**
   - Don't commit it to GitHub
   - Don't share it in Discord
   - Don't post it in screenshots

2. **Use environment variables**
   - Keep API keys in `.env` file
   - Add `.env` to `.gitignore`

3. **Restrict API key scope**
   - Only give DataStore permissions
   - Restrict to specific experience
   - Set reasonable expiration

4. **Monitor usage**
   - Check Creator Dashboard for API usage
   - Revoke keys if suspicious activity
   - Rotate keys periodically

## 📊 DataStore Structure

Your game saves data in this format:

```lua
{
    playtime = 3600,           -- seconds
    coins_collected = 5000,    -- total coins
    kills = 50,                -- total kills
    deaths = 20,               -- total deaths
    level = 15,                -- current level
    last_played = 1234567890   -- unix timestamp
}
```

Key format: `Player_{RobloxUserID}`
DataStore name: `PlayerStats`

## 🎮 Customizing Stats

To track additional stats:

1. **Update `PlayerStatsManager.lua`:**
   ```lua
   local DEFAULT_STATS = {
       playtime = 0,
       coins_collected = 0,
       kills = 0,
       deaths = 0,
       level = 1,
       last_played = 0,
       -- Add your custom stats here
       quests_completed = 0,
       bosses_defeated = 0,
       pets_owned = 0
   }
   ```

2. **Update bot's `get_game_stats` method:**
   ```python
   return {
       'user_id': user_id,
       'game_id': game_id or self.place_id,
       'playtime': data.get('playtime', 0),
       'coins_collected': data.get('coins_collected', 0),
       'kills': data.get('kills', 0),
       'deaths': data.get('deaths', 0),
       'level': data.get('level', 1),
       'last_played': data.get('last_played'),
       # Add your custom stats here
       'quests_completed': data.get('quests_completed', 0),
       'bosses_defeated': data.get('bosses_defeated', 0),
       'pets_owned': data.get('pets_owned', 0)
   }
   ```

3. **Update display commands** to show new stats

## 📚 Additional Resources

- [Roblox Open Cloud Documentation](https://create.roblox.com/docs/cloud/open-cloud)
- [DataStore Guide](https://create.roblox.com/docs/cloud-services/data-stores)
- [API Keys Documentation](https://create.roblox.com/docs/cloud/open-cloud/api-keys)
- [DataStore API Reference](https://create.roblox.com/docs/cloud/reference/DataStore)

## ✅ Verification Checklist

Before asking for help, verify:

- [ ] Universe ID and Place ID are correct
- [ ] API key is copied correctly (no spaces)
- [ ] API key has DataStore Read permissions
- [ ] API key is for the correct experience
- [ ] Game scripts are installed in ServerScriptService
- [ ] API Services are enabled in game settings
- [ ] Game is published (not just saved locally)
- [ ] `.env` file has all three variables
- [ ] Bot was restarted after configuration
- [ ] Player has actually played the game
- [ ] Player left the game properly (triggered save)

## 🎉 Success!

Once configured, you'll see:
- Real player stats in Discord commands
- Accurate leaderboards in web dashboard
- Live stat updates every 5 minutes
- Proper playtime, coins, kills, deaths, and levels

Your Discord bot is now fully integrated with your Roblox game! 🚀
