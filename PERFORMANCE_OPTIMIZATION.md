# 🚀 Watch Party Performance Optimization Guide

## Overview

Complete guide for optimizing watch party performance for high-load scenarios (100+ concurrent viewers).

---

## 1. Database Optimization

### Connection Pooling

```python
# config.py
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    'postgresql://user:pass@localhost/watch_party',
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
    pool_recycle=3600,
    pool_pre_ping=True,
)
```

### Query Optimization

```python
# Avoid N+1 queries
# Bad
for room in rooms:
    viewers = get_viewers(room.id)  # N queries

# Good
rooms_with_viewers = (
    db.session.query(Room)
    .options(joinedload(Room.viewers))
    .all()
)
```

### Indexing

```python
# models.py
class WatchRoom(db.Model):
    __tablename__ = 'watch_rooms'
    
    id = db.Column(db.String, primary_key=True, index=True)
    guild_id = db.Column(db.String, index=True)
    host_id = db.Column(db.String, index=True)
    created_at = db.Column(db.DateTime, index=True)
    is_active = db.Column(db.Boolean, index=True)
```

---

## 2. Caching Strategy

### Redis Caching

```python
# cache.py
import redis
from functools import wraps

redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True,
    socket_keepalive=True,
    socket_keepalive_options={
        1: 1,  # TCP_KEEPIDLE
        2: 1,  # TCP_KEEPINTVL
        3: 3,  # TCP_KEEPCNT
    }
)

def cache_result(ttl=300):
    """Cache function result"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            
            # Try cache
            result = redis_client.get(cache_key)
            if result:
                return json.loads(result)
            
            # Compute and cache
            result = func(*args, **kwargs)
            redis_client.setex(
                cache_key,
                ttl,
                json.dumps(result)
            )
            return result
        return wrapper
    return decorator

@cache_result(ttl=60)
def get_room_state(room_id):
    """Get room state (cached for 60s)"""
    room = _watch_rooms.get(room_id)
    return room.to_dict() if room else None
```

### Cache Invalidation

```python
def invalidate_room_cache(room_id):
    """Invalidate room cache"""
    cache_keys = redis_client.keys(f"get_room_state:{room_id}*")
    if cache_keys:
        redis_client.delete(*cache_keys)

# On room update
@socketio.on("watch_play")
def on_watch_play(data):
    room_id = data.get("room_id")
    # ... update room ...
    invalidate_room_cache(room_id)
```

---

## 3. Socket.IO Optimization

### Message Compression

```python
# app.py
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    engineio_logger=False,
    logger=False,
    compression='gzip',  # Enable compression
    ping_timeout=60,
    ping_interval=25,
)
```

### Batch Updates

```python
# Instead of sending individual updates
# Bad
for viewer in room.viewers:
    emit("watch_sync", sync_data, room=f"watch_{room_id}")

# Good - send once to room
emit("watch_sync", sync_data, room=f"watch_{room_id}")
```

### Reduce Payload Size

```python
# Minimize data sent
# Bad
emit("watch_sync", {
    "action": "sync",
    "current_time": 1234.5,
    "is_playing": True,
    "room_id": "abc123",
    "host_id": "111111111",
    "host_name": "Admin",
    "title": "Movie Night",
    "video_url": "https://example.com/video.mp4",
})

# Good - only essential data
emit("watch_sync", {
    "a": "sync",  # action
    "t": 1234.5,  # time
    "p": True,    # playing
})
```

---

## 4. Streaming Optimization

### Adaptive Bitrate

```python
# watch_party_config.py
STREAMING_BITRATES = {
    "low": 1000,      # 1 Mbps
    "medium": 2500,   # 2.5 Mbps
    "high": 5000,     # 5 Mbps
    "ultra": 10000,   # 10 Mbps
}

def get_optimal_bitrate(bandwidth: int) -> str:
    """Get optimal bitrate based on available bandwidth"""
    if bandwidth < 1500:
        return "low"
    elif bandwidth < 3000:
        return "medium"
    elif bandwidth < 7000:
        return "high"
    else:
        return "ultra"
```

### Chunk Optimization

```python
# Adjust chunk size based on network conditions
CHUNK_SIZES = {
    "low": 32768,      # 32KB
    "medium": 65536,   # 64KB
    "high": 131072,    # 128KB
    "ultra": 262144,   # 256KB
}

def get_chunk_size(bandwidth: str) -> int:
    """Get chunk size for bandwidth"""
    return CHUNK_SIZES.get(bandwidth, 65536)
```

