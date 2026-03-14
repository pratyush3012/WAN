# 🚀 Production Deployment Guide

## Pre-Deployment Checklist

### 1. Environment Configuration

Create `.env` file with production values:

```env
# Required
DISCORD_TOKEN=your_production_bot_token
OWNER_ID=your_discord_user_id

# Database (use PostgreSQL in production)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/discord_bot

# Optional but recommended
GOOGLE_TRANSLATE_API_KEY=your_api_key
YOUTUBE_API_KEY=your_api_key

# Logging
LOG_LEVEL=WARNING  # Use WARNING in production, INFO for debugging
```

### 2. Database Setup (PostgreSQL Recommended)

**Why PostgreSQL over SQLite:**
- Better concurrency handling
- Connection pooling support
- Better performance at scale
- ACID compliance
- Backup and replication support

**Setup:**
```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database
sudo -u postgres psql
CREATE DATABASE discord_bot;
CREATE USER bot_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE discord_bot TO bot_user;
\q

# Update .env
DATABASE_URL=postgresql+asyncpg://bot_user:secure_password@localhost:5432/discord_bot

# Install Python driver
pip install asyncpg
```

### 3. System Requirements

**Minimum (Small servers <1000 members):**
- 1 CPU core
- 512MB RAM
- 5GB storage

**Recommended (Medium servers 1000-10000 members):**
- 2 CPU cores
- 2GB RAM
- 20GB storage

**Production (Large servers 10000+ members):**
- 4 CPU cores
- 4GB RAM
- 50GB storage
- SSD recommended

### 4. Install System Dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.10 python3-pip ffmpeg postgresql redis-server

# Verify installations
python3 --version  # Should be 3.10+
ffmpeg -version
redis-cli ping  # Should return PONG
```

## Deployment Options

### Option 1: Systemd Service (Recommended for VPS)

Create `/etc/systemd/system/discord-bot.service`:

```ini
[Unit]
Description=Discord Gaming Bot
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/discord-bot
Environment="PATH=/opt/discord-bot/venv/bin"
EnvironmentFile=/opt/discord-bot/.env
ExecStart=/opt/discord-bot/venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/discord-bot/output.log
StandardError=append:/var/log/discord-bot/error.log

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/discord-bot

# Resource limits
MemoryMax=2G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
```

**Setup:**
```bash
# Create user
sudo useradd -r -s /bin/false botuser

# Create directories
sudo mkdir -p /opt/discord-bot /var/log/discord-bot
sudo chown botuser:botuser /opt/discord-bot /var/log/discord-bot

# Deploy code
sudo cp -r . /opt/discord-bot/
sudo chown -R botuser:botuser /opt/discord-bot

# Create virtual environment
cd /opt/discord-bot
sudo -u botuser python3 -m venv venv
sudo -u botuser venv/bin/pip install -r requirements.txt

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable discord-bot
sudo systemctl start discord-bot

# Check status
sudo systemctl status discord-bot
sudo journalctl -u discord-bot -f  # Follow logs
```

### Option 2: Docker (Recommended for Containers)

**Improved Dockerfile:**
```dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 botuser

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY --chown=botuser:botuser . .

# Switch to non-root user
USER botuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import discord; print('healthy')" || exit 1

# Run bot
CMD ["python", "bot.py"]
```

**Improved docker-compose.yml:**
```yaml
version: '3.8'

services:
  bot:
    build: .
    container_name: discord-gaming-bot
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    depends_on:
      - postgres
      - redis
    networks:
      - bot-network
    mem_limit: 2g
    cpus: 2
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  postgres:
    image: postgres:15-alpine
    container_name: discord-bot-db
    restart: unless-stopped
    environment:
      POSTGRES_DB: discord_bot
      POSTGRES_USER: bot_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - bot-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bot_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: discord-bot-redis
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis-data:/data
    networks:
      - bot-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres-data:
  redis-data:

networks:
  bot-network:
    driver: bridge
```

**Deploy:**
```bash
docker-compose up -d
docker-compose logs -f bot  # Follow logs
docker-compose ps  # Check status
```

### Option 3: PM2 (Alternative Process Manager)

```bash
# Install PM2
npm install -g pm2

