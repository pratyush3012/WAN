# 🎬 Watch Party API Reference

## REST API Endpoints

### List Watch Parties

```http
GET /api/watch/list/<server_id>
```

**Response:**
```json
{
  "rooms": [
    {
      "room_id": "abc123",
      "title": "Movie Night",
      "host_id": "123456789",
      "host_name": "Admin",
      "is_playing": true,
      "current_time": 1234.5,
      "viewer_count": 42,
      "created_at": "2024-03-29T20:30:00Z",
      "required_role_id": null
    }
  ]
}
```

---

### Create Watch Party (URL)

```http
POST /api/watch/create/<server_id>
Content-Type: application/json

{
  "title": "Movie Night",
  "video_url": "https://example.com/video.mp4",
  "required_role_id": "987654321"
}
```

**Response:**
```json
{
  "room": { /* room object */ },
  "room_id": "abc123"
}
```

**Errors:**
- `400` - Missing video_url
- `403` - Unauthorized
- `413` - File too large

---

### Upload Video File

```http
POST /api/watch/upload/<server_id>
Content-Type: multipart/form-data

file: <binary video data>
title: "Movie Night"
required_role_id: "987654321"
```

**Response:**
```json
{
  "room": { /* room object */ },
  "room_id": "abc123"
}
```

**Supported Formats:**
- `.mp4` - MPEG-4 Video
- `.webm` - WebM Video
- `.mkv` - Matroska Video
- `.mov` - QuickTime Video
- `.avi` - Audio Video Interleave
- `.m4v` - MPEG-4 Video (iTunes)

**Limits:**
- Max file size: 10GB (configurable)
- Max concurrent uploads: 3

---

### Stream Video File

```http
GET /api/watch/stream/<room_id>
Range: bytes=0-1023
```

**Response:**
```
206 Partial Content
Content-Type: video/mp4
Content-Range: bytes 0-1023/1048576
Content-Length: 1024
```

**Features:**
- HTTP Range request support for seeking
- Byte-range streaming
- Automatic MIME type detection

---

### Get Room State

```http
GET /api/watch/<room_id>
```

**Response:**
```json
{
  "room_id": "abc123",
  "title": "Movie Night",
  "host_id": "123456789",
  "host_name": "Admin",
  "is_playing": true,
  "current_time": 1234.5,
  "viewer_count": 42,
  "viewers": [
    {
      "name": "User1",
      "user_id": "111111111",
      "avatar": "https://...",
      "joined_at": "2024-03-29T20:30:00Z",
      "role_level": 2
    }
  ],
  "created_at": "2024-03-29T20:30:00Z",
  "required_role_id": null,
  "volume": 1.0,
  "is_looping": false
}
```

**Errors:**
- `404` - Room not found
- `403` - Access denied

---

### Close Watch Party

```http
POST /api/watch/<room_id>/close
```

**Response:**
```json
{
  "success": true
}
```

**Errors:**
- `404` - Room not found
- `403` - Only host can close

---

## Socket.IO Events

### Client → Server

#### watch_join

Join a watch party room.

```javascript
socket.emit("watch_join", {
  room_id: "abc123",
  username: "User1",
  user_id: "111111111"
});
```

**Response:**
```javascript
socket.on("watch_state", {
  is_playing: true,
  current_time: 1234.5,
  video_url: "https://...",
  title: "Movie Night",
  host_id: "123456789",
  host_name: "Admin",
  viewer_count: 42,
  chat_history: [ /* last 50 messages */ ],
  my_role_level: 2,
  volume: 1.0,
  is_looping: false
});
```

---

#### watch_leave

Leave a watch party room.

```javascript
socket.emit("watch_leave", {
  room_id: "abc123"
});
```

---

#### watch_play

Play the video (Mods+ only).

```javascript
socket.emit("watch_play", {
  room_id: "abc123",
  current_time: 1234.5
});
```

**Response:**
```javascript
socket.on("watch_sync", {
  action: "play",
  current_time: 1234.5,
  is_playing: true
});
```

**Errors:**
- "Only mods and above can control playback"

---

#### watch_pause

Pause the video (Mods+ only).

```javascript
socket.emit("watch_pause", {
  room_id: "abc123",
  current_time: 1234.5
});
```

**Response:**
```javascript
socket.on("watch_sync", {
  action: "pause",
  current_time: 1234.5,
  is_playing: false
});
```

---

#### watch_seek

Seek to a specific time (Mods+ only).

```javascript
socket.emit("watch_seek", {
  room_id: "abc123",
  current_time: 5000.0
});
```

**Response:**
```javascript
socket.on("watch_sync", {
  action: "seek",
  current_time: 5000.0,
  is_playing: true
});
```

---

#### watch_chat

Send a chat message (Members+ only).

```javascript
socket.emit("watch_chat", {
  room_id: "abc123",
  message: "Great movie!",
  username: "User1"
});
```

**Response:**
```javascript
socket.on("watch_chat_msg", {
  user: "User1",
  avatar: "https://...",
  msg: "Great movie!",
  ts: "20:30",
  user_id: "111111111"
});
```

**Limits:**
- Max 500 characters
- Rate limit: 10 messages/minute
- Guests cannot send messages

**Errors:**
- "Guests cannot send messages"
- "Rate limit exceeded"

---

#### watch_request_sync

Request synchronization with server.

```javascript
socket.emit("watch_request_sync", {
  room_id: "abc123"
});
```

**Response:**
```javascript
socket.on("watch_sync", {
  action: "sync",
  current_time: 1234.5,
  is_playing: true
});
```

---

### Server → Client

#### watch_state

Initial room state when joining.

