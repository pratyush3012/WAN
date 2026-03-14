# 🚀 Get Started with WAN Bot in 5 Minutes

**The fastest way to get your ultimate Discord bot running!**

---

## ⚡ Super Quick Start (3 Commands)

```bash
# 1. Setup
./setup.sh

# 2. Configure (add your bot token)
nano .env

# 3. Start with web dashboard
./start_with_web.sh
```

**That's it!** Your bot is now running with web dashboard at `http://localhost:5000`

---

## 📋 What You Need

1. **Discord Bot Token** - Get from [Discord Developer Portal](https://discord.com/developers/applications)
2. **Your Discord User ID** - Enable Developer Mode in Discord, right-click your name, Copy ID
3. **Python 3.8+** - Check with `python3 --version`

---

## 🎯 Step-by-Step Guide

### Step 1: Get Your Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Give it a name (e.g., "WAN Bot")
4. Go to "Bot" section
5. Click "Add Bot"
6. Click "Reset Token" and copy it
7. **Save this token** - you'll need it in Step 3

### Step 2: Invite Bot to Your Server

1. In Developer Portal, go to "OAuth2" → "URL Generator"
2. Select scopes: `bot`, `applications.commands`
3. Select permissions: `Administrator` (or specific permissions)
4. Copy the generated URL
5. Open URL in browser and invite bot to your server

### Step 3: Setup WAN Bot

```bash
# Clone repository (if not already done)
git clone <repository-url>
cd wanbot

# Run setup script
./setup.sh

# This will:
# - Create virtual environment
# - Install all dependencies
# - Create .env file
```

### Step 4: Configure Bot

```bash
# Edit configuration file
nano .env
```

Add your information:
```env
DISCORD_TOKEN=paste_your_bot_token_here
OWNER_ID=your_discord_user_id
```

Save and exit (Ctrl+X, then Y, then Enter)

### Step 5: Start Bot

```bash
# Start with web dashboard
./start_with_web.sh
```

You should see:
```
🤖 Starting WAN Bot with Web Dashboard...
✅ Bot started successfully!
🌐 Web Dashboard is now running!
📊 Access it at: http://localhost:5000
```

### Step 6: Access Dashboard

1. Open browser
2. Go to `http://localhost:5000`
3. Login with:
   - Username: `admin`
   - Password: `admin`
4. **Change password immediately!**

---

## 🎮 Try Your First Commands

In Discord, try these commands:

```
/wan              # Bot dashboard
/help             # List all commands
/serverinfo       # Server information
/ai Hello!        # Chat with AI
/balance          # Check your balance
/play lofi        # Play music (needs FFmpeg)
```

---

## 🌐 Web Dashboard Features

Once logged in, you can:

- 📊 **Dashboard** - View live stats
- 🖥️ **Servers** - Manage all servers
- 📈 **Analytics** - Growth charts
- 🛡️ **Moderation** - Kick/ban members
- 🎵 **Music** - Control playback
- 🤖 **AI** - AI features
- 🎮 **Games** - Game management
- ⚙️ **Settings** - Configuration
- 📝 **Logs** - Real-time logs

---

## ⚡ Make It Run 24/7

### Option 1: Keep Terminal Open
Just leave the terminal running. Bot will run as long as terminal is open.

### Option 2: Use Screen (Simple)
```bash
# Start screen session
screen -S wanbot

# Run bot
./start_with_web.sh

# Detach: Press Ctrl+A then D
# Bot keeps running in background

# Reattach later
screen -r wanbot
```

### Option 3: Systemd (Production)
```bash
# Edit service file
nano wanbot.service
# Update paths to match your setup

# Install service
sudo cp wanbot.service /etc/systemd/system/
sudo systemctl enable wanbot
sudo systemctl start wanbot

# Check status
sudo systemctl status wanbot
```

See [24_7_DEPLOYMENT.md](24_7_DEPLOYMENT.md) for complete guide.

---

## 🔧 Common Issues

### "Module not found"
```bash
# Reinstall dependencies
pip install -r requirements.txt
```

### "Permission denied"
```bash
# Make scripts executable
chmod +x setup.sh
chmod +x start_with_web.sh
```

### "Port already in use"
```bash
# Change port in .env
nano .env
# Change DASHBOARD_PORT=5000 to another port
```

### "Bot not responding"
```bash
# Check logs
tail -f bot.log

# Verify token in .env
cat .env

# Restart bot
# Press Ctrl+C to stop
./start_with_web.sh
```

---

## 📚 Next Steps

### Learn More
- **[README.md](README.md)** - Full documentation
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Command reference
- **[24_7_DEPLOYMENT.md](24_7_DEPLOYMENT.md)** - Production deployment

### Customize
- Change bot status in `bot.py`
- Customize dashboard colors in `static/css/style.css`
- Add custom commands
- Configure features

### Secure
- Change default dashboard password
- Set up HTTPS for production
- Configure firewall
- Regular backups

---

## 🎯 Quick Commands Reference

### Bot Management
```bash
# Start bot
./start_with_web.sh

# Stop bot
Ctrl+C

# View logs
tail -f bot.log

# Check status (if using systemd)
sudo systemctl status wanbot
```

### Dashboard
```
URL: http://localhost:5000
Login: admin/admin
```

### Discord Commands
```
/wan              # Bot dashboard
/help             # Help menu
/play <song>      # Play music
/ai <message>     # Chat with AI
/serverinfo       # Server info
/balance          # Your balance
```

---

## 💡 Pro Tips

1. **Install FFmpeg** for music features:
   ```bash
   ./install-ffmpeg.sh
   ```

2. **Change dashboard password** immediately:
   - Edit `web_dashboard.py` line ~60
   - Change 'admin' password

3. **Use screen/tmux** for easy 24/7 running:
   ```bash
   screen -S wanbot
   ./start_with_web.sh
   # Detach: Ctrl+A then D
   ```

4. **Monitor resources**:
   ```bash
   # Check memory/CPU
   ps aux | grep python3
   ```

5. **Regular backups**:
   ```bash
   # Backup database
   cp bot.db backups/bot_$(date +%Y%m%d).db
   ```

---

## 🆘 Need Help?

1. **Check logs**: `tail -f bot.log`
2. **Read docs**: All .md files in project
3. **Review troubleshooting**: [24_7_DEPLOYMENT.md](24_7_DEPLOYMENT.md)
4. **Test commands**: Start with `/help` in Discord

---

## 🎉 You're All Set!

Your WAN Bot is now running with:
- ✅ 250+ commands
- ✅ Web dashboard control
- ✅ AI features
- ✅ Music system
- ✅ Games and economy
- ✅ Moderation tools
- ✅ And much more!

**Enjoy your ultimate Discord bot!** 🚀🤖

---

## 📊 What You Get

- **250+ Commands** - Most comprehensive bot
- **Web Dashboard** - Control from browser
- **AI Features** - ChatGPT-style AI
- **Music System** - 25+ music commands
- **Gaming Platform** - RPG and casino
- **Beautiful Visuals** - Stunning graphics
- **100% Free** - No premium features
- **24/7 Capable** - Multiple deployment options

---

## 🚀 Quick Links

- **Dashboard**: http://localhost:5000
- **Documentation**: [README.md](README.md)
- **Commands**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- **Deployment**: [24_7_DEPLOYMENT.md](24_7_DEPLOYMENT.md)
- **Checklist**: [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)

---

**WAN Bot - The Ultimate Discord Bot - Get Started in 5 Minutes!** ⚡🚀

*For detailed information, see [README.md](README.md) and [24_7_DEPLOYMENT.md](24_7_DEPLOYMENT.md)*