# Create ecosystem.config.js
cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [{
    name: 'discord-bot',
    script: 'bot.py',
    interpreter: 'python3',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '2G',
    env: {
      NODE_ENV: 'production'
    },
    error_file: './logs/err.log',
    out_file: './logs/out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
  }]
}
EOF

# Start bot
pm2 start ecosystem.config.js
pm2 save
pm2 startup  # Enable auto-start on boot

# Monitor
pm2 monit
pm2 logs discord-bot
```

## Monitoring Setup

### 1. Log Rotation

Create `/etc/logrotate.d/discord-bot`:

```
/var/log/discord-bot/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 botuser botuser
    sharedscripts
    postrotate
        systemctl reload discord-bot > /dev/null 2>&1 || true
    endscript
}
```

### 2. Basic Monitoring Script

Create `monitor.sh`:

```bash
#!/bin/bash

# Check if bot is running
if ! systemctl is-active --quiet discord-bot; then
    echo "❌ Bot is not running!"
    systemctl restart discord-bot
    # Send alert (email, Discord webhook, etc.)
fi

# Check memory usage
MEM_USAGE=$(ps aux | grep "python bot.py" | grep -v grep | awk '{print $4}')
if (( $(echo "$MEM_USAGE > 80" | bc -l) )); then
    echo "⚠️ High memory usage: ${MEM_USAGE}%"
    # Send alert
fi

# Check disk space
DISK_USAGE=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    echo "⚠️ High disk usage: ${DISK_USAGE}%"
    # Send alert
fi

# Check error rate in logs
ERROR_COUNT=$(grep -c "ERROR" /var/log/discord-bot/error.log 2>/dev/null || echo 0)
if [ "$ERROR_COUNT" -gt 100 ]; then
    echo "⚠️ High error count: $ERROR_COUNT"
    # Send alert
fi
```

Add to crontab:
```bash
crontab -e
# Add: */5 * * * * /opt/discord-bot/monitor.sh
```

### 3. Discord Webhook Alerts

Add to your bot for self-monitoring:

```python
# utils/monitoring.py
import aiohttp
import os