---

## 5. Memory Optimization

### Limit Room Storage

```python
# watch_party_config.py
MAX_ROOMS_IN_MEMORY = 100
MAX_CHAT_HISTORY = 200
MAX_VIEWERS_PER_ROOM = 500

# Implement cleanup
def cleanup_old_rooms():
    """Remove inactive rooms from memory"""
    current_time = time.time()
    inactive_threshold = 3600  # 1 hour
    
    rooms_to_delete = []
    for room_id, room in _watch_rooms.items():
        if len(room.viewers) == 0:
            if current_time - room.last_activity > inactive_threshold:
                rooms_to_delete.append(room_id)
    
    for room_id in rooms_to_delete:
        del _watch_rooms[room_id]
        logger.info(f"Cleaned up room: {room_id}")

# Schedule cleanup
schedule.every(30).minutes.do(cleanup_old_rooms)
```

### Optimize Data Structures

```python
# Use efficient data structures
# Bad - list of dicts
viewers = [
    {"id": "1", "name": "User1", "role": 1},
    {"id": "2", "name": "User2", "role": 2},
]

# Good - dict with id as key
viewers = {
    "1": {"name": "User1", "role": 1},
    "2": {"name": "User2", "role": 2},
}
```

---

## 6. CPU Optimization

### Async Processing

```python
# Use async for I/O operations
import asyncio

async def process_chat_message(room_id, message):
    """Process chat message asynchronously"""
    # Validate message
    await validate_message(message)
    
    # Store in database
    await db.store_message(room_id, message)
    
    # Broadcast to viewers
    emit("watch_chat_msg", message, room=f"watch_{room_id}")

@socketio.on("watch_chat")
def on_watch_chat(data):
    room_id = data.get("room_id")
    message = data.get("message")
    
    # Process asynchronously
    socketio.start_background_task(
        process_chat_message,
        room_id,
        message
    )
```

### Lazy Loading

```python
# Load data only when needed
class WatchRoom:
    def __init__(self, room_id):
        self.room_id = room_id
        self._chat_history = None
    
    @property
    def chat_history(self):
        """Lazy load chat history"""
        if self._chat_history is None:
            self._chat_history = load_chat_history(self.room_id)
        return self._chat_history
```

---

## 7. Network Optimization

### HTTP/2 Server Push

```python
# nginx.conf
server {
    listen 443 ssl http2;
    
    # Enable HTTP/2 server push
    http2_push_preload on;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

### Compression

```python
# app.py
from flask_compress import Compress

Compress(app)

# Or configure manually
@app.after_request
def compress_response(response):
    if response.content_length > 1000:
        response.direct_passthrough = False
    return response
```

### CDN Integration

```python
# Use CDN for static assets and videos
STATIC_CDN = "https://cdn.example.com"
VIDEO_CDN = "https://video-cdn.example.com"

def get_video_url(room_id):
    """Get video URL from CDN"""
    if use_cdn:
        return f"{VIDEO_CDN}/watch/stream/{room_id}"
    else:
        return f"/watch/stream/{room_id}"
```

---

## 8. Load Balancing

### Nginx Load Balancer

```nginx
# nginx.conf
upstream watch_party_backend {
    least_conn;  # Use least connections algorithm
    
    server localhost:5000 weight=1;
    server localhost:5001 weight=1;
    server localhost:5002 weight=1;
    
    keepalive 32;
}

