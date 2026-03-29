# 🎬 Watch Party Setup Guide

## Prerequisites

- Python 3.8+
- Flask with Socket.IO
- 10GB+ free disk space
- Discord.py bot with proper permissions

## Installation

### 1. Install Dependencies

```bash
pip install flask-socketio python-socketio python-engineio
```

### 2. Create Upload Directory

```bash
mkdir -p uploads/watch_party
chmod 755 uploads/watch_party
```

### 3. Configure Environment Variables

Create or update your `.env` file:

```env
# Watch Party Settings
WATCH_PARTY_UPLOAD_DIR=./uploads/watch_party
WATCH_PARTY_MAX_MB=10240          # 10GB max file size
WATCH_PARTY_CLEANUP_HOURS=24      # Delete videos after 24 hours
WATCH_PARTY_LOG_LEVEL=INFO

# Storage (optional)
WATCH_PARTY_MIN_FREE_GB=5         # Minimum free space required
```

### 4. Import Configuration

In your `web_dashboard_enhanced.py`, add:

```python
from watch_party_config import (
    UPLOAD_FOLDER, MAX_UPLOAD_MB, ALLOWED_VIDEO_EXTS,
    ROLE_PERMISSIONS, can_perform_action, get_storage_info
)
```

### 5. Enable Socket.IO Events

Ensure these Socket.IO event handlers are registered:

```python
@socketio.on("watch_join")
@socketio.on("watch_leave")
@socketio.on("watch_play")
@socketio.on("watch_pause")
@socketio.on("watch_seek")
@socketio.on("watch_chat")
@socketio.on("watch_request_sync")
```

### 6. Add Routes

Ensure these Flask routes are registered:

```python
@app.route("/api/watch/list/<server_id>")
@app.route("/api/watch/create/<server_id>", methods=["POST"])
@app.route("/api/watch/upload/<server_id>", methods=["POST"])
@app.route("/api/watch/stream/<room_id>")
@app.route("/api/watch/<room_id>")
@app.route("/api/watch/<room_id>/close", methods=["POST"])
@app.route("/watch/<room_id>")
```

## Configuration

### Storage Settings

Edit `watch_party_config.py`:

```python
# Maximum file size (in MB)
MAX_UPLOAD_MB = 10240  # 10GB

# Upload directory
UPLOAD_FOLDER = "./uploads/watch_party"

# Auto-cleanup after (hours)
VIDEO_CLEANUP_HOURS = 24

# Allowed formats
ALLOWED_VIDEO_EXTS = [".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"]
```

### Role Permissions

Customize role permissions in `watch_party_config.py`:

```python
ROLE_PERMISSIONS = {
    0: {"watch": True, "chat": False, "control": False},  # Guest
    1: {"watch": True, "chat": True, "control": False},   # Member
    2: {"watch": True, "chat": True, "control": True},    # Mod
    3: {"watch": True, "chat": True, "control": True},    # Admin
    4: {"watch": True, "chat": True, "control": True},    # Owner
}
```

### Chat Settings

```python
MAX_CHAT_LENGTH = 500          # Max message length
MAX_CHAT_HISTORY = 200         # Messages to keep
CHAT_RATE_LIMIT = 10           # Messages per minute
GUEST_CHAT_ENABLED = False     # Allow guests to chat
```

## Disk Space Management

### Check Available Space

```python
from watch_party_config import get_storage_info

info = get_storage_info()
print(f"Free: {info['free_gb']:.1f}GB")
print(f"Used: {info['used_gb']:.1f}GB")
print(f"Total: {info['total_gb']:.1f}GB")
```

### Monitor Storage

Add to your monitoring script:

```python
import os
import shutil

def check_storage():
    stat = shutil.disk_usage(UPLOAD_FOLDER)
    free_gb = stat.free / (1024**3)
    
    if free_gb < 5:
        logger.warning(f"Low disk space: {free_gb:.1f}GB remaining")
        # Trigger cleanup or alert
    
    return free_gb

# Run periodically
schedule.every(1).hour.do(check_storage)
```

### Cleanup Old Videos

```python
import os
import time
from watch_party_config import UPLOAD_FOLDER, VIDEO_CLEANUP_HOURS

def cleanup_old_videos():
    """Remove videos older than VIDEO_CLEANUP_HOURS"""
    cutoff_time = time.time() - (VIDEO_CLEANUP_HOURS * 3600)
    
    for filename in os.listdir(UPLOAD_FOLDER):
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(filepath):
            if os.path.getmtime(filepath) < cutoff_time:
                try:
                    os.remove(filepath)
                    logger.info(f"Cleaned up: {filename}")
                except Exception as e:
                    logger.error(f"Failed to cleanup {filename}: {e}")

# Schedule cleanup
schedule.every(6).hours.do(cleanup_old_videos)
```

## Discord Bot Permissions

Ensure your bot has these permissions:

```
- Read Messages/View Channels
- Send Messages
- Embed Links
- Attach Files
- Read Message History
- Use External Emojis
- Add Reactions
```

## Testing

### Test Video Upload

```bash
curl -X POST http://localhost:5000/api/watch/upload/123456789 \
  -F "file=@test_video.mp4" \
  -F "title=Test Video"
```

### Test Video Streaming