async def send_alert(title, message, severity="warning"):
    """Send alert to Discord webhook"""
    webhook_url = os.getenv('ALERT_WEBHOOK_URL')
    if not webhook_url:
        return
    
    colors = {
        "info": 0x3498db,
        "warning": 0xf39c12,
        "error": 0xe74c3c,
        "critical": 0x992d22
    }
    
    embed = {
        "title": f"🚨 {title}",
        "description": message,
        "color": colors.get(severity, 0x95a5a6),
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    
    async with aiohttp.ClientSession() as session:
        await session.post(webhook_url, json={"embeds": [embed]})
```

## Backup Strategy

### 1. Database Backups

```bash
# Create backup script
cat > /opt/discord-bot/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/discord-bot/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
pg_dump -U bot_user discord_bot | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Keep only last 7 days
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +7 -delete

echo "Backup completed: db_$DATE.sql.gz"
EOF

chmod +x /opt/discord-bot/backup.sh

# Add to crontab (daily at 2 AM)
crontab -e
# Add: 0 2 * * * /opt/discord-bot/backup.sh
```

### 2. Configuration Backups

```bash
# Backup .env and configs
tar -czf config_backup_$(date +%Y%m%d).tar.gz .env *.md
```

## Security Hardening

### 1. Firewall Configuration

```bash
# UFW (Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 443/tcp  # If running web dashboard
sudo ufw enable
```

### 2. Fail2Ban (Prevent brute force)

```bash
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 3. Secure Environment Variables

```bash
# Restrict .env permissions
chmod 600 .env
chown botuser:botuser .env
```

### 4. Regular Updates

```bash
# Create update script
cat > /opt/discord-bot/update.sh << 'EOF'
#!/bin/bash
cd /opt/discord-bot
git pull
venv/bin/pip install -r requirements.txt --upgrade
sudo systemctl restart discord-bot
EOF

chmod +x /opt/discord-bot/update.sh
```

## Performance Tuning

### 1. PostgreSQL Optimization

Edit `/etc/postgresql/15/main/postgresql.conf`:

```ini
# Memory settings (adjust based on available RAM)
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
work_mem = 16MB

# Connection settings
max_connections = 100

# Performance
random_page_cost = 1.1  # For SSD
effective_io_concurrency = 200
```

Restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

### 2. Redis Configuration

Edit `/etc/redis/redis.conf`:

```ini
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### 3. Python Optimization

```bash
# Use uvloop for better async performance
pip install uvloop

# Add to bot.py:
import uvloop
uvloop.install()
```

## Troubleshooting

### Bot Won't Start

```bash
# Check logs
sudo journalctl -u discord-bot -n 50
tail -f /var/log/discord-bot/error.log

# Check permissions
ls -la /opt/discord-bot
ps aux | grep python

# Test manually
cd /opt/discord-bot
sudo -u botuser venv/bin/python bot.py
```

### High Memory Usage

```bash
# Check memory
free -h
ps aux --sort=-%mem | head

# Restart bot
sudo systemctl restart discord-bot

# Check for memory leaks
python -m memory_profiler bot.py
```

### Database Connection Issues

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test connection
psql -U bot_user -d discord_bot -h localhost

# Check connections
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"
```

### Voice Connection Issues

```bash
# Check FFmpeg
ffmpeg -version

# Check voice connections
# Add to bot: /debug voice command

# Restart voice connections
# Add to bot: /cleanup voice command
```

## Scaling Considerations

### Horizontal Scaling (Multiple Instances)

For 50k+ members, consider sharding:

```python
# bot.py
class GamingBot(commands.AutoShardedBot):  # Use AutoShardedBot
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None,
            shard_count=4  # Adjust based on guild count
        )
```

### Load Balancing

Use Redis for shared state across instances:

```python
# utils/cache.py
import redis.asyncio as redis

class RedisCache:
    def __init__(self):
        self.redis = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost'))
    
    async def get_guild_config(self, guild_id):
        cached = await self.redis.get(f"config:{guild_id}")
        if cached:
            return json.loads(cached)
        return None
    
    async def set_guild_config(self, guild_id, config, ttl=300):
        await self.redis.setex(
            f"config:{guild_id}",
            ttl,
            json.dumps(config)
        )
```

## Cost Estimation

### VPS Hosting (DigitalOcean, Linode, Vultr)

- **Small (1GB RAM):** $5-6/month
- **Medium (2GB RAM):** $10-12/month
- **Large (4GB RAM):** $20-24/month

### Cloud Hosting (AWS, GCP, Azure)

- **t3.small (2GB RAM):** ~$15/month
- **t3.medium (4GB RAM):** ~$30/month

### Additional Costs

- **PostgreSQL (managed):** $15-50/month
- **Redis (managed):** $10-30/month
- **Backups:** $5-10/month
- **Monitoring:** $0-20/month
- **Translation API:** $0-50/month (depends on usage)

**Total Estimated Cost:** $50-150/month for production setup

## Launch Checklist

- [ ] Environment variables configured
- [ ] Database initialized and backed up
- [ ] All critical fixes applied
- [ ] Monitoring and alerts configured
- [ ] Logs rotation configured
- [ ] Firewall rules set
- [ ] SSL certificates installed (if web dashboard)
- [ ] Backup strategy tested
- [ ] Rollback procedure documented
- [ ] Load testing completed
- [ ] Security audit passed
- [ ] Documentation updated
- [ ] Team trained on operations
- [ ] Incident response plan ready
- [ ] Status page configured
- [ ] Gradual rollout plan ready

## Post-Launch

### Week 1
- Monitor error rates hourly
- Check memory usage daily
- Review logs for issues
- Gather user feedback
- Optimize based on metrics

### Month 1
- Review performance metrics
- Optimize slow queries
- Update documentation
- Plan feature improvements
- Review security

### Ongoing
- Weekly backups verification
- Monthly security updates
- Quarterly performance review
- Annual disaster recovery drill

---

**Need Help?** Check logs first, then review AUDIT_REPORT.md and CRITICAL_FIXES.md for common issues.
