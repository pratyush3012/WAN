# ✅ WAN Bot - Deployment Checklist

**Complete checklist for deploying WAN Bot to production**

---

## 📋 Pre-Deployment Checklist

### System Requirements
- [ ] Python 3.8 or higher installed
- [ ] pip package manager available
- [ ] Git installed (for cloning)
- [ ] FFmpeg installed (for music features)
- [ ] Sufficient disk space (minimum 1GB)
- [ ] Stable internet connection

### Discord Setup
- [ ] Discord bot created at [Discord Developer Portal](https://discord.com/developers/applications)
- [ ] Bot token obtained
- [ ] Bot invited to server with proper permissions
- [ ] Your Discord User ID obtained (for OWNER_ID)

### Server Access (for 24/7 hosting)
- [ ] VPS or dedicated server access
- [ ] SSH access configured
- [ ] Sudo/root privileges (for systemd)
- [ ] Firewall access (for web dashboard)

---

## 🚀 Installation Checklist

### 1. Clone Repository
```bash
- [ ] git clone <repository-url>
- [ ] cd wanbot
- [ ] ls -la  # Verify files
```

### 2. Setup Virtual Environment
```bash
- [ ] python3 -m venv venv
- [ ] source venv/bin/activate  # Linux/Mac
- [ ] venv\Scripts\activate     # Windows
```

### 3. Install Dependencies
```bash
- [ ] pip install -r requirements.txt
- [ ] pip list  # Verify installations
```

### 4. Install FFmpeg (for music)
```bash
- [ ] ./install-ffmpeg.sh  # Linux/Mac
- [ ] # Or install manually
```

### 5. Configure Environment
```bash
- [ ] cp .env.example .env
- [ ] nano .env  # Edit configuration
```

### 6. Environment Variables
Edit `.env` file:
```env
- [ ] DISCORD_TOKEN=your_bot_token_here
- [ ] OWNER_ID=your_discord_user_id
- [ ] DATABASE_URL=sqlite+aiosqlite:///bot.db
- [ ] LOG_LEVEL=INFO
- [ ] ENABLE_DASHBOARD=true
- [ ] DASHBOARD_HOST=0.0.0.0
- [ ] DASHBOARD_PORT=5000
- [ ] DASHBOARD_SECRET_KEY=<generate_random_key>
```

### 7. Generate Secret Key
```bash
- [ ] python3 -c "import secrets; print(secrets.token_hex(32))"
- [ ] # Copy output to DASHBOARD_SECRET_KEY in .env
```

---

## 🧪 Testing Checklist

### Local Testing
```bash
- [ ] python3 bot.py  # Test bot starts
- [ ] # Check for errors in console
- [ ] # Verify bot appears online in Discord
- [ ] # Test a few commands in Discord
- [ ] Ctrl+C  # Stop bot
```

### Web Dashboard Testing
```bash
- [ ] ./start_with_web.sh  # Start with dashboard
- [ ] # Open browser: http://localhost:5000
- [ ] # Login with admin/admin
- [ ] # Verify dashboard loads
- [ ] # Check all pages work
- [ ] # Verify real-time updates
- [ ] Ctrl+C  # Stop bot
```

### Command Testing
In Discord, test these commands:
```
- [ ] /wan  # Bot dashboard
- [ ] /help  # Help command
- [ ] /serverinfo  # Server info
- [ ] /play test  # Music (if FFmpeg installed)
- [ ] /balance  # Economy
- [ ] /ai Hello  # AI features
```

---

## 🔒 Security Checklist

### Change Default Credentials
- [ ] Edit `web_dashboard.py` line ~60
- [ ] Change default password from 'admin'
- [ ] Use strong password (12+ characters)
- [ ] Consider implementing password hashing

### Secure Environment File
```bash
- [ ] chmod 600 .env  # Restrict permissions
- [ ] # Verify .env is in .gitignore
- [ ] # Never commit .env to git
```

### Firewall Configuration
```bash
- [ ] sudo ufw status  # Check firewall
- [ ] sudo ufw allow 5000  # Allow dashboard port
- [ ] # Or restrict to specific IP:
- [ ] sudo ufw allow from YOUR_IP to any port 5000
```

### HTTPS Setup (Production)
- [ ] Install Nginx or Apache
- [ ] Obtain SSL certificate (Let's Encrypt)
- [ ] Configure reverse proxy
- [ ] Test HTTPS access
- [ ] Redirect HTTP to HTTPS

---

## ⚡ 24/7 Deployment Checklist

### Choose Deployment Method
Select ONE method:
- [ ] Systemd (Linux - Recommended)
- [ ] PM2 (Easy management)
- [ ] Docker (Containerized)
- [ ] Screen/Tmux (Simple)

### Method 1: Systemd (Linux)

**Setup:**
```bash
- [ ] nano wanbot.service  # Edit paths
- [ ] # Update User, WorkingDirectory, ExecStart paths
- [ ] sudo cp wanbot.service /etc/systemd/system/
- [ ] sudo systemctl daemon-reload
- [ ] sudo systemctl enable wanbot
- [ ] sudo systemctl start wanbot
```

**Verify:**
```bash
- [ ] sudo systemctl status wanbot  # Check status
- [ ] sudo journalctl -u wanbot -f  # Check logs
- [ ] # Verify bot is online in Discord
- [ ] # Access dashboard: http://your-server-ip:5000
```

### Method 2: PM2

**Setup:**
```bash
- [ ] npm install -g pm2
- [ ] pm2 start ecosystem.config.js
- [ ] pm2 save
- [ ] pm2 startup  # Follow instructions
```

**Verify:**
```bash
- [ ] pm2 status  # Check status
- [ ] pm2 logs wanbot  # Check logs
- [ ] pm2 monit  # Monitor resources
```

### Method 3: Docker

**Setup:**
```bash
- [ ] docker-compose up -d
```

**Verify:**
```bash
- [ ] docker-compose ps  # Check status
- [ ] docker-compose logs -f  # Check logs
```

### Method 4: Screen/Tmux

**Setup:**
```bash
- [ ] screen -S wanbot  # or tmux new -s wanbot
- [ ] ./start_with_web.sh
- [ ] # Detach: Ctrl+A then D (screen) or Ctrl+B then D (tmux)
```

**Verify:**
```bash
- [ ] screen -ls  # or tmux ls
- [ ] # Verify bot is running
```

---

## 📊 Monitoring Checklist

### Setup Monitoring
- [ ] Configure log rotation
- [ ] Set up health checks
- [ ] Configure backup automation
- [ ] Set up alerts (optional)

### Log Rotation
```bash
- [ ] sudo nano /etc/logrotate.d/wanbot
- [ ] # Add log rotation config
- [ ] sudo logrotate -f /etc/logrotate.d/wanbot
```

### Health Check Script
```bash
- [ ] Create health_check.sh
- [ ] chmod +x health_check.sh
- [ ] Test health check
- [ ] Add to crontab: */5 * * * * /path/to/health_check.sh
```

### Backup Script
```bash
- [ ] Create backup.sh
- [ ] chmod +x backup.sh
- [ ] Test backup
- [ ] Add to crontab: 0 2 * * * /path/to/backup.sh
```

---

## 🌐 Web Dashboard Checklist

### Access Configuration
- [ ] Verify DASHBOARD_HOST in .env
- [ ] Verify DASHBOARD_PORT in .env
- [ ] Test local access: http://localhost:5000
- [ ] Test remote access: http://server-ip:5000

### Security
- [ ] Change default password
- [ ] Configure HTTPS (production)
- [ ] Set up firewall rules
- [ ] Test authentication
- [ ] Verify session timeout

### Functionality
- [ ] Test all dashboard pages
- [ ] Verify real-time updates
- [ ] Test moderation tools
- [ ] Test music control
- [ ] Check analytics display
- [ ] Verify logs viewer

---

## 📝 Documentation Checklist

### Read Documentation
- [ ] README.md - Overview
- [ ] SETUP.md - Setup guide
- [ ] 24_7_DEPLOYMENT.md - Deployment guide
- [ ] QUICK_REFERENCE.md - Command reference
- [ ] PRODUCTION_GUIDE.md - Production tips

### Save Important Info
- [ ] Document your server IP
- [ ] Save dashboard URL
- [ ] Note deployment method used
- [ ] Save backup locations
- [ ] Document custom configurations

---

## 🧹 Cleanup Checklist

### Remove Unnecessary Files
```bash
- [ ] rm -rf __pycache__
- [ ] rm -rf venv  # If using system Python
- [ ] rm *.pyc
```

### Verify .gitignore
```bash
- [ ] cat .gitignore
- [ ] # Ensure .env is listed
- [ ] # Ensure bot.db is listed
- [ ] # Ensure logs are listed
```

---

## ✅ Final Verification Checklist

### Bot Status
- [ ] Bot shows as online in Discord
- [ ] Bot responds to commands
- [ ] No errors in logs
- [ ] All features working

### Web Dashboard
- [ ] Dashboard accessible
- [ ] Login works
- [ ] All pages load
- [ ] Real-time updates working
- [ ] No console errors

### 24/7 Operation
- [ ] Bot auto-starts on server reboot
- [ ] Bot auto-restarts on crash
- [ ] Logs are being written
- [ ] Backups are working
- [ ] Health checks running

### Performance
- [ ] CPU usage acceptable (<50%)
- [ ] Memory usage acceptable (<500MB)
- [ ] Disk space sufficient (>500MB free)
- [ ] Network latency good (<100ms)

### Security
- [ ] Default password changed
- [ ] Firewall configured
- [ ] HTTPS enabled (production)
- [ ] .env file secured
- [ ] Logs protected

---

## 🎉 Post-Deployment Checklist

### Announce to Community
- [ ] Announce bot is live
- [ ] Share command list
- [ ] Share dashboard URL (if public)
- [ ] Provide support channel

### Monitor First 24 Hours
- [ ] Check logs regularly
- [ ] Monitor resource usage
- [ ] Watch for errors
- [ ] Test all major features
- [ ] Gather user feedback

### Setup Maintenance Schedule
- [ ] Weekly log review
- [ ] Weekly backup verification
- [ ] Monthly dependency updates
- [ ] Monthly security review
- [ ] Quarterly feature review

---

## 🆘 Troubleshooting Checklist

### If Bot Won't Start
- [ ] Check logs: `tail -f bot.log`
- [ ] Verify .env file exists
- [ ] Check DISCORD_TOKEN is valid
- [ ] Verify all dependencies installed
- [ ] Check Python version (3.8+)

### If Dashboard Won't Load
- [ ] Check bot is running
- [ ] Verify port 5000 is open
- [ ] Check firewall rules
- [ ] Verify DASHBOARD_HOST setting
- [ ] Check browser console for errors

### If Bot Keeps Crashing
- [ ] Check error logs
- [ ] Verify sufficient memory
- [ ] Check disk space
- [ ] Review recent changes
- [ ] Test with minimal config

### If Commands Don't Work
- [ ] Verify bot has permissions
- [ ] Check command syntax
- [ ] Review bot logs
- [ ] Test with /help command
- [ ] Verify bot is in server

---

## 📞 Support Resources

### Documentation
- [ ] Review all .md files in project
- [ ] Check 24_7_DEPLOYMENT.md for details
- [ ] Read TROUBLESHOOTING section

### Commands
```bash
# Status
- [ ] sudo systemctl status wanbot
- [ ] pm2 status

# Logs
- [ ] tail -f bot.log
- [ ] sudo journalctl -u wanbot -f
- [ ] pm2 logs wanbot

# Restart
- [ ] sudo systemctl restart wanbot
- [ ] pm2 restart wanbot
```

---

## 🎯 Success Criteria

Your deployment is successful when:
- ✅ Bot is online 24/7
- ✅ All commands work
- ✅ Web dashboard accessible
- ✅ No errors in logs
- ✅ Auto-restart working
- ✅ Backups running
- ✅ Security configured
- ✅ Performance acceptable
- ✅ Community satisfied

---

## 🎊 Congratulations!

If you've completed all items in this checklist, your WAN Bot is successfully deployed and running 24/7 with complete web control!

**Your bot is now:**
- ✅ Running 24/7 automatically
- ✅ Accessible via web dashboard
- ✅ Secured and protected
- ✅ Monitored and backed up
- ✅ Production ready

**Enjoy your ultimate Discord bot!** 🚀🤖🌐

---

*For detailed help, see [24_7_DEPLOYMENT.md](24_7_DEPLOYMENT.md)*
