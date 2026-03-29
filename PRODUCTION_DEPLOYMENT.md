# 🚀 Production Deployment Guide

Complete guide for deploying watch party to production with high availability and reliability.

---

## 1. Pre-Deployment Checklist

### Code Quality
- [ ] All tests passing (`pytest tests/`)
- [ ] Code coverage > 80%
- [ ] No security vulnerabilities (`bandit -r .`)
- [ ] Code formatted (`black .`)
- [ ] Linting passed (`flake8 .`)

### Configuration
- [ ] Environment variables configured
- [ ] Database migrations ready
- [ ] SSL certificates obtained
- [ ] CDN configured
- [ ] Backup strategy defined

### Infrastructure
- [ ] Servers provisioned
- [ ] Load balancer configured
- [ ] Database replicated
- [ ] Redis cluster ready
- [ ] Monitoring set up

---

## 2. Environment Setup

### Production Environment Variables

```bash
# .env.production
# Flask
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=<generate-secure-key>

# Database
DATABASE_URL=postgresql://user:pass@db-primary:5432/watch_party
DATABASE_REPLICA_URL=postgresql://user:pass@db-replica:5432/watch_party
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

# Redis
REDIS_URL=redis://redis-cluster:6379/0
REDIS_POOL_SIZE=10

# Watch Party
WATCH_PARTY_UPLOAD_DIR=/data/watch_party/uploads
WATCH_PARTY_MAX_MB=10240
WATCH_PARTY_CLEANUP_HOURS=24
WATCH_PARTY_LOG_LEVEL=INFO

# Discord
DISCORD_TOKEN=<bot-token>
DISCORD_CLIENT_ID=<client-id>
DISCORD_CLIENT_SECRET=<client-secret>

# Security
CORS_ORIGINS=https://example.com,https://www.example.com
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax

# Monitoring
SENTRY_DSN=<sentry-dsn>
DATADOG_API_KEY=<datadog-key>

# CDN
CDN_URL=https://cdn.example.com
VIDEO_CDN_URL=https://video-cdn.example.com
```

### Generate Secure Key

```python
import secrets
print(secrets.token_urlsafe(32))
```

---

## 3. Database Setup

### PostgreSQL Configuration

```sql
-- Create database
CREATE DATABASE watch_party;

-- Create user
CREATE USER watch_party_user WITH PASSWORD 'secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE watch_party TO watch_party_user;

-- Create tables
CREATE TABLE watch_rooms (
    id VARCHAR(255) PRIMARY KEY,
    guild_id VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    host_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_guild_id (guild_id),
    INDEX idx_host_id (host_id),
    INDEX idx_created_at (created_at)
);

CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    room_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (room_id) REFERENCES watch_rooms(id),
    INDEX idx_room_id (room_id),
    INDEX idx_created_at (created_at)
);

-- Create indexes
CREATE INDEX idx_watch_rooms_guild_id ON watch_rooms(guild_id);
CREATE INDEX idx_watch_rooms_host_id ON watch_rooms(host_id);
CREATE INDEX idx_chat_messages_room_id ON chat_messages(room_id);
```

### Database Replication

```bash
# Primary server
# postgresql.conf
wal_level = replica
max_wal_senders = 10
wal_keep_size = 1GB

# Replica server
# recovery.conf
standby_mode = 'on'
primary_conninfo = 'host=primary-db port=5432 user=replication password=pass'
```

---

## 4. Redis Setup

### Redis Cluster Configuration

```bash
# redis.conf
port 6379
bind 0.0.0.0
protected-mode yes
daemonize yes
logfile /var/log/redis/redis-server.log
dir /var/lib/redis

# Memory
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec

# Replication
repl-diskless-sync yes
repl-diskless-sync-delay 5
```

### Redis Sentinel (High Availability)

```bash
# sentinel.conf
port 26379
daemonize yes
logfile /var/log/redis/sentinel.log

sentinel monitor mymaster 127.0.0.1 6379 2
sentinel down-after-milliseconds mymaster 30000
sentinel parallel-syncs mymaster 1
sentinel failover-timeout mymaster 180000
```

---

## 5. Web Server Setup

### Gunicorn Configuration

```python
# gunicorn_config.py
import multiprocessing

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"

# Process naming
proc_name = "watch-party"

# Server mechanics
daemon = False
pidfile = "/var/run/gunicorn.pid"
umask = 0
user = "www-data"
group = "www-data"
tmp_upload_dir = "/tmp"

# SSL
keyfile = "/etc/ssl/private/key.pem"
certfile = "/etc/ssl/certs/cert.pem"
ssl_version = "TLSv1_2"
```

