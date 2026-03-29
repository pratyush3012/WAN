# 🎬 Watch Party Feature Guide

## Overview

The Watch Party feature allows Discord server members to watch videos together in real-time with synchronized playback, live chat, and role-based controls. Perfect for movie nights, tutorials, or community events.

## Key Features

✅ **Synchronized Playback** - All viewers see the same video at the same time  
✅ **Live Chat** - Real-time messaging with emoji reactions  
✅ **Role-Based Permissions** - Different control levels based on server roles  
✅ **Large File Support** - Up to 10GB+ video uploads  
✅ **Persistent Chat History** - Last 200 messages stored  
✅ **Viewer Tracking** - See who's watching in real-time  

---

## Role Hierarchy & Permissions

### Permission Levels

| Role | Level | Can Watch | Can Chat | Can Control | Can Request |
|------|-------|-----------|----------|-------------|-------------|
| **Guest** | 0 | ✅ | ❌ | ❌ | ❌ |
| **Member** | 1 | ✅ | ✅ | ❌ | ❌ |
| **Mod** | 2 | ✅ | ✅ | ✅ | ✅ |
| **Admin** | 3 | ✅ | ✅ | ✅ | ✅ |
| **Owner** | 4 | ✅ | ✅ | ✅ | ✅ |

### What Each Role Can Do

**👤 Guests (No Role)**
- Watch the video as an audience member
- See live chat and reactions
- Cannot send messages
- Cannot control playback (pause, play, skip)
- Cannot make requests

**👥 Members (Any Server Role)**
- Watch the video
- Send chat messages
- Use emoji reactions
- Cannot control playback
- Cannot make requests

**🛡️ Mods (Manage Messages/Guild Permission)**
- Full control over playback (play, pause, skip, seek)
- Send chat messages
- Use emoji reactions
- Can make requests
- Can moderate chat

**⚙️ Admins (Administrator Permission)**
- Same as Mods
- Can manage watch party settings
- Can end watch parties

**👑 Owner (Server Owner)**
- Same as Admins
- Can create/delete watch parties
- Full control over all settings

---

## Creating a Watch Party

### Via Web Dashboard

1. Navigate to your server's dashboard
2. Go to **Watch Party** section
3. Click **Create New Watch Party**
4. Choose upload method:
   - **Upload Video File** (up to 10GB)
   - **Enter Video URL** (YouTube, Vimeo, etc.)
5. Set title and optional role requirement
6. Click **Start Watch Party**

### Via Discord Command

```
/watch_party create
  title: "Movie Night"
  video_url: "https://example.com/video.mp4"
  required_role: @Members (optional)
```

---

## Storage Requirements

### Disk Space

- **Minimum**: 10GB free space for video uploads
- **Recommended**: 50GB+ for multiple concurrent watch parties
- **Video Formats Supported**: MP4, WebM, MKV, MOV, AVI, M4V

### File Size Limits

- **Max per video**: 10GB
- **Max concurrent uploads**: 3
- **Auto-cleanup**: Videos deleted 24 hours after watch party ends

### Storage Location

Videos are stored in: `./uploads/watch_party/`

---

## Playback Controls

### For Mods & Above

**Play/Pause**
- Click the play button or press `Space`
- Syncs to all viewers instantly

**Skip/Seek**
- Click progress bar to jump to time
- Use arrow keys: `←` (back 10s), `→` (forward 10s)
- Drag progress bar for precise seeking

