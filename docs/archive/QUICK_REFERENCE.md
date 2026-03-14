# 🚀 WAN Bot - Quick Reference Card

**The Ultimate Discord Bot - Quick Access Guide**

---

## ⚡ Quick Start

```bash
# Start bot with web dashboard
./start_with_web.sh

# Access dashboard
http://localhost:5000

# Default login
Username: admin
Password: admin
```

---

## 🌐 Web Dashboard

### Access URLs
- **Local**: `http://localhost:5000`
- **Remote**: `http://YOUR_SERVER_IP:5000`
- **HTTPS**: Configure reverse proxy (see 24_7_DEPLOYMENT.md)

### Dashboard Pages
- 🏠 Dashboard - Overview and stats
- 🖥️ Servers - Manage all servers
- 📊 Analytics - Growth and metrics
- 🛡️ Moderation - Kick/ban tools
- 🎵 Music - Playback control
- 🤖 AI - AI features
- 🎮 Games - Game management
- ⚙️ Settings - Configuration
- 📝 Logs - Real-time logs

---

## 🔧 24/7 Deployment

### Systemd (Linux - Recommended)
```bash
# Setup
sudo cp wanbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wanbot
sudo systemctl start wanbot

# Management
sudo systemctl status wanbot    # Check status
sudo systemctl restart wanbot   # Restart
sudo systemctl stop wanbot      # Stop
sudo journalctl -u wanbot -f    # View logs
```

### PM2 (Easy Management)
```bash
# Setup
npm install -g pm2
pm2 start ecosystem.config.js

# Management
pm2 status          # Check status
pm2 restart wanbot  # Restart
pm2 stop wanbot     # Stop
pm2 logs wanbot     # View logs
pm2 monit           # Monitor
```

### Docker (Containerized)
```bash
# Start
docker-compose up -d

# Management
docker-compose logs -f      # View logs
docker-compose restart      # Restart
docker-compose down         # Stop
```

### Screen/Tmux (Simple)
```bash
# Screen
screen -S wanbot
./start_with_web.sh
# Detach: Ctrl+A then D
screen -r wanbot    # Reattach

# Tmux
tmux new -s wanbot
./start_with_web.sh
# Detach: Ctrl+B then D
tmux attach -t wanbot    # Reattach
```

---

## 🎮 Top Commands

### Music (25+ commands)
```
/play <song>              # Play music
/playlist-create <name>   # Create playlist
/radio <station>          # 24/7 radio
/music-mood <mood>        # Mood-based music
/music-effects            # Audio effects
/music-quiz               # Music trivia
```

### AI Features (15+ commands)
```
/ai <message>             # Chat with AI
/ai-personality <type>    # Change personality
/ai-image <prompt>        # Generate image
/ai-code <language>       # Generate code
/ai-analyze <text>        # Analyze text
```

### Games (25+ commands)
```
/rpg-create <name> <class>    # Create character
/rpg-adventure <difficulty>   # Go on adventure
/rpg-battle <user>            # PvP battle
/casino-slots <bet>           # Play slots
/casino-blackjack <bet>       # Play blackjack
```

### Server Management (20+ commands)
```
/server-analytics         # View analytics
/security-scan            # Security check
/server-optimize          # Optimize server
/server-backup            # Backup server
/server-health            # Health check
```

### Moderation (20+ commands)
```
/ban <user> [reason]      # Ban member
/kick <user> [reason]     # Kick member
/timeout <user> <time>    # Timeout member
/warn <user> <reason>     # Warn member
/purge <amount>           # Delete messages
```

### Economy (15+ commands)
```
/balance                  # Check balance
/daily                    # Daily reward
/work                     # Earn money
/shop                     # View shop
/buy <item>              # Buy item
```

### Utility (15+ commands)
```
/wan                      # Bot dashboard
/serverinfo               # Server info
/userinfo [user]          # User info
/poll <question>          # Create poll
/remind <time> <message>  # Set reminder
```

---

## 📊 Statistics

- **Commands**: 250+
- **Cogs**: 30
- **Features**: 100+
- **Visual Components**: 100+
- **Emoji Library**: 165+
- **Lines of Code**: 15,000+