### Nginx Configuration

```nginx
# /etc/nginx/sites-available/watch-party
upstream watch_party_backend {
    least_conn;
    
    server localhost:5000 weight=1 max_fails=3 fail_timeout=30s;
    server localhost:5001 weight=1 max_fails=3 fail_timeout=30s;
    server localhost:5002 weight=1 max_fails=3 fail_timeout=30s;
    
    keepalive 32;
}

server {
    listen 80;
    server_name watch.example.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name watch.example.com;
    
    # SSL
    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Compression
    gzip on;
    gzip_types text/plain text/css text/javascript application/json;
    gzip_min_length 1000;
    
    # Logging
    access_log /var/log/nginx/watch-party-access.log;
    error_log /var/log/nginx/watch-party-error.log;
    
    # Proxy
    location / {
        proxy_pass http://watch_party_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_request_buffering off;
    }
    
    # Static files
    location /static/ {
        alias /var/www/watch-party/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Video streaming
    location /watch/stream/ {
        proxy_pass http://watch_party_backend;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;
    }
}
```

---

## 6. Systemd Service

### Service File

```ini
# /etc/systemd/system/watch-party.service
[Unit]
Description=Watch Party Service
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/watch-party

Environment="PATH=/opt/watch-party/venv/bin"
EnvironmentFile=/opt/watch-party/.env.production

ExecStart=/opt/watch-party/venv/bin/gunicorn \
    --config /opt/watch-party/gunicorn_config.py \
    app:app

ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
KillSignal=SIGTERM

Restart=always
RestartSec=10

# Resource limits
LimitNOFILE=65535
LimitNPROC=65535

[Install]
WantedBy=multi-user.target
```

### Enable Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable watch-party
sudo systemctl start watch-party
sudo systemctl status watch-party
```

---

## 7. Monitoring & Logging

### Prometheus Metrics

```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Counters
watch_party_created = Counter('watch_party_created_total', 'Total watch parties created')
watch_party_closed = Counter('watch_party_closed_total', 'Total watch parties closed')
chat_messages_sent = Counter('chat_messages_sent_total', 'Total chat messages sent')

# Histograms
sync_latency = Histogram('sync_latency_seconds', 'Sync latency in seconds')
chat_latency = Histogram('chat_latency_seconds', 'Chat latency in seconds')

# Gauges
active_watch_parties = Gauge('active_watch_parties', 'Number of active watch parties')
total_viewers = Gauge('total_viewers', 'Total number of viewers')
```

### Logging Configuration

```python
# logging_config.py
import logging
import logging.handlers

# Create logger
logger = logging.getLogger('watch_party')
logger.setLevel(logging.INFO)

# File handler
file_handler = logging.handlers.RotatingFileHandler(
    '/var/log/watch-party/app.log',
    maxBytes=10485760,  # 10MB
    backupCount=10
)
file_handler.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers
logger.addHandler(file_handler)
logger.addHandler(console_handler)
```

### Sentry Error Tracking

```python
# app.py
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    integrations=[FlaskIntegration()],
    traces_sample_rate=0.1,
    environment=os.getenv('FLASK_ENV'),
)
```

---

## 8. Backup & Recovery

### Automated Backups

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/watch-party"
DATE=$(date +%Y%m%d_%H%M%S)

# Database backup
pg_dump -h localhost -U watch_party_user watch_party | \
    gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Upload directory backup
tar -czf "$BACKUP_DIR/uploads_$DATE.tar.gz" \
    /data/watch_party/uploads

# Redis backup
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb "$BACKUP_DIR/redis_$DATE.rdb"

# Keep only last 30 days
find "$BACKUP_DIR" -type f -mtime +30 -delete

echo "Backup completed: $DATE"
```

### Backup Schedule

```bash
# /etc/cron.d/watch-party-backup
0 2 * * * root /opt/watch-party/backup.sh >> /var/log/watch-party/backup.log 2>&1
```

### Recovery Procedure

```bash
#!/bin/bash
# restore.sh

BACKUP_FILE=$1

# Restore database
gunzip -c "$BACKUP_FILE" | psql -h localhost -U watch_party_user watch_party

# Restore uploads
tar -xzf "${BACKUP_FILE%.sql.gz}.tar.gz" -C /

# Restart service
systemctl restart watch-party
```