**Volume**
- Slider in bottom-right of player
- Individual volume (doesn't affect others)

**Fullscreen**
- Press `F` or click fullscreen button
- Keyboard shortcuts still work in fullscreen

### For Members & Guests

- Can watch and see progress
- Cannot interact with controls
- Controls appear disabled/grayed out

---

## Chat & Reactions

### Sending Messages

**Members & Above**
- Type in chat input box
- Press Enter or click send button
- Max 500 characters per message
- Supports emojis and mentions

**Guests**
- Cannot send messages
- Will see: "Guests cannot send messages"

### Emoji Reactions

**All Viewers**
- Click reaction buttons: ❤️ 😂 😮 👏 🔥 💀
- Reactions float up and disappear
- No limit on reactions

### Chat History

- Last 50 messages shown when joining
- Full history (200 messages) stored on server
- Timestamps shown for each message

---

## Synchronization

### Auto-Sync

- Viewers automatically sync every 30 seconds
- If out of sync by >1.5 seconds, auto-corrects
- Sync indicator shows when syncing

### Manual Sync

- Click the sync button (↻) in top bar
- Useful if video gets out of sync
- Takes ~1-2 seconds to complete

### Latency Handling

- System accounts for network latency
- Playback position calculated server-side
- Viewers see smooth, synchronized playback

---

## Ending a Watch Party

### Host/Admin Only

1. Click **End Party** button (top-right)
2. Confirm the action
3. All viewers will be notified
4. Video file automatically deleted
5. Chat history preserved for 24 hours

---

## Troubleshooting

### Video Won't Play

- Check file format (MP4, WebM, MKV supported)
- Verify file size < 10GB
- Try refreshing the page
- Check browser console for errors

### Out of Sync

- Click the sync button (↻)
- Refresh the page
- Check your internet connection
- Try a different browser

### Can't Send Messages

- Check your role level (need Member+)
- Verify you're not muted in the server
- Try refreshing the page

### Chat Not Showing

- Scroll up in chat area
- Check if you're muted
- Verify chat history loaded (50 messages)

### Controls Disabled

- Check your role (need Mod+ to control)
- Verify you're not a guest
- Ask a mod to promote you

---

## Best Practices

### For Hosts

1. **Test Before Starting** - Verify video plays correctly
2. **Set Clear Rules** - Communicate expectations in chat
3. **Monitor Chat** - Keep conversation on-topic
4. **Sync Regularly** - Click sync button every 5-10 minutes
5. **Announce End Time** - Let viewers know when party ends

### For Viewers

1. **Join Early** - Arrive 5 minutes before start
2. **Check Connection** - Ensure stable internet
3. **Use Reactions** - React instead of spamming chat
4. **Respect Roles** - Don't ask mods to give you control
5. **Report Issues** - Tell host if video is out of sync

### For Admins

1. **Monitor Storage** - Check disk space regularly
2. **Clean Old Videos** - Delete unused watch parties
3. **Set Role Requirements** - Restrict to members-only if needed
4. **Backup Important Parties** - Save videos before deletion
5. **Review Chat Logs** - Monitor for inappropriate content

---

## Technical Details

### Architecture

- **Frontend**: HTML5 Video Player + Socket.IO
- **Backend**: Flask + Python
- **Streaming**: HTTP Range requests for seeking
- **Sync**: Server-side time calculation
- **Storage**: Local filesystem (configurable)

### Performance

- **Concurrent Viewers**: 100+ per watch party
- **Latency**: <500ms typical
- **Bandwidth**: ~5Mbps per viewer (1080p)
- **CPU**: <5% per watch party
- **Memory**: ~50MB per watch party

### Security

- **Access Control**: Role-based permissions
- **Chat Filtering**: XSS protection
- **File Validation**: MIME type checking
- **Rate Limiting**: 10 messages/minute per user
- **Session Management**: Secure cookies

---

## API Endpoints

### Create Watch Party

```
POST /api/watch/create
{
  "title": "Movie Night",
  "video_url": "https://example.com/video.mp4",
  "required_role_id": "123456789"
}
```

### Upload Video

```
POST /api/watch/upload
Content-Type: multipart/form-data
- file: <video file>
- title: "Movie Night"
- required_role_id: "123456789"
```

### Get Room State

```
GET /api/watch/{room_id}
```

### Close Watch Party

```
POST /api/watch/{room_id}/close
```

---

## Socket Events

### Client → Server

- `watch_join` - Join a watch party
- `watch_leave` - Leave a watch party
- `watch_play` - Play video
- `watch_pause` - Pause video
- `watch_seek` - Seek to time
- `watch_chat` - Send message
- `watch_request_sync` - Request sync

### Server → Client

- `watch_state` - Initial state
- `watch_sync` - Sync playback
- `watch_chat_msg` - New message
- `viewer_joined` - Viewer joined
- `viewer_left` - Viewer left
- `room_closed` - Party ended
- `error` - Error message

---

## FAQ

**Q: Can I upload videos larger than 10GB?**  
A: No, 10GB is the maximum. Consider splitting large files or using external URLs.

**Q: Do guests need to be in the Discord server?**  
A: Yes, they must be members to access the watch party.

**Q: Can I download videos from the watch party?**  
A: No, videos are streamed only and deleted after the party ends.

**Q: How long are videos stored?**  
A: 24 hours after the watch party ends, then automatically deleted.

**Q: Can I pause for other viewers?**  
A: Only if you're a Mod or above. Members cannot control playback.

**Q: What happens if the host leaves?**  
A: The watch party continues. Another mod can take over controls.

**Q: Can I use external video URLs?**  
A: Yes, YouTube, Vimeo, and direct MP4 URLs are supported.

**Q: Is there a viewer limit?**  
A: No hard limit, but performance may degrade with 500+ concurrent viewers.

---

## Support

For issues or feature requests:
- Report in `#support` channel
- Contact server admins
- Check logs: `./logs/watch_party.log`

Enjoy your watch parties! 🎬🍿