server {
    listen 80;
    
    location / {
        proxy_pass http://watch_party_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Session Affinity

```python
# Ensure user stays on same server
# Use sticky sessions with load balancer
# nginx.conf
upstream watch_party_backend {
    hash $cookie_jsessionid consistent;
    
    server localhost:5000;
    server localhost:5001;
    server localhost:5002;
}
```

---

## 9. Monitoring & Profiling

### Performance Monitoring

```python
# monitor.py
import time
from functools import wraps

def monitor_performance(func):
    """Monitor function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        
        if duration > 1.0:  # Log slow operations
            logger.warning(
                f"Slow operation: {func.__name__} took {duration:.2f}s"
            )
        
        return result
    return wrapper

@monitor_performance
def on_watch_play(data):
    # ... implementation ...
    pass
```

### Memory Profiling

```bash
# Install memory profiler
pip install memory-profiler

# Profile memory usage
python -m memory_profiler watch_party.py

# Or use in code
from memory_profiler import profile

@profile
def on_watch_join(data):
    # ... implementation ...
    pass
```

### CPU Profiling

```python
# profile.py
import cProfile
import pstats

def profile_function():
    """Profile function execution"""
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Run code
    on_watch_play({"room_id": "test"})
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)  # Top 10 functions
```

---

## 10. Configuration Tuning

### Optimal Settings for 100+ Viewers

```python
# watch_party_config.py

# Streaming
CHUNK_SIZE = 131072  # 128KB chunks
BUFFER_SIZE = 2 * 1024 * 1024  # 2MB buffer
STREAM_TIMEOUT = 60

# Sync
SYNC_INTERVAL_SECONDS = 60  # Sync less frequently
SYNC_TOLERANCE_SECONDS = 2.0  # More tolerance

# Chat
MAX_CHAT_LENGTH = 500
MAX_CHAT_HISTORY = 100  # Reduce history
CHAT_RATE_LIMIT = 5  # Stricter rate limit

# Performance
MAX_CONCURRENT_VIEWERS = 500
VIEWER_TIMEOUT_SECONDS = 600  # 10 minutes
CLEANUP_INTERVAL_MINUTES = 30

# Database
DB_POOL_SIZE = 20
DB_MAX_OVERFLOW = 40
DB_POOL_RECYCLE = 3600

# Redis
REDIS_POOL_SIZE = 10
REDIS_SOCKET_KEEPALIVE = True

# Socket.IO
SOCKETIO_PING_INTERVAL = 25
SOCKETIO_PING_TIMEOUT = 60
SOCKETIO_COMPRESSION = 'gzip'
```

---

## 11. Benchmarking

### Load Testing

```bash
# Install locust
pip install locust

# Create locustfile.py
from locust import HttpUser, task, between

class WatchPartyUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def join_watch_party(self):
        self.client.get("/watch/abc123")
    
    @task
    def send_chat(self):
        self.client.post("/api/watch/chat", json={
            "room_id": "abc123",
            "message": "Hello!"
        })

# Run load test
locust -f locustfile.py --host=http://localhost:5000
```

### Performance Benchmarks

```python
# benchmark.py
import time
import statistics

def benchmark_operation(func, iterations=1000):
    """Benchmark operation performance"""
    times = []
    
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append(end - start)
    
    return {
        "min": min(times),
        "max": max(times),
        "avg": statistics.mean(times),
        "median": statistics.median(times),
        "stdev": statistics.stdev(times),
    }

# Benchmark sync operation
results = benchmark_operation(lambda: on_watch_sync({}))
print(f"Sync operation: {results['avg']*1000:.2f}ms avg")
```

---

## 12. Deployment Optimization

### Docker Optimization

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Use multi-stage build
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run with gunicorn
CMD ["gunicorn", \
     "--workers=4", \
     "--worker-class=gevent", \
     "--worker-connections=1000", \
     "--bind=0.0.0.0:5000", \
     "app:app"]
```

### Kubernetes Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: watch-party
spec:
  replicas: 3
  selector:
    matchLabels:
      app: watch-party
  template:
    metadata:
      labels:
        app: watch-party
    spec:
      containers:
      - name: watch-party
        image: watch-party:latest
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 5
```

---

## Performance Checklist

- [ ] Enable Redis caching
- [ ] Configure database connection pooling
- [ ] Add database indexes
- [ ] Enable Socket.IO compression
- [ ] Implement async processing
- [ ] Set up load balancing
- [ ] Configure CDN for videos
- [ ] Enable HTTP/2
- [ ] Set up monitoring
- [ ] Run load tests
- [ ] Optimize chunk sizes
- [ ] Reduce sync frequency
- [ ] Implement lazy loading
- [ ] Use efficient data structures
- [ ] Set up auto-scaling

---

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Sync latency | <500ms | - |
| Chat latency | <200ms | - |
| Memory per viewer | <1MB | - |
| CPU per viewer | <0.1% | - |
| Concurrent viewers | 500+ | - |
| Throughput | 1000+ msg/s | - |

---

## Resources

- [Flask Performance](https://flask.palletsprojects.com/en/2.3.x/deploying/)
- [Socket.IO Performance](https://python-socketio.readthedocs.io/en/latest/)
- [Redis Optimization](https://redis.io/docs/management/optimization/)
- [Nginx Tuning](https://nginx.org/en/docs/)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)

---

**Performance optimization is ongoing. Monitor, measure, and iterate!** 📊
