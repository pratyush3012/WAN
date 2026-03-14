# ⚡ Quick Start Guide

## 🎯 What's Been Done For You

✅ Python 3.14.3 detected  
✅ Virtual environment created (`venv/`)  
✅ All Python dependencies installed  
✅ Setup scripts created  
⚠️ FFmpeg needs to be installed (for music feature)

---

## 🚀 3 Steps to Get Running

### Step 1: Install FFmpeg (Required for Music)

```bash
brew install ffmpeg
```

This will take 5-10 minutes. You can continue to Step 2 while it installs.

---

### Step 2: Get Your Discord Bot Credentials

#### A. Create Discord Bot
1. Go to: https://discord.com/developers/applications
2. Click **"New Application"** → Name it → **"Create"**
3. Go to **"Bot"** tab → **"Add Bot"**
4. Enable these under **"Privileged Gateway Intents"**:
   - ✅ Presence Intent
   - ✅ Server Members Intent
   - ✅ Message Content Intent
5. Click **"Reset Token"** → Copy the token (you'll need this!)

#### B. Get Your User ID
1. Open Discord → User Settings → Advanced
2. Enable **"Developer Mode"**
3. Right-click your username → **"Copy ID"**

#### C. Invite Bot to Your Server
1. In Developer Portal, go to **"OAuth2"** → **"URL Generator"**
2. Select: **bot** + **applications.commands**
3. Select: **Administrator** (or specific permissions)
4. Copy the URL and open it in browser
5. Select your server → **"Authorize"**

---

### Step 3: Run Setup Script

```bash
./setup.sh
```

This will:
- Create your `.env` file with your credentials
- Initialize the database
- Verify everything is ready

**You'll be asked for:**
- Discord Bot Token (from Step 2A)
- Your User ID (from Step 2B)
- Optional: Google Translate API Key (press Enter to skip)
- Optional: YouTube API Key (press Enter to skip)

---

## 🎉 Start Your Bot

```bash
./run.sh
```

You should see:
```
🤖 Starting Discord Bot...
✅ Starting bot...

2026-02-27 12:00:00 | INFO | 🤖 YourBotName#1234 is now online!
2026-02-27 12:00:00 | INFO | 📊 Connected to 1 guilds
2026-02-27 12:00:00 | INFO | ✅ Synced 25 slash commands
```

---

## 🧪 Test Your Bot

In Discord, try these commands:

```
/config          - View bot configuration
/rank            - Check your XP rank
/play <song>     - Play music (if FFmpeg installed)
```

Type a message and react with 🌐 to test translation!

---

## 🛑 Stop the Bot

Press `Ctrl + C` in the terminal

---

## 📚 Next Steps

### Configure Your Server
```
/setlogchannel #logs       - Set mod log channel
/setwelcome #welcome       - Set welcome channel
/setautorole @Member       - Auto-role for new members
/setdjrole @DJ            - DJ role for music
```

### Learn More
- **Full Setup Guide:** `SETUP.md`
- **All Commands:** `README.md`
- **Production Deployment:** `PRODUCTION_GUIDE.md`
- **Troubleshooting:** `OPERATIONS_RUNBOOK.md`

---

## 🆘 Common Issues

### "FFmpeg not found"
```bash
brew install ffmpeg
```

### "Module not found"
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### "Commands not appearing"
- Wait 5-10 minutes for Discord to sync
- Make sure bot has `applications.commands` scope
- Kick and re-invite bot if needed

### "Permission denied"
```bash
chmod +x setup.sh run.sh
```

---

## 🎯 What You Have

### Features Ready:
- ✅ Moderation (kick, ban, timeout, lock channels)
- ✅ Music System (YouTube playback with queue)
- ✅ Translation (Hinglish-optimized with buttons)
- ✅ XP & Leveling (message and voice XP)
- ✅ Auto-moderation (anti-spam, anti-raid)
- ✅ Automation (welcome messages, auto-roles)
- ✅ YouTube Notifications
- ✅ Giveaways
- ✅ Logging (all server events)

### Production Ready:
- ✅ No memory leaks
- ✅ No connection leaks
- ✅ Rate limiting
- ✅ Race condition protection
- ✅ Proper error handling
- ✅ Comprehensive logging

---

## 💡 Pro Tips

### Keep Bot Running 24/7
```bash
# Option 1: Using screen
screen -S bot
./run.sh
# Press Ctrl+A then D to detach

# Option 2: Using nohup
nohup ./run.sh &

# Option 3: Using PM2 (recommended)
npm install -g pm2
pm2 start bot.py --name discord-bot --interpreter python3
```

### View Logs
```bash
tail -f bot.log           # Real-time logs
grep ERROR bot.log        # Find errors
```

### Update Bot
```bash
git pull                  # Get latest code
source venv/bin/activate
pip install -r requirements.txt --upgrade
./run.sh                  # Restart bot
```

---

## ✅ Checklist

- [ ] FFmpeg installed (`brew install ffmpeg`)
- [ ] Discord bot created
- [ ] Bot token obtained
- [ ] User ID obtained
- [ ] Bot invited to server
- [ ] Setup script run (`./setup.sh`)
- [ ] Bot started (`./run.sh`)
- [ ] Commands synced (wait 5-10 min)
- [ ] Tested basic commands

---

**Need Help?** Check the documentation files or the logs in `bot.log`

**Ready for Production?** See `PRODUCTION_GUIDE.md` for VPS deployment

🎉 **Enjoy your bot!**
