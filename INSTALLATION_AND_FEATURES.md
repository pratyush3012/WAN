# WAN Bot - Complete Installation & Features Guide

## Quick Installation (10 Minutes)

### Prerequisites
- Python 3.8+
- Discord Bot Token
- Render account (for deployment)

### Step 1: Clone & Setup
```bash
git clone <your-repo-url>
cd WAN-Bot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Configure Environment
Copy `.env.example` to `.env` and fill in:
```env
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_guild_id_here
OWNER_ID=your_user_id_here
```

### Step 3: Run Bot
```bash
python bot.py
```

Bot will automatically create data directories on first run.

### Step 4: Deploy to Render
1. Push code to GitHub
2. Create new Web Service on Render
3. Connect GitHub repo
4. Set environment variables in Render dashboard
5. Deploy (uses Procfile: `web: python bot.py`)

---

## Core Features

### 1. Watch Party System
**Premium video watching experience with chat, requests, scheduling, and auto-registration**

#### New Features:
- **Auto-Registration**: Mods/Admins automatically registered when promoted
- **Account System**: Each user gets account with Discord username as primary ID
- **Password Protection**: Users set passwords for dashboard access
- **Movie Upload Notifications**: Discord announcements when movies upload
- **Schedule Voting**: Community votes on best time to watch
- **Advanced UI**: Modern dark theme with cyan accents, smooth animations
- **Live Chat**: Everyone can chat with role-based colors
- **Request System**: Members+ can request Play, Pause, Skip, Rewind, Forward
- **Permission Levels**:
  - **Owner**: Full control, approves uploads, manages schedule
  - **Admin**: Can upload, schedule, manage users
  - **Moderator**: Can moderate chat, approve requests
  - **Member**: Can chat, raise requests
  - **Guest**: Can watch, cannot chat or request

#### Database Structure:
```
./data/watch_party/
├── movies.json          # Uploaded movies
├── movie_rooms.json     # Active watch rooms
├── enhanced.json        # Premium features
├── chat.json           # Chat messages
├── requests.json       # Watch requests
└── schedule_votes.json # Schedule voting data