---

## 9. Security Hardening

### Firewall Rules

```bash
# UFW (Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow internal services
sudo ufw allow from 10.0.0.0/8 to any port 5432  # PostgreSQL
sudo ufw allow from 10.0.0.0/8 to any port 6379  # Redis

sudo ufw enable
```

### SSL/TLS Certificates

```bash
# Using Let's Encrypt
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot certonly --nginx -d watch.example.com

# Auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### Security Headers

```python
# app.py
@app.after_request
def set_security_headers(response):
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response
```

---

## 10. Health Checks

### Health Check Endpoint

```python
# app.py
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    checks = {
        'status': 'healthy',
        'database': check_database(),
        'redis': check_redis(),
        'disk_space': check_disk_space(),
    }
    
    if all(checks.values()):
        return jsonify(checks), 200
    else:
        return jsonify(checks), 503

def check_database():
    """Check database connectivity"""
    try:
        db.session.execute('SELECT 1')
        return True
    except:
        return False

def check_redis():
    """Check Redis connectivity"""
    try:
        redis_client.ping()
        return True
    except:
        return False

def check_disk_space():
    """Check available disk space"""
    import shutil
    stat = shutil.disk_usage('/')
    free_gb = stat.free / (1024**3)
    return free_gb > 10  # At least 10GB free
```

---

## 11. Deployment Steps

### 1. Prepare Server

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install dependencies
sudo apt-get install -y python3.11 python3-pip postgresql redis-server nginx

# Create application user
sudo useradd -m -s /bin/bash www-data

# Create directories
sudo mkdir -p /opt/watch-party
sudo mkdir -p /data/watch_party/uploads
sudo mkdir -p /var/log/watch-party
sudo mkdir -p /backups/watch-party

# Set permissions
sudo chown -R www-data:www-data /opt/watch-party
sudo chown -R www-data:www-data /data/watch_party
sudo chown -R www-data:www-data /var/log/watch-party
```

### 2. Deploy Application

```bash
# Clone repository
cd /opt/watch-party
git clone https://github.com/your-org/watch-party.git .

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy configuration
cp .env.example .env.production
# Edit .env.production with production values

# Run migrations
python manage.py db upgrade
```

### 3. Start Services

```bash
# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Start Nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# Start Watch Party
sudo systemctl start watch-party
sudo systemctl enable watch-party
```

### 4. Verify Deployment

```bash
# Check services
sudo systemctl status watch-party
sudo systemctl status nginx
sudo systemctl status postgresql
sudo systemctl status redis-server

# Check logs
tail -f /var/log/watch-party/app.log
tail -f /var/log/nginx/watch-party-access.log

# Test health check
curl https://watch.example.com/health
```

---

## 12. Monitoring Dashboard

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Watch Party Monitoring",
    "panels": [
      {
        "title": "Active Watch Parties",
        "targets": [
          {
            "expr": "active_watch_parties"
          }
        ]
      },
      {
        "title": "Total Viewers",
        "targets": [
          {
            "expr": "total_viewers"
          }
        ]
      },
      {
        "title": "Sync Latency",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, sync_latency_seconds)"
          }
        ]
      },
      {
        "title": "Chat Messages/sec",
        "targets": [
          {
            "expr": "rate(chat_messages_sent_total[1m])"
          }
        ]
      }
    ]
  }
}
```

---

## Deployment Checklist

- [ ] All tests passing
- [ ] Code reviewed and approved
- [ ] Environment variables configured
- [ ] Database migrations tested
- [ ] SSL certificates obtained
- [ ] Backups configured
- [ ] Monitoring set up
- [ ] Health checks working
- [ ] Load balancer configured
- [ ] Firewall rules applied
- [ ] Security headers enabled
- [ ] Logging configured
- [ ] Alerting configured
- [ ] Runbooks created
- [ ] Team trained

---

## Rollback Procedure

```bash
#!/bin/bash
# rollback.sh

VERSION=$1

# Stop service
sudo systemctl stop watch-party

# Checkout previous version
cd /opt/watch-party
git checkout $VERSION

# Reinstall dependencies
source venv/bin/activate
pip install -r requirements.txt

# Run migrations
python manage.py db downgrade

# Start service
sudo systemctl start watch-party

# Verify
curl https://watch.example.com/health
```

---

**Production deployment complete! Monitor closely and iterate.** 🚀