```bash
curl -H "Range: bytes=0-1023" \
  http://localhost:5000/api/watch/stream/room_id
```

### Test Socket Connection

```javascript
const socket = io("http://localhost:5000");
socket.on("connect", () => {
  console.log("Connected!");
  socket.emit("watch_join", {
    room_id: "test_room",
    username: "Test User",
    user_id: "123"
  });
});
```

## Troubleshooting

### Issue: "File too large" error

**Solution**: Increase `MAX_UPLOAD_MB` in `.env`:
```env
WATCH_PARTY_MAX_MB=20480  # 20GB
```

### Issue: "Disk space low" warning

**Solution**: 
1. Check available space: `df -h`
2. Run cleanup: `python -c "from watch_party_config import cleanup_old_videos; cleanup_old_videos()"`
3. Delete old videos manually: `rm uploads/watch_party/*`

### Issue: Video won't play

**Solution**:
1. Check file format is supported (MP4, WebM, MKV, MOV, AVI, M4V)
2. Verify file is not corrupted: `ffprobe video.mp4`
3. Check MIME type: `file -i video.mp4`
4. Try re-uploading

### Issue: Out of sync playback

**Solution**:
1. Increase `SYNC_INTERVAL_SECONDS` to 15-20
2. Decrease `SYNC_TOLERANCE_SECONDS` to 1.0
3. Check network latency: `ping server`
4. Restart watch party

### Issue: Chat not working

**Solution**:
1. Verify Socket.IO is running: `curl http://localhost:5000/socket.io/`
2. Check browser console for errors
3. Verify user role level: `_get_user_role_level(guild_id, user_id)`
4. Check rate limiting: `CHAT_RATE_LIMIT`

### Issue: High CPU usage

**Solution**:
1. Reduce `MAX_CONCURRENT_VIEWERS`
2. Increase `CHUNK_SIZE` for streaming
3. Disable unnecessary features in `watch_party_config.py`
4. Monitor with: `top -p $(pgrep -f "python.*bot")`

## Performance Tuning

### For High Viewer Count (100+)

```python
# watch_party_config.py
CHUNK_SIZE = 131072  # 128KB chunks
BUFFER_SIZE = 2 * 1024 * 1024  # 2MB buffer
SYNC_INTERVAL_SECONDS = 60  # Sync less frequently
```

### For Low Bandwidth

```python
# watch_party_config.py
CHUNK_SIZE = 32768  # 32KB chunks
SYNC_INTERVAL_SECONDS = 15  # Sync more frequently
```

### For High Latency Networks

```python
# watch_party_config.py
SYNC_TOLERANCE_SECONDS = 2.5  # More tolerance
STREAM_TIMEOUT = 60  # Longer timeout
```

## Monitoring

### Log File Location

```
./logs/watch_party.log
```

### Enable Debug Logging

```env
WATCH_PARTY_LOG_LEVEL=DEBUG
```

### Monitor Active Watch Parties

```python
from web_dashboard_enhanced import _watch_rooms

for room_id, room in _watch_rooms.items():
    print(f"Room: {room_id}")
    print(f"  Title: {room.title}")
    print(f"  Viewers: {len(room.viewers)}")
    print(f"  Playing: {room.is_playing}")
    print(f"  Time: {room.sync_time():.1f}s")
```

## Backup & Recovery

### Backup Watch Party Data

```bash
# Backup uploaded videos
tar -czf watch_party_backup.tar.gz uploads/watch_party/

# Backup configuration
cp watch_party_config.py watch_party_config.backup.py
```

### Restore from Backup

```bash
# Restore videos
tar -xzf watch_party_backup.tar.gz

# Restore configuration
cp watch_party_config.backup.py watch_party_config.py
```

## Security Considerations

1. **File Validation**: Always validate file types and sizes
2. **Access Control**: Enforce role-based permissions
3. **Rate Limiting**: Prevent spam and abuse
4. **XSS Protection**: Sanitize chat messages
5. **CORS**: Configure CORS properly for Socket.IO
6. **HTTPS**: Use HTTPS in production
7. **Authentication**: Verify user identity before allowing access

## Production Deployment

### Recommended Setup

```
┌─────────────────┐
│   Discord Bot   │
└────────┬────────┘
         │
    ┌────▼────────────────┐
    │  Flask + Socket.IO   │
    │  (Watch Party)       │
    └────┬────────────────┘
         │
    ┌────▼──────────────────┐
    │  File Storage (10GB+)  │
    │  uploads/watch_party/  │
    └───────────────────────┘
```

### Nginx Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name watch.example.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /uploads/watch_party/ {
        alias /var/www/watch_party/uploads/watch_party/;
        expires 24h;
        add_header Cache-Control "public, max-age=86400";
    }
}
```

### Systemd Service

```ini
[Unit]
Description=WAN Bot Watch Party Service
After=network.target

[Service]
Type=simple
User=bot
WorkingDirectory=/opt/wan-bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Support & Documentation

- **Guide**: See `WATCH_PARTY_GUIDE.md`
- **Config**: See `watch_party_config.py`
- **Issues**: Check logs in `./logs/watch_party.log`
- **API**: See Socket.IO events in `web_dashboard_enhanced.py`

---

**Setup Complete!** 🎉 Your watch party feature is ready to use.
