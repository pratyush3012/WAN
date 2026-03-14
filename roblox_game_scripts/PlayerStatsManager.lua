--[[
    Wizard West - Player Stats Manager
    
    This script tracks and saves player statistics to DataStore
    Compatible with WAN Bot Discord integration
    
    Installation:
    1. Place this script in ServerScriptService
    2. Ensure API Services are enabled in Game Settings
    3. Configure the stats you want to track below
]]

local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")

-- DataStore configuration (must match bot's datastoreName)
local PlayerStats = DataStoreService:GetDataStore("PlayerStats")

-- Stats configuration
local DEFAULT_STATS = {
    playtime = 0,           -- Total playtime in seconds
    coins_collected = 0,    -- Total coins collected
    kills = 0,              -- Total kills
    deaths = 0,             -- Total deaths
    level = 1,              -- Player level
    last_played = 0         -- Unix timestamp of last play
}

-- Player data cache (in-memory during session)
local playerData = {}

--[[
    Load player stats from DataStore
]]
local function loadPlayerStats(player)
    local userId = player.UserId
    local key = "Player_" .. userId
    
    local success, data = pcall(function()
        return PlayerStats:GetAsync(key)
    end)
    
    if success and data then
        print("[Stats] Loaded data for " .. player.Name)
        return data
    else
        print("[Stats] Creating new profile for " .. player.Name)
        return table.clone(DEFAULT_STATS)
    end
end

--[[
    Save player stats to DataStore
]]
local function savePlayerStats(player)
    local userId = player.UserId
    local key = "Player_" .. userId
    local data = playerData[userId]
    
    if not data then
        warn("[Stats] No data to save for " .. player.Name)
        return false
    end
    
    -- Update last played timestamp
    data.last_played = os.time()
    
    local success, err = pcall(function()
        PlayerStats:SetAsync(key, data)
    end)
    
    if success then
        print("[Stats] Saved data for " .. player.Name)
        return true
    else
        warn("[Stats] Failed to save data for " .. player.Name .. ": " .. tostring(err))
        return false
    end
end

--[[
    Initialize player stats when they join
]]
local function onPlayerAdded(player)
    -- Load stats from DataStore
    local stats = loadPlayerStats(player)
    playerData[player.UserId] = stats
    
    -- Set player attributes (accessible from other scripts)
    player:SetAttribute("Playtime", stats.playtime)
    player:SetAttribute("Coins", stats.coins_collected)
    player:SetAttribute("Kills", stats.kills)
    player:SetAttribute("Deaths", stats.deaths)
    player:SetAttribute("Level", stats.level)
    
    -- Track playtime
    local joinTime = os.time()
    
    -- Update playtime every minute
    task.spawn(function()
        while player.Parent do
            task.wait(60) -- Update every minute
            if player.Parent then
                local currentPlaytime = os.time() - joinTime
                playerData[player.UserId].playtime = stats.playtime + currentPlaytime
                player:SetAttribute("Playtime", playerData[player.UserId].playtime)
            end
        end
    end)
end

--[[
    Save player stats when they leave
]]
local function onPlayerRemoving(player)
    local userId = player.UserId
    
    if playerData[userId] then
        -- Update final stats from attributes
        playerData[userId].coins_collected = player:GetAttribute("Coins") or playerData[userId].coins_collected
        playerData[userId].kills = player:GetAttribute("Kills") or playerData[userId].kills
        playerData[userId].deaths = player:GetAttribute("Deaths") or playerData[userId].deaths
        playerData[userId].level = player:GetAttribute("Level") or playerData[userId].level
        
        -- Save to DataStore
        savePlayerStats(player)
        
        -- Clear from cache
        playerData[userId] = nil
    end
end

--[[
    Public API functions for other scripts to use
]]

-- Add coins to player
function AddCoins(player, amount)
    local current = player:GetAttribute("Coins") or 0
    player:SetAttribute("Coins", current + amount)
end

-- Add kill to player
function AddKill(player)
    local current = player:GetAttribute("Kills") or 0
    player:SetAttribute("Kills", current + 1)
end

-- Add death to player
function AddDeath(player)
    local current = player:GetAttribute("Deaths") or 0
    player:SetAttribute("Deaths", current + 1)
end

-- Set player level
function SetLevel(player, level)
    player:SetAttribute("Level", level)
end

-- Get player stats
function GetPlayerStats(player)
    return {
        playtime = player:GetAttribute("Playtime") or 0,
        coins_collected = player:GetAttribute("Coins") or 0,
        kills = player:GetAttribute("Kills") or 0,
        deaths = player:GetAttribute("Deaths") or 0,
        level = player:GetAttribute("Level") or 1
    }
end

-- Make functions global so other scripts can use them
_G.AddCoins = AddCoins
_G.AddKill = AddKill
_G.AddDeath = AddDeath
_G.SetLevel = SetLevel
_G.GetPlayerStats = GetPlayerStats

-- Connect events
Players.PlayerAdded:Connect(onPlayerAdded)
Players.PlayerRemoving:Connect(onPlayerRemoving)

-- Handle players already in game (for testing)
for _, player in ipairs(Players:GetPlayers()) do
    task.spawn(onPlayerAdded, player)
end

-- Auto-save every 5 minutes
task.spawn(function()
    while true do
        task.wait(300) -- 5 minutes
        print("[Stats] Auto-saving all player data...")
        for _, player in ipairs(Players:GetPlayers()) do
            if playerData[player.UserId] then
                savePlayerStats(player)
            end
        end
    end
end)

print("[Stats] Player Stats Manager initialized!")
print("[Stats] DataStore: PlayerStats")
print("[Stats] Auto-save: Every 5 minutes")
