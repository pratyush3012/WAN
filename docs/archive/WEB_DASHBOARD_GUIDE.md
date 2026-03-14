# 🌐 WAN Bot - Web Dashboard Guide

**Access your Discord bot through a beautiful web interface!**

---

## 🚀 Quick Start

### 1. Install Web Dashboard Dependencies

```bash
pip install flask flask-cors
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

### 2. Start the Bot (Web Dashboard Auto-Starts)

```bash
python3 bot.py
```

The web dashboard will automatically start when the bot starts!

### 3. Access the Dashboard

Open your web browser and go to:
```
http://localhost:5000
```

---

## 🎨 Web Dashboard Features

### 📊 Real-Time Statistics
- **Server Count**: Number of Discord servers using your bot
- **User Count**: Total users across all servers
- **Command Count**: 250+ available commands
- **Bot Status**: Online/Offline status with live updates

### 🏠 Home Page
- Beautiful hero section with bot overview
- Real-time statistics dashboard
- Feature showcase with all bot capabilities
- Comparison table vs premium bots

### 📈 Dashboard Page
- Server management interface
- Quick access to bot controls
- Real-time analytics and metrics

### ⚡ Commands Page
- Complete command list organized by category
- Search and filter commands
- Command descriptions and usage examples

### 📊 Analytics Page
- Detailed server analytics
- User engagement metrics
- Growth tracking and predictions

### ⚙️ Settings Page
- Bot configuration options
- Server-specific settings
- Feature toggles

---

## 🌐 Accessing from Different Devices

### Local Access (Same Computer)
```
http://localhost:5000
```

### Network Access (Other Devices on Same Network)

1. Find your computer's IP address:

**macOS/Linux**:
```bash
ifconfig | grep "inet "
```

**Windows**:
```bash
ipconfig
```

2. Access from other devices:
```
http://YOUR_IP_ADDRESS:5000
```

Example: `http://192.168.1.100:5000`

### Public Access (Internet)

To access from anywhere on the internet, you need to:

1. **Port Forward** port 5000 on your router
2. **Use your public IP** or set up a domain name
3. **Add HTTPS** for security (recommended)

**Security Warning**: Only expose to the internet if you add proper authentication!

---

## 🔧 Configuration

### Change Port

Edit `web_dashboard.py`:
```python
# Change port from 5000 to your preferred port
run_web_dashboard(host='0.0.0.0', port=8080)
```

### Change Host

```python
# Listen only on localhost (more secure)
run_web_dashboard(host='127.0.0.1', port=5000)

# Listen on all interfaces (accessible from network)
run_web_dashboard(host='0.0.0.0', port=5000)
```

---

## 📱 Mobile Access

The web dashboard is fully responsive and works great on mobile devices!

1. Connect your phone to the same WiFi network
2. Open browser on your phone
3. Go to `http://YOUR_COMPUTER_IP:5000`

---

## 🎨 Customization

### Change Colors

Edit `static/css/style.css`:
```css
/* Change primary gradient */
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

/* Change to your colors */
background: linear-gradient(135deg, #YOUR_COLOR1 0%, #YOUR_COLOR2 100%);
```

### Add Custom Pages

1. Create HTML template in `templates/`
2. Add route in `web_dashboard.py`:
```python
@app.route('/mypage')
def my_page():
    return render_template('mypage.html')
```

---

## 🔒 Security Best Practices

### For Local Use Only
```python
# In web_dashboard.py
run_web_dashboard(host='127.0.0.1', port=5000)
```

### For Network Use
1. Use strong passwords (add authentication)
2. Use HTTPS instead of HTTP
3. Limit access by IP address
4. Keep software updated

### Add Authentication (Recommended)

Install Flask-Login:
```bash
pip install flask-login
```

Add to `web_dashboard.py`:
```python
from flask_login import LoginManager, login_required

# Protect routes
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')
```

---

## 🐛 Troubleshooting

### Dashboard Won't Start

**Error**: `Address already in use`
**Solution**: Port 5000 is already in use. Change to different port:
```python
run_web_dashboard(host='0.0.0.0', port=8080)
```

### Can't Access from Other Devices

**Problem**: Dashboard only accessible on localhost
**Solution**: Change host to `0.0.0.0`:
```python
run_web_dashboard(host='0.0.0.0', port=5000)
```

### Stats Not Updating

**Problem**: Statistics show 0 or don't update
**Solution**: 
1. Make sure bot is running
2. Check browser console for errors (F12)
3. Verify `/api/stats` endpoint works: `http://localhost:5000/api/stats`

