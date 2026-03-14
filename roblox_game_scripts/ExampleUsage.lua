--[[
    Example Usage - How to use the Player Stats Manager in your game
    
    Place these examples in your game scripts where you handle
    coins, kills, deaths, and leveling
]]

-- Example 1: When player collects a coin
local function onCoinCollected(player, coinValue)
    -- Add coins to player stats
    _G.AddCoins(player, coinValue)
    
    -- Your existing coin collection code here
    print(player.Name .. " collected " .. coinValue .. " coins!")
end

-- Example 2: When player gets a kill
local function onPlayerKill(killer, victim)
    if killer and killer:IsA("Player") then
        -- Add kill to killer's stats
        _G.AddKill(killer)
        print(killer.Name .. " got a kill!")
    end
    
    if victim and victim:IsA("Player") then
        -- Add death to victim's stats
        _G.AddDeath(victim)
        print(victim.Name .. " died!")
    end
end

-- Example 3: When player levels up
local function onPlayerLevelUp(player, newLevel)
    -- Set player's new level
    _G.SetLevel(player, newLevel)
    
    -- Your existing level up code here
    print(player.Name .. " reached level " .. newLevel .. "!")
end

-- Example 4: Display player stats in GUI
local function showPlayerStats(player)
    local stats = _G.GetPlayerStats(player)
    
    print("=== " .. player.Name .. "'s Stats ===")
    print("Playtime: " .. math.floor(stats.playtime / 3600) .. " hours")
    print("Coins: " .. stats.coins_collected)
    print("Kills: " .. stats.kills)
    print("Deaths: " .. stats.deaths)
    print("Level: " .. stats.level)
    print("K/D Ratio: " .. string.format("%.2f", stats.kills / math.max(stats.deaths, 1)))
end

-- Example 5: Coin pickup part
local coinPart = workspace.CoinPart -- Replace with your coin part
local COIN_VALUE = 10

coinPart.Touched:Connect(function(hit)
    local player = game.Players:GetPlayerFromCharacter(hit.Parent)
    if player then
        _G.AddCoins(player, COIN_VALUE)
        coinPart:Destroy() -- Remove coin after collection
    end
end)

-- Example 6: Combat system integration
local function handleCombat(attacker, target, damage)
    -- Your combat logic here
    local targetHealth = target.Humanoid.Health - damage
    target.Humanoid.Health = targetHealth
    
    -- If target died
    if targetHealth <= 0 then
        local attackerPlayer = game.Players:GetPlayerFromCharacter(attacker)
        local targetPlayer = game.Players:GetPlayerFromCharacter(target)
        
        if attackerPlayer and targetPlayer then
            _G.AddKill(attackerPlayer)
            _G.AddDeath(targetPlayer)
        end
    end
end

-- Example 7: XP and Leveling system
local XP_PER_LEVEL = 100

local function addXP(player, amount)
    local currentXP = player:GetAttribute("XP") or 0
    local currentLevel = player:GetAttribute("Level") or 1
    
    currentXP = currentXP + amount
    player:SetAttribute("XP", currentXP)
    
    -- Check for level up
    local xpNeeded = currentLevel * XP_PER_LEVEL
    if currentXP >= xpNeeded then
        currentLevel = currentLevel + 1
        currentXP = currentXP - xpNeeded
        
        player:SetAttribute("XP", currentXP)
        _G.SetLevel(player, currentLevel)
        
        -- Show level up effect
        print(player.Name .. " leveled up to " .. currentLevel .. "!")
    end
end

-- Example 8: Quest completion rewards
local function completeQuest(player, questReward)
    _G.AddCoins(player, questReward.coins)
    addXP(player, questReward.xp)
    
    print(player.Name .. " completed quest! +" .. questReward.coins .. " coins, +" .. questReward.xp .. " XP")
end

-- Example 9: Daily login bonus
local function giveLoginBonus(player)
    local DAILY_COINS = 100
    _G.AddCoins(player, DAILY_COINS)
    
    print(player.Name .. " received daily login bonus: " .. DAILY_COINS .. " coins!")
end

-- Example 10: Leaderboard display (in-game)
local function createLeaderboard()
    local leaderboard = Instance.new("Folder")
    leaderboard.Name = "leaderstats"
    
    return function(player)
        local stats = leaderboard:Clone()
        stats.Parent = player
        
        local coins = Instance.new("IntValue")
        coins.Name = "Coins"
        coins.Value = player:GetAttribute("Coins") or 0
        coins.Parent = stats
        
        local level = Instance.new("IntValue")
        level.Name = "Level"
        level.Value = player:GetAttribute("Level") or 1
        level.Parent = stats
        
        local kills = Instance.new("IntValue")
        kills.Name = "Kills"
        kills.Value = player:GetAttribute("Kills") or 0
        kills.Parent = stats
        
        -- Update leaderboard when attributes change
        player:GetAttributeChangedSignal("Coins"):Connect(function()
            coins.Value = player:GetAttribute("Coins")
        end)
        
        player:GetAttributeChangedSignal("Level"):Connect(function()
            level.Value = player:GetAttribute("Level")
        end)
        
        player:GetAttributeChangedSignal("Kills"):Connect(function()
            kills.Value = player:GetAttribute("Kills")
        end)
    end
end

-- Initialize leaderboard for all players
local initLeaderboard = createLeaderboard()
game.Players.PlayerAdded:Connect(initLeaderboard)

print("[Examples] Stats usage examples loaded!")
print("[Examples] Use _G.AddCoins, _G.AddKill, _G.AddDeath, _G.SetLevel in your scripts")