./data/users/
├── users.json          # User accounts and passwords
└── roles.json          # User roles and permissions
```

#### Upload Flow:
1. Admin uploads movie via `/movie-upload`
2. Discord announcement sent to server
3. Community votes on schedule time (reactions)
4. Owner receives permission request via DM
5. Owner approves/denies with reactions
6. Movie auto-starts at scheduled time
7. Watch party created with live chat and requests

#### Commands:
```
/set-password <password>    # Set dashboard password
/movie-upload              # Upload new movie
/watch-party               # Create watch party
/list-movies               # List available movies
```

#### API Endpoints:
```
POST   /api/watch/upload              # Upload movie
GET    /api/watch/movies              # List movies
POST   /api/watch/room/create         # Create watch room
GET    /api/watch/room/<room_id>      # Get room details
POST   /api/watch/chat/<room_id>      # Send chat message
GET    /api/watch/chat/<room_id>      # Get chat history
POST   /api/watch/request/<room_id>   # Create watch request
GET    /api/watch/request/<room_id>   # Get pending requests
POST   /api/watch/request/approve     # Approve request
POST   /api/watch/request/reject      # Reject request
POST   /api/watch/schedule/<room_id>  # Schedule movie
GET    /api/watch/schedule/<room_id>  # Get schedule
GET    /api/watch/viewers/<room_id>   # Get viewers list
```

#### Advanced UI Features:
- **Video Player**: Full controls (play, pause, rewind, forward, fullscreen)
- **Progress Bar**: Click to seek, shows current time
- **Live Chat Panel**: Real-time messages with role-based colors
- **Requests Panel**: Pending requests with approve/reject buttons
- **Viewers Panel**: Live viewer list with role badges
- **Schedule Panel**: Upcoming movies with countdown timer
- **Reactions**: Users can react to messages
- **Smooth Animations**: All interactions have smooth transitions
- **Responsive Design**: Works on desktop and mobile

#### User Account System:
- **Auto-Registration**: When user gets mod/admin role
- **Primary ID**: Discord username (e.g., "pratyush3012")
- **Password Setup**: User sets password via `/set-password`
- **Dashboard Access**: Login with username and password
- **Permission Levels**: Based on Discord role
- **Account Info**: Sent via DM when promoted

#### Schedule Voting:
- **Emoji Reactions**: 🕐-🕗 for different times
- **Community Vote**: Everyone can vote
- **Auto-Selection**: Time with most votes wins
- **Confirmation**: Owner notified of winning time
- **Auto-Start**: Movie starts at scheduled time

---

### 2. Music Player System
**Persistent music queue with settings and history**

#### Features:
- Queue persists across bot restarts
- Settings persist (volume, loop, autoplay, 24/7 mode)
- Play history tracking
- Skip cooldown (prevents double-skip)
- Dashboard auto-recreates if deleted
- Autoplay prevents repeating recently played songs

#### Database Structure:
```
./data/music/
├── queues.json         # Music queues per guild
├── settings.json       # Player settings (volume, loop, autoplay, 24/7)
└── history.json        # Play history for autoplay
```

#### Settings:
- **Volume**: 0-100 (default: 50)
- **Loop**: off, one, all (default: off)
- **Autoplay**: true/false (default: true)
- **24/7 Mode**: Keep player running 24/7 (default: false)

#### Commands:
```
/play <song>           # Play song
/pause                 # Pause playback
/resume                # Resume playback
/skip                  # Skip current song
/queue                 # Show queue
/clear                 # Clear queue
/volume <0-100>        # Set volume
/loop <off|one|all>    # Set loop mode
/autoplay <on|off>     # Toggle autoplay
/24-7 <on|off>         # Toggle 24/7 mode
```

---

### 3. Leveling System
**User progression with levels, XP, and rewards**

#### Features:
- Automatic XP gain from messages
- Level progression with configurable XP requirements
- Leaderboards
- Role rewards at specific levels
- Persistent storage

#### Database:
```
./data/leveling/
└── levels.json         # User levels and XP
```

#### Commands:
```
/level                 # Show your level
/leaderboard           # Show top users
/level-config          # Configure leveling
```

---

### 4. Moderation System
**Server management and user protection**

#### Features:
- Warn users
- Mute/Unmute
- Kick/Ban
- Message filtering
- Auto-moderation

#### Commands:
```
/warn <user> <reason>
/mute <user> <duration>
/unmute <user>
/kick <user> <reason>
/ban <user> <reason>
/unban <user>
```

---

### 5. Utility Features
- Custom commands
- Role management
- Temporary voice channels
- Starboard
- Suggestions system
- Ticket system
- Translation
- YouTube integration

---

## User Account & Authentication System

### Auto-Registration
- **Automatic**: Users registered when promoted to mod/admin
- **No Manual Setup**: Happens instantly
- **DM Notification**: User receives account info via Discord DM
- **Primary ID**: Discord username used as account identifier

### Account Features
- **Username**: Discord username (e.g., "pratyush3012")
- **Password**: User-set password (minimum 8 characters)
- **Role-Based Access**: Permissions based on Discord role
- **Dashboard Login**: Access web controls with credentials
- **Permission Levels**:
  - Owner: Full control
  - Admin: Upload, schedule, manage users
  - Moderator: Moderate chat, approve requests
  - Member: Chat, raise requests
  - Guest: Watch only

### Password Management
```
/set-password <password>    # Set your dashboard password
```

### Dashboard Access
1. Go to WAN Bot dashboard
2. Click "Login"
3. Enter username (Discord name)
4. Enter password (set via `/set-password`)
5. Access all controls based on your role

### Permissions by Role

| Feature | Owner | Admin | Mod | Member | Guest |
|---------|-------|-------|-----|--------|-------|
| Chat | ✅ | ✅ | ✅ | ✅ | ❌ |
| React | ✅ | ✅ | ✅ | ✅ | ❌ |
| Request | ✅ | ✅ | ✅ | ✅ | ❌ |
| Pause | ✅ | ✅ | ✅ | ❌ | ❌ |
| Play | ✅ | ✅ | ✅ | ❌ | ❌ |
| Upload | ✅ | ✅ | ❌ | ❌ | ❌ |
| Schedule | ✅ | ✅ | ❌ | ❌ | ❌ |
| Manage Users | ✅ | ✅ | ❌ | ❌ | ❌ |

---

## Movie Upload & Schedule Voting

### Upload Process
1. Admin runs `/movie-upload`
2. Uploads movie file via dashboard
3. Discord announcement sent to server
4. Community votes on schedule time
5. Owner approves/denies upload
6. Movie auto-starts at winning time

### Schedule Voting
- **Emoji Reactions**: 🕐 (6 PM) through 🕗 (1 AM)
- **Community Vote**: Everyone can vote
- **Auto-Selection**: Time with most votes wins
- **Confirmation**: Owner notified of schedule
- **Auto-Start**: Movie starts automatically

### Notification Flow
1. **Upload Announcement**: "New movie uploaded!"
2. **Vote Request**: "React to vote for watch time"
3. **Permission Request**: Owner gets DM to approve
4. **Schedule Confirmation**: Owner notified of winning time
5. **Auto-Start**: Movie starts at scheduled time

---

All data is stored in JSON files in `./data/` directory:

### Auto-Creation
Databases automatically create on first use:
- `./data/watch_party/` - Watch party data
- `./data/music/` - Music player data
- `./data/leveling/` - Leveling data

### Data Survival
- ✅ Survives bot restarts
- ✅ Survives server refreshes
- ✅ Survives crashes (soft deletes only)
- ✅ Backed up in git (optional)

### Soft Deletes
Data is marked as deleted but not removed:
- Allows recovery if needed
- Keeps historical records
- Prevents accidental data loss

---

## Deployment

### Local Development
```bash
python bot.py
```

### Render Deployment
1. **Create Web Service**
   - Connect GitHub repo
   - Set environment variables
   - Render uses Procfile: `web: python bot.py`

2. **Environment Variables**
   ```
   DISCORD_TOKEN=your_token
   GUILD_ID=your_guild_id
   OWNER_ID=your_owner_id
   ```

3. **Data Persistence**
   - Use Render Disk for persistent storage
   - Mount at `/data` directory
   - Survives deployments

### Docker Deployment
```bash
docker build -t wan-bot .
docker run -e DISCORD_TOKEN=your_token wan-bot
```

---

## Troubleshooting

### Movies Disappearing
**Solution**: Ensure database persistence is enabled
- Check `./data/watch_party/movies.json` exists
- Verify file permissions (readable/writable)
- Check bot has access to data directory

### Music Queue Lost
**Solution**: Queue is saved automatically
- Check `./data/music/queues.json` exists
- Verify bot restarted properly
- Check for errors in bot logs

### Watch Party Not Starting
**Solution**: Check scheduled time
- Verify schedule time is in future
- Check bot has permission to send messages
- Verify room is still active

### Chat Not Showing
**Solution**: Verify permissions
- Check user role in watch room
- Verify chat history file exists
- Check browser cache (clear if needed)

---

## File Structure

```
WAN-Bot/
├── bot.py                          # Main bot entry point
├── requirements.txt                # Python dependencies
├── Procfile                        # Render deployment config
├── .env                           # Environment variables
├── .env.example                   # Example env file
│
├── cogs/                          # Discord bot commands
│   ├── music.py                   # Music player
│   ├── watch_party_enhanced.py    # Watch party integration
│   ├── moderation.py              # Moderation commands
│   ├── leveling.py                # Leveling system
│   └── ...                        # Other features
│
├── watch_party_*.py               # Watch party modules
│   ├── watch_party_movies_db.py   # Movie database
│   ├── watch_party_enhanced.py    # Premium features DB
│   ├── watch_party_premium_api.py # API endpoints
│   └── watch_party_api.py         # Basic API
│
├── music_db.py                    # Music database
├── leveling_db.py                 # Leveling database
│
├── templates/                     # Web dashboard HTML
│   ├── watch_party_premium.html   # Premium watch party UI
│   ├── watch_party.html           # Basic watch party UI
│   └── ...                        # Other templates
│
├── static/                        # CSS, JS, images
│   └── css/
│       └── liquid-glass.css       # Modern UI styling
│
├── data/                          # Persistent storage (auto-created)
│   ├── watch_party/               # Watch party data
│   ├── music/                     # Music data
│   └── leveling/                  # Leveling data
│
├── uploads/                       # Uploaded files
│   └── watch_party/               # Movie uploads
│
└── docs/                          # Documentation
    └── ROBLOX_SETUP.md            # Roblox integration guide
