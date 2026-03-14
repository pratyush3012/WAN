# 🚀 WAN Bot - 24/7 Deployment & Web Dashboard Guide

Complete guide for running WAN Bot 24/7 with full web dashboard control.

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Web Dashboard Setup](#web-dashboard-setup)
3. [24/7 Running Methods](#247-running-methods)
4. [Security Configuration](#security-configuration)
5. [Monitoring & Maintenance](#monitoring--maintenance)
6. [Troubleshooting](#troubleshooting)

---

## 🎯 Quick Start

### Prerequisites
- Python 3.8 or higher
- Virtual environment (recommended)
- Discord bot token
- Server with internet connection (for 24/7 hosting)

### Basic Setup

```bash
# 1. Clone and setup
git clone <your-repo>
cd wanbot
./setup.sh

# 2. Configure environment
cp .env.example .env
nano .env  # Add your DISCORD_TOKEN and OWNER_ID

# 3. Start with web dashboard
./start_with_web.sh
```

The bot will start and the web dashboard will be available at `http://localhost:5000`

---

## 🌐 Web Dashboard Setup

### Configuration

Edit your `.env` file:

```env
# Web Dashboard Configuration
ENABLE_DASHBOARD=true          # Enable/disable dashboard
DASHBOARD_HOST=0.0.0.0        # 0.0.0.0 for all interfaces, 127.0.0.1 for local only
DASHBOARD_PORT=5000           # Port for web dashboard
DASHBOARD_SECRET_KEY=your_random_secret_key_here  # Generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Accessing the Dashboard

**Local Access:**
```
http://localhost:5000
```

**Remote Access (if hosted on server):**
```
http://your-server-ip:5000
```

**Default Login:**
- Username: `admin`
- Password: `admin`

⚠️ **IMPORTANT**: Change the default password in `web_dashboard.py` before production use!

### Dashboard Features

✅ **Real-time Server Monitoring**
- Live bot status and statistics
- Server list with member counts
- Latency and uptime tracking

✅ **Server Management**
- View all servers the bot is in
- Detailed server information
- Channel and role management
- Member list and activity

✅ **Moderation Tools**
- Kick/ban members from web interface
- View moderation logs
- Bulk actions (message purge, cleanup)

✅ **Music Control**
- Control music playback remotely
- View current queue
- Manage playlists

✅ **Analytics Dashboard**
- Member growth charts
- Activity metrics
- Engagement statistics

✅ **Live Logs**
- Real-time bot logs
- Error tracking
- Activity feed

---

## ⚡ 24/7 Running Methods

### Method 1: Systemd Service (Linux - Recommended)

Best for: VPS, dedicated servers, Linux systems

**Setup:**

1. Edit the service file:
```bash
nano wanbot.service
```

2. Update these paths:
```ini
User=YOUR_USERNAME                          # Your Linux username
WorkingDirectory=/path/to/wanbot           # Full path to bot directory
Environment="PATH=/path/to/wanbot/venv/bin"
ExecStart=/path/to/wanbot/venv/bin/python3 bot.py
ReadWritePaths=/path/to/wanbot
```

3. Install the service:
```bash
# Copy service file
sudo cp wanbot.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable wanbot

# Start service
sudo systemctl start wanbot
```

**Management Commands:**
```bash
# Check status
sudo systemctl status wanbot

# View logs
sudo journalctl -u wanbot -f

# Restart
sudo systemctl restart wanbot

# Stop
sudo systemctl stop wanbot

# Disable auto-start
sudo systemctl disable wanbot
```

---

### Method 2: PM2 Process Manager

Best for: Easy management, auto-restart, monitoring

**Setup:**

1. Install PM2:
```bash
npm install -g pm2
```

2. Start the bot:
```bash
pm2 start ecosystem.config.js
```

**Management Commands:**
```bash
# Monitor all processes
pm2 monit

# View logs
pm2 logs wanbot

# Restart
pm2 restart wanbot

# Stop
pm2 stop wanbot

# Delete from PM2
pm2 delete wanbot

# Save PM2 configuration
pm2 save

# Setup auto-start on boot
pm2 startup
# Follow the instructions shown
```

**PM2 Dashboard:**
```bash
# Install PM2 web dashboard
pm2 install pm2-server-monit

# Access at http://localhost:9615
```

---

### Method 3: Screen/Tmux (Simple)

Best for: Quick testing, temporary hosting

**Using Screen:**
```bash
# Start new screen session
screen -S wanbot

# Run bot
./start_with_web.sh

# Detach: Press Ctrl+A then D

# Reattach
screen -r wanbot

# List sessions
screen -ls
```

**Using Tmux:**
```bash
# Start new tmux session
tmux new -s wanbot

# Run bot
./start_with_web.sh

# Detach: Press Ctrl+B then D

# Reattach
tmux attach -t wanbot

# List sessions
tmux ls
```

---

### Method 4: Docker (Containerized)

Best for: Isolated environment, easy deployment

**Using Docker Compose:**
```bash
# Start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Restart
docker-compose restart
```

---

## 🔒 Security Configuration

### 1. Change Default Credentials

Edit `web_dashboard.py`:
```python
# Find this line and change credentials
if username == 'admin' and password == 'admin':  # Change this!
```

Better: Implement proper authentication with password hashing:
```python
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Store hashed passwords
ADMIN_USERS = {
    'admin': hash_password('your_secure_password')
}
```

### 2. Use HTTPS (Production)

Use a reverse proxy like Nginx:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### 3. Firewall Configuration

```bash
# Allow only specific IPs to access dashboard
sudo ufw allow from YOUR_IP to any port 5000

# Or use SSH tunnel
ssh -L 5000:localhost:5000 user@your-server
# Then access at http://localhost:5000 on your local machine
```

### 4. Environment Variables

Never commit `.env` file! Keep sensitive data secure:
```bash
# Set restrictive permissions
chmod 600 .env

# Add to .gitignore
echo ".env" >> .gitignore
```

---

## 📊 Monitoring & Maintenance

### Health Checks

Create a monitoring script:
```bash
#!/bin/bash
# health_check.sh

# Check if bot is running
if ! pgrep -f "python3 bot.py" > /dev/null; then
    echo "Bot is down! Restarting..."
    systemctl restart wanbot
    # Send alert (email, Discord webhook, etc.)
fi

# Check dashboard
if ! curl -s http://localhost:5000 > /dev/null; then
    echo "Dashboard is down!"
fi
```

Add to crontab:
```bash
# Check every 5 minutes
*/5 * * * * /path/to/health_check.sh
```

### Log Rotation

Prevent logs from filling disk:
```bash
# Create logrotate config
sudo nano /etc/logrotate.d/wanbot
```

```
/path/to/wanbot/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 username username
}
```

### Backup Strategy

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup database
cp bot.db "$BACKUP_DIR/bot_$DATE.db"

# Backup configuration
cp .env "$BACKUP_DIR/env_$DATE.bak"

# Keep only last 7 days
find "$BACKUP_DIR" -name "bot_*.db" -mtime +7 -delete
```

---

## 🔧 Troubleshooting

### Bot Won't Start

**Check logs:**
```bash
tail -f bot.log
tail -f bot_error.log
```

**Common issues:**
- Missing DISCORD_TOKEN in .env
- Invalid token
- Missing dependencies: `pip install -r requirements.txt`
- Port 5000 already in use: Change DASHBOARD_PORT in .env

### Dashboard Not Accessible

**Check if running:**
```bash
netstat -tulpn | grep 5000
# or
lsof -i :5000
```

**Firewall blocking:**
```bash
# Allow port 5000
sudo ufw allow 5000
```

**Wrong host binding:**
- Use `0.0.0.0` to allow external access
- Use `127.0.0.1` for local only

### High Memory Usage

**Check memory:**
```bash
ps aux | grep python3
```

**Solutions:**
- Restart bot regularly (cron job)
- Limit cache size in code
- Use PM2 with max_memory_restart

### Bot Keeps Crashing

**Enable auto-restart:**
- Systemd: Already configured with `Restart=always`
- PM2: Already configured with `autorestart: true`
- Screen/Tmux: Use a wrapper script with loop

**Wrapper script:**
```bash
#!/bin/bash
while true; do
    python3 bot.py
    echo "Bot crashed! Restarting in 10 seconds..."
    sleep 10
done
```

---

## 🌟 Best Practices

### Production Checklist

- [ ] Change default dashboard credentials
- [ ] Set strong DASHBOARD_SECRET_KEY
- [ ] Enable HTTPS with reverse proxy
- [ ] Configure firewall rules
- [ ] Set up log rotation
- [ ] Implement automated backups
- [ ] Configure health monitoring
- [ ] Set up alerts (Discord webhook, email)
- [ ] Document your configuration
- [ ] Test disaster recovery

### Performance Optimization

1. **Use Redis for caching** (optional):
```bash
pip install redis
```

2. **Enable uvloop** (already in requirements):
```python
# Automatically used on Linux
```

3. **Database optimization**:
```bash
# Regular vacuum for SQLite
sqlite3 bot.db "VACUUM;"
```

4. **Monitor resource usage**:
```bash
# Install monitoring tools
pip install prometheus-client
```

---

## 📞 Support

### Getting Help

1. Check logs: `tail -f bot.log`
2. Review this guide
3. Check Discord.py documentation
4. Open an issue on GitHub

### Useful Commands

```bash
# Check bot status
systemctl status wanbot

# View real-time logs
journalctl -u wanbot -f

# Check disk space
df -h

# Check memory
free -h

# Check CPU
top

# Network connections
netstat -tulpn

# Process list
ps aux | grep python
```

---

## 🎉 Success!

Your WAN Bot is now running 24/7 with full web dashboard control!

**Access your dashboard:**
- Local: http://localhost:5000
- Remote: http://your-server-ip:5000

**Monitor your bot:**
- Dashboard: Real-time statistics
- Logs: `tail -f bot.log`
- Systemd: `systemctl status wanbot`
- PM2: `pm2 monit`

---

**WAN Bot - The Ultimate Discord Bot - Running 24/7 with Complete Web Control!** 🚀🤖🌐