### Page Not Loading

**Problem**: White screen or 404 error
**Solution**:
1. Check that `templates/` and `static/` folders exist
2. Verify HTML files are in `templates/`
3. Check browser console for errors

---

## 📊 API Endpoints

The dashboard provides REST API endpoints:

### Get Bot Statistics
```
GET /api/stats
```

Response:
```json
{
  "guilds": 10,
  "users": 5000,
  "commands": 250,
  "uptime": "2h 30m 15s",
  "status": "online"
}
```

### Get Guild List
```
GET /api/guilds
```

Response:
```json
[
  {
    "id": 123456789,
    "name": "My Server",
    "members": 500,
    "icon": "https://..."
  }
]
```

### Get Commands List
```
GET /api/commands
```

Response:
```json
{
  "Music": ["play", "pause", "skip", ...],
  "AI": ["ai", "ai-image", ...],
  ...
}
```

---

## 🚀 Advanced Features

### Auto-Start on System Boot

**macOS/Linux** - Create systemd service:
```bash
sudo nano /etc/systemd/system/wanbot.service
```

Add:
```ini
[Unit]
Description=WAN Bot with Web Dashboard
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/bot
ExecStart=/usr/bin/python3 bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl enable wanbot
sudo systemctl start wanbot
```

### Reverse Proxy with Nginx

For production deployment with custom domain:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Docker Deployment

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000
CMD ["python3", "bot.py"]
```

Run:
```bash
docker build -t wanbot .
docker run -p 5000:5000 wanbot
```

---

## 📱 Progressive Web App (PWA)

The dashboard can be installed as a mobile app!

1. Open dashboard in mobile browser
2. Tap "Add to Home Screen"
3. Access like a native app

---

## 🎉 Features Overview

### What You Can Do
✅ **Monitor bot status** in real-time
✅ **View server statistics** and analytics
✅ **Browse all commands** with search
✅ **Check bot health** and performance
✅ **Access from any device** (phone, tablet, computer)
✅ **Beautiful responsive design** that works everywhere
✅ **Real-time updates** every 5 seconds
✅ **API access** for custom integrations

### Coming Soon
🔜 **Server management** - Manage servers from web
🔜 **Command execution** - Run commands from dashboard
🔜 **User authentication** - Secure login system
🔜 **Advanced analytics** - Detailed charts and graphs
🔜 **Configuration editor** - Edit bot settings
🔜 **Log viewer** - View bot logs in real-time

---

## 💡 Tips & Tricks

### Bookmark the Dashboard
Add `http://localhost:5000` to your browser bookmarks for quick access!

### Use Multiple Tabs
Open different pages in separate tabs:
- Tab 1: Dashboard (real-time stats)
- Tab 2: Commands (reference)
- Tab 3: Analytics (insights)

### Mobile Widget
On iOS/Android, add dashboard to home screen for app-like experience!

### Keyboard Shortcuts
- `Ctrl/Cmd + R` - Refresh page
- `F12` - Open developer tools
- `Ctrl/Cmd + F` - Search on page

---

## 🆘 Support

### Need Help?
1. Check this guide first
2. Review `CHANGELOG.md` for updates
3. Check `STATUS.md` for known issues
4. Review bot logs in `bot.log`

### Common Issues
- **Port in use**: Change port in `web_dashboard.py`
- **Can't connect**: Check firewall settings
- **Stats not showing**: Ensure bot is running
- **Page not loading**: Clear browser cache

---

## 🎨 Screenshots

### Home Page
Beautiful landing page with bot overview and real-time statistics

### Dashboard
Comprehensive control panel with server management

### Commands
Complete command list with search and categories

### Analytics
Detailed insights and growth metrics

---

## 🚀 Quick Commands

```bash
# Start bot with web dashboard
python3 bot.py

# Access dashboard
open http://localhost:5000

# Check if dashboard is running
curl http://localhost:5000/api/stats

# View dashboard logs
tail -f bot.log | grep "Web Dashboard"
```

---

## 🎉 Enjoy Your Web Dashboard!

You now have a beautiful web interface to manage your Discord bot!

**Access it at**: `http://localhost:5000`

**Features**: Real-time stats, command browser, analytics, and more!

**Mobile Friendly**: Works perfectly on phones and tablets!

---

*WAN Bot - The Ultimate Discord Bot with Beautiful Web Dashboard!* 🌐✨🚀