```

---

## Configuration

### Watch Party Setup
```bash
/watchparty setup
```
Configure:
- Upload channel
- Watch party channel
- Announcement channel

### Music Settings
```bash
/music-config
```
Configure:
- Default volume
- Loop mode
- Autoplay
- 24/7 mode

---

## Support & Updates

### Check Bot Status
```bash
/status
```

### View Logs
```bash
tail -f bot.log
```

### Update Bot
```bash
git pull
pip install -r requirements.txt
python bot.py
```

---

## Security Notes

- Keep `.env` file private (never commit)
- Use strong Discord bot token
- Restrict bot permissions to needed roles
- Enable 2FA on Discord account
- Regularly update dependencies

---

## Performance Tips

- Use 24/7 mode only if needed (uses more resources)
- Limit queue size to 500 songs
- Archive old watch party data monthly
- Monitor bot memory usage

---

## Reliability & Uptime

### Automatic Crash Recovery
- Bot automatically restarts on crash (up to 5 attempts)
- Exponential backoff: 5s → 10s → 20s → 40s → 60s
- Logs all errors for debugging
- Never stays offline permanently

### Keep-Alive System
- Pings health endpoint every 10 minutes
- Prevents Render from sleeping
- Tracks consecutive failures
- Ensures 24/7 availability

### Error Handling
- Global error handler for all events
- Graceful error recovery
- Detailed logging for troubleshooting
- No silent failures

---

## Version Info

- **Bot Version**: 3.0 - Complete Watch Party System
- **Python**: 3.8+
- **discord.py**: Latest
- **Last Updated**: March 30, 2026
- **Status**: Production Ready with Full Automation ✅

### What's New in v3.0:
- ✅ Auto-registration for mods/admins
- ✅ User account system with passwords
- ✅ Advanced UI with modern design
- ✅ Movie upload notifications
- ✅ Community schedule voting
- ✅ Permission-based access control
- ✅ Automatic movie start at scheduled time
- ✅ Enhanced chat with role-based colors
- ✅ Request system with approval workflow

---

## License & Credits

Built with discord.py and Flask
Designed for community servers

---

## Quick Reference

| Feature | Command | Status |
|---------|---------|--------|
| Watch Party | `/watchparty setup` | ✅ Active |
| Music Player | `/play <song>` | ✅ Active |
| Leveling | `/level` | ✅ Active |
| Moderation | `/warn <user>` | ✅ Active |
| Utility | `/help` | ✅ Active |

---

**Last Updated**: March 30, 2026
**Status**: Production Ready ✅
