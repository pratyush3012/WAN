# 🎬 Watch Party Quick Reference

## Role Permissions at a Glance

| Feature | Guest | Member | Mod | Admin | Owner |
|---------|:-----:|:------:|:---:|:-----:|:-----:|
| **Watch Video** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **See Chat** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Send Messages** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Use Reactions** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Play/Pause** | ❌ | ❌ | ✅ | ✅ | ✅ |
| **Skip/Seek** | ❌ | ❌ | ✅ | ✅ | ✅ |
| **Manage Settings** | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Create/Delete** | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Space` | Play/Pause |
| `←` | Skip back 10s |
| `→` | Skip forward 10s |
| `F` | Fullscreen |
| `M` | Mute/Unmute |
| `+` | Volume up |
| `-` | Volume down |

---

## Storage Limits

```
Max file size:     10 GB
Max concurrent:    3 uploads
Auto-cleanup:      24 hours
Supported formats: MP4, WebM, MKV, MOV, AVI, M4V
```

---

## Chat Limits

```
Max message:       500 characters
Rate limit:        10 messages/minute
History stored:    200 messages
Guests can chat:   NO
```

---

## Configuration Quick Start

### Environment Variables

```bash
# .env file
WATCH_PARTY_UPLOAD_DIR=./uploads/watch_party
WATCH_PARTY_MAX_MB=10240
WATCH_PARTY_CLEANUP_HOURS=24
WATCH_PARTY_LOG_LEVEL=INFO
```

### Python Config

```python
# watch_party_config.py
MAX_UPLOAD_MB = 10240
ALLOWED_VIDEO_EXTS = [".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"]
SYNC_INTERVAL_SECONDS = 30
MAX_CHAT_LENGTH = 500
GUEST_CHAT_ENABLED = False
```

---

## API Endpoints

```
GET    /api/watch/list/<server_id>
POST   /api/watch/create/<server_id>
POST   /api/watch/upload/<server_id>
GET    /api/watch/stream/<room_id>
GET    /api/watch/<room_id>
POST   /api/watch/<room_id>/close
GET    /watch/<room_id>
```

---

## Socket.IO Events

### Emit (Client → Server)

```javascript
socket.emit("watch_join", {room_id, username, user_id})
socket.emit("watch_leave", {room_id})
socket.emit("watch_play", {room_id, current_time})
socket.emit("watch_pause", {room_id, current_time})
socket.emit("watch_seek", {room_id, current_time})
socket.emit("watch_chat", {room_id, message, username})
socket.emit("watch_request_sync", {room_id})
```

### Listen (Server → Client)

```javascript
socket.on("watch_state", data)
socket.on("watch_sync", data)
socket.on("watch_chat_msg", data)
socket.on("viewer_joined", data)
socket.on("viewer_left", data)
socket.on("room_closed", data)
socket.on("error", data)
```

---

## Common Tasks

### Create Watch Party

```bash
curl -X POST http://localhost:5000/api/watch/create/123456789 \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Movie Night",
    "video_url": "https://example.com/video.mp4"
  }'
```

### Upload Video

```bash
curl -X POST http://localhost:5000/api/watch/upload/123456789 \
  -F "file=@movie.mp4" \
  -F "title=Movie Night"
```

### Check Storage

```python
from watch_party_config import get_storage_info
info = get_storage_info()
print(f"Free: {info['free_gb']:.1f}GB")
```

### Get User Role

```python
from web_dashboard_enhanced import _get_user_role_level
role = _get_user_role_level(guild_id=123, user_id=456)
# 0=Guest, 1=Member, 2=Mod, 3=Admin, 4=Owner
```

---

## Troubleshooting

### Video Won't Play
- Check format (MP4, WebM, MKV, MOV, AVI, M4V)
- Verify file < 10GB
- Try refreshing page

### Out of Sync
- Click sync button (↻)
- Refresh page
- Check internet connection

### Can't Send Messages
- Check role (need Member+)
- Verify not muted
- Try refreshing

### Controls Disabled
- Check role (need Mod+)
- Verify not a guest
- Ask mod to promote

### Disk Space Low
- Check: `df -h`
- Cleanup: `rm uploads/watch_party/*`
- Increase: `WATCH_PARTY_MAX_MB`

---

## Performance Tips

### For High Viewers (100+)

```python
CHUNK_SIZE = 131072  # 128KB
SYNC_INTERVAL_SECONDS = 60
```

### For Low Bandwidth

```python
CHUNK_SIZE = 32768  # 32KB
SYNC_INTERVAL_SECONDS = 15
```

### For High Latency

```python
SYNC_TOLERANCE_SECONDS = 2.5
STREAM_TIMEOUT = 60
```

---

## Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| "Room not found" | Invalid room_id | Check room exists |
| "Access denied" | Missing role | Join with role |
| "Only mods can control" | Insufficient perms | Ask mod to promote |
| "Guests cannot chat" | Guest trying to chat | Join with role |
| "File too large" | Exceeds 10GB | Split file or use URL |
| "Rate limit exceeded" | Too many messages | Wait before sending |

---

## Files Reference

| File | Purpose |
|------|---------|
| `watch_party_config.py` | Configuration & settings |
| `web_dashboard_enhanced.py` | Backend implementation |
| `templates/watch_party.html` | Frontend UI |
| `WATCH_PARTY_GUIDE.md` | User guide |
| `WATCH_PARTY_SETUP.md` | Setup instructions |
| `WATCH_PARTY_API.md` | API documentation |

---

## Role Hierarchy

```
Owner (4)
  ├─ Admin (3)
  │   ├─ Mod (2)
  │   │   ├─ Member (1)
  │   │   │   └─ Guest (0)
```

**Permissions increase with role level**

---

## Sync Behavior

```
Auto-sync every 30 seconds
If difference > 1.5 seconds → Force sync
Manual sync available via button
Server calculates playback position
```

---

## Chat Features

```
✅ Emoji reactions (6 types)
✅ Message history (200 messages)
✅ Timestamps
✅ User avatars
✅ Rate limiting (10/min)
✅ XSS protection
❌ Guests cannot send
```

---

## Deployment Checklist

- [ ] Install: `pip install flask-socketio`
- [ ] Create: `mkdir -p uploads/watch_party`
- [ ] Configure: `.env` file
- [ ] Import: `watch_party_config.py`
- [ ] Register: Socket.IO handlers
- [ ] Register: Flask routes
- [ ] Test: Upload & stream
- [ ] Monitor: Disk space
- [ ] Backup: Configuration
- [ ] Document: For team

---

## Support Resources

- **User Guide**: `WATCH_PARTY_GUIDE.md`
- **Setup Guide**: `WATCH_PARTY_SETUP.md`
- **API Docs**: `WATCH_PARTY_API.md`
- **Config**: `watch_party_config.py`
- **Logs**: `./logs/watch_party.log`

---

## Quick Stats

```
Max file size:        10 GB
Max concurrent:       500 viewers
Typical latency:      <500ms
CPU per party:        <5%
Memory per party:     ~50MB
Bandwidth per viewer: ~5Mbps (1080p)
```

---

**Need help?** Check the full guides or contact your server admin! 🎬