---

## 🔒 Security

### Change Default Password
Edit `web_dashboard.py` line ~60:
```python
if username == 'admin' and password == 'YOUR_NEW_PASSWORD':
```

### Generate Secret Key
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Enable HTTPS
Use Nginx reverse proxy:
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:5000;
    }
}
```

### Firewall
```bash
# Allow specific IP only
sudo ufw allow from YOUR_IP to any port 5000

# Or use SSH tunnel
ssh -L 5000:localhost:5000 user@server
```

---

## 🛠️ Troubleshooting

### Bot Won't Start
```bash
# Check logs
tail -f bot.log
tail -f bot_error.log

# Check environment
cat .env

# Reinstall dependencies
pip install -r requirements.txt
```

### Dashboard Not Accessible
```bash
# Check if running
netstat -tulpn | grep 5000
lsof -i :5000

# Check firewall
sudo ufw status

# Check host binding in .env
DASHBOARD_HOST=0.0.0.0  # For external access
```

### High Memory Usage
```bash
# Check memory
ps aux | grep python3

# Restart bot
sudo systemctl restart wanbot
# or
pm2 restart wanbot
```

---

## 📚 Documentation

- **README.md** - Main documentation
- **SETUP.md** - Setup instructions
- **QUICKSTART.md** - Quick start guide
- **24_7_DEPLOYMENT.md** - Deployment guide (500+ lines)
- **PRODUCTION_GUIDE.md** - Production tips
- **CHANGELOG.md** - All changes
- **STATUS.md** - Current status
- **PHASE6_COMPLETE.md** - Phase 6 summary

---

## 🔗 Important Files

### Configuration
- `.env` - Environment variables
- `bot.py` - Main bot file
- `web_dashboard.py` - Dashboard backend
- `requirements.txt` - Dependencies

### Deployment
- `wanbot.service` - Systemd service
- `ecosystem.config.js` - PM2 config
- `docker-compose.yml` - Docker config
- `start_with_web.sh` - Startup script

### Database
- `bot.db` - SQLite database
- `utils/database.py` - Database utilities

---

## 💡 Pro Tips

1. **Always use virtual environment**
   ```bash
   source venv/bin/activate
   ```

2. **Keep logs clean**
   ```bash
   # Rotate logs weekly
   sudo logrotate -f /etc/logrotate.d/wanbot
   ```

3. **Regular backups**
   ```bash
   # Backup database
   cp bot.db backups/bot_$(date +%Y%m%d).db
   ```

4. **Monitor resources**
   ```bash
   # Check bot resources
   ps aux | grep python3
   free -h
   df -h
   ```

5. **Update regularly**
   ```bash
   git pull
   pip install -r requirements.txt --upgrade
   sudo systemctl restart wanbot
   ```

---

## 🆘 Quick Help

### Common Issues

**"Module not found"**
```bash
pip install -r requirements.txt
```

**"Permission denied"**
```bash
chmod +x start_with_web.sh
chmod +x setup.sh
```

**"Port already in use"**
```bash
# Change port in .env
DASHBOARD_PORT=5001
```

**"Bot offline in dashboard"**
```bash
# Check bot process
ps aux | grep python3
# Restart if needed
sudo systemctl restart wanbot
```

---

## 📞 Support

1. Check logs: `tail -f bot.log`
2. Review documentation
3. Check Discord.py docs
4. Open GitHub issue

---

## 🎉 Quick Commands Summary

```bash
# Start
./start_with_web.sh

# Status
sudo systemctl status wanbot
pm2 status

# Logs
tail -f bot.log
sudo journalctl -u wanbot -f
pm2 logs wanbot

# Restart
sudo systemctl restart wanbot
pm2 restart wanbot

# Stop
sudo systemctl stop wanbot
pm2 stop wanbot

# Dashboard
http://localhost:5000
```

---

**WAN Bot - The Ultimate Discord Bot with 24/7 Web Control!** 🚀🤖🌐

*For detailed information, see 24_7_DEPLOYMENT.md*