```javascript
{
  is_playing: true,
  current_time: 1234.5,
  video_url: "https://...",
  title: "Movie Night",
  host_id: "123456789",
  host_name: "Admin",
  viewer_count: 42,
  chat_history: [ /* messages */ ],
  my_role_level: 2,
  volume: 1.0,
  is_looping: false
}
```

---

#### watch_sync

Playback synchronization event.

```javascript
{
  action: "play" | "pause" | "seek" | "sync",
  current_time: 1234.5,
  is_playing: true
}
```

---

#### watch_chat_msg

New chat message.

```javascript
{
  user: "User1",
  avatar: "https://...",
  msg: "Great movie!",
  ts: "20:30",
  user_id: "111111111"
}
```

---

#### viewer_joined

Viewer joined the room.

```javascript
{
  name: "User1",
  viewer_count: 43
}
```

---

#### viewer_left

Viewer left the room.

```javascript
{
  name: "User1",
  viewer_count: 41
}
```

---

#### room_closed

Watch party ended.

```javascript
{
  room_id: "abc123"
}
```

---

#### error

Error message.

```javascript
{
  message: "Only mods and above can control playback"
}
```

---

## Role Levels

```
0 = Guest (no role)
1 = Member (any server role)
2 = Mod (manage_messages or manage_guild)
3 = Admin (administrator)
4 = Owner (server owner)
```

---

## Permission Matrix

| Action | Guest | Member | Mod | Admin | Owner |
|--------|-------|--------|-----|-------|-------|
| Watch | ✅ | ✅ | ✅ | ✅ | ✅ |
| Chat | ❌ | ✅ | ✅ | ✅ | ✅ |
| Control | ❌ | ❌ | ✅ | ✅ | ✅ |
| Request | ❌ | ❌ | ✅ | ✅ | ✅ |

---

## Error Codes

### HTTP Errors

| Code | Message | Cause |
|------|---------|-------|
| 400 | Bad Request | Missing required fields |
| 403 | Forbidden | Access denied / insufficient permissions |
| 404 | Not Found | Room or file not found |
| 413 | Payload Too Large | File exceeds size limit |
| 500 | Server Error | Internal server error |

### Socket Errors

| Message | Cause |
|---------|-------|
| "Room not found" | Invalid room_id |
| "Access denied" | Missing required role |
| "Only mods and above can control playback" | Insufficient permissions |
| "Only mods and above can skip/seek" | Insufficient permissions |
| "Guests cannot send messages" | Guest trying to chat |
| "Rate limit exceeded" | Too many messages too quickly |

---

## Rate Limits

| Action | Limit |
|--------|-------|
| Chat messages | 10 per minute |
| File uploads | 3 concurrent |
| Sync requests | 1 per 5 seconds |
| Seek requests | 1 per 100ms |

---

## Configuration

### Environment Variables

```env
WATCH_PARTY_UPLOAD_DIR=./uploads/watch_party
WATCH_PARTY_MAX_MB=10240
WATCH_PARTY_CLEANUP_HOURS=24
WATCH_PARTY_LOG_LEVEL=INFO
```

### Python Configuration

```python
from watch_party_config import (
    MAX_UPLOAD_MB,
    ALLOWED_VIDEO_EXTS,
    SYNC_INTERVAL_SECONDS,
    MAX_CHAT_LENGTH,
    ROLE_PERMISSIONS,
)
```

---

## Examples

### JavaScript Client

```javascript
// Connect to watch party
const socket = io();

// Join room
socket.emit("watch_join", {
  room_id: "abc123",
  username: "User1",
  user_id: "111111111"
});

// Listen for state
socket.on("watch_state", (data) => {
  console.log("Room state:", data);
});

// Play video
socket.emit("watch_play", {
  room_id: "abc123",
  current_time: 0
});

// Send message
socket.emit("watch_chat", {
  room_id: "abc123",
  message: "Great movie!",
  username: "User1"
});

// Listen for sync
socket.on("watch_sync", (data) => {
  console.log("Sync:", data);
});
```

### Python Backend

```python
from web_dashboard_enhanced import _watch_rooms, _get_user_role_level

# Get room
room = _watch_rooms.get("abc123")

# Get user role
role_level = _get_user_role_level(guild_id=123456789, user_id=111111111)

# Check permissions
if role_level >= 2:  # Mod+
    print("Can control playback")

# Access room data
print(f"Viewers: {len(room.viewers)}")
print(f"Playing: {room.is_playing}")
print(f"Time: {room.sync_time()}")
```

### cURL Examples

```bash
# List rooms
curl http://localhost:5000/api/watch/list/123456789

# Create room
curl -X POST http://localhost:5000/api/watch/create/123456789 \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Movie Night",
    "video_url": "https://example.com/video.mp4"
  }'

# Upload video
curl -X POST http://localhost:5000/api/watch/upload/123456789 \
  -F "file=@video.mp4" \
  -F "title=Movie Night"

# Get room state
curl http://localhost:5000/api/watch/abc123

# Close room
curl -X POST http://localhost:5000/api/watch/abc123/close
```

---

## Webhooks (Future)

Planned webhook events:

- `watch_party.created` - New watch party started
- `watch_party.closed` - Watch party ended
- `watch_party.viewer_joined` - Viewer joined
- `watch_party.viewer_left` - Viewer left
- `watch_party.message` - Chat message sent

---

## Changelog

### v1.0.0 (2024-03-29)

- ✅ Initial release
- ✅ Role-based permissions
- ✅ Video upload (10GB max)
- ✅ Live chat with reactions
- ✅ Synchronized playback
- ✅ Socket.IO integration

---

## Support

For API issues or questions:
- Check logs: `./logs/watch_party.log`
- Review configuration: `watch_party_config.py`
- See setup guide: `WATCH_PARTY_SETUP.md`
- See user guide: `WATCH_PARTY_GUIDE.md`
