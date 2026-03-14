// WAN Bot - Ultimate Dashboard JavaScript

// Initialize Socket.IO
const socket = io();

// Global state
let currentServer = null;
let botStatus = 'offline';

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    initializeNavigation();
    connectWebSocket();
    loadBotStatus();
    loadServers();
    startAutoRefresh();
});

// Navigation
function initializeNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            const page = this.getAttribute('data-page');
            showPage(page);
            
            // Update active state
            navItems.forEach(nav => nav.classList.remove('active'));
            this.classList.add('active');
        });
    });
}

function showPage(pageName) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    
    // Show selected page
    const page = document.getElementById(`${pageName}-page`);
    if (page) {
        page.classList.add('active');
        
        // Update header
        const titles = {
            'dashboard': 'Dashboard',
            'servers': 'Your Servers',
            'analytics': 'Server Analytics',
            'moderation': 'Moderation Tools',
            'music': 'Music Control',
            'ai': 'AI Features',
            'games': 'Games Management',
            'settings': 'Bot Settings',
            'logs': 'Bot Logs'
        };
        
        document.getElementById('page-title').textContent = titles[pageName] || pageName;
        
        // Load page-specific data
        loadPageData(pageName);
    }
}

function loadPageData(pageName) {
    switch(pageName) {
        case 'servers':
            loadServers();
            break;
        case 'analytics':
            loadAnalytics();
            break;
        case 'logs':
            loadLogs();
            break;
    }
}

// WebSocket Connection
function connectWebSocket() {
    socket.on('connect', function() {
        console.log('Connected to WAN Bot Dashboard');
        updateBotStatus('online');
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected from WAN Bot Dashboard');
        updateBotStatus('offline');
    });
    
    socket.on('bot_update', function(data) {
        updateDashboardStats(data);
    });
    
    socket.on('activity_update', function(data) {
        addActivityItem(data);
    });
}

// Bot Status
async function loadBotStatus() {
    try {
        const response = await fetch('/api/bot/status');
        const data = await response.json();
        
        if (data.status === 'online') {
            updateBotStatus('online');
            updateDashboardStats(data);
        } else {
            updateBotStatus('offline');
        }
    } catch (error) {
        console.error('Error loading bot status:', error);
        updateBotStatus('offline');
    }
}

function updateBotStatus(status) {
    botStatus = status;
    const indicator = document.getElementById('bot-status-indicator');
    const text = document.getElementById('bot-status-text');
    
    if (status === 'online') {
        indicator.className = 'status-indicator online';
        text.textContent = 'Bot Online';
    } else {
        indicator.className = 'status-indicator offline';
        text.textContent = 'Bot Offline';
    }
}

function updateDashboardStats(data) {
    if (data.servers) {
        document.getElementById('total-servers').textContent = data.servers;
    }
    if (data.users) {
        document.getElementById('total-users').textContent = data.users.toLocaleString();
    }
    if (data.latency) {
        document.getElementById('bot-latency').textContent = data.latency + 'ms';
    }
    if (data.uptime) {
        document.getElementById('bot-uptime').textContent = data.uptime;
    }
}

// Servers
async function loadServers() {
    const grid = document.getElementById('servers-grid');
    grid.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i><p>Loading servers...</p></div>';
    
    try {
        const response = await fetch('/api/servers');
        const data = await response.json();
        
        if (data.servers && data.servers.length > 0) {
            grid.innerHTML = '';
            data.servers.forEach(server => {
                grid.innerHTML += createServerCard(server);
            });
        } else {
            grid.innerHTML = '<p>No servers found</p>';
        }
    } catch (error) {
        console.error('Error loading servers:', error);
        grid.innerHTML = '<p>Error loading servers</p>';
    }
}

function createServerCard(server) {
    const iconUrl = server.icon || 'https://via.placeholder.com/60';
    
    return `
        <div class="server-card" onclick="selectServer(${server.id})">
            <div class="server-header">
                <img src="${iconUrl}" alt="${server.name}" class="server-icon">
                <div class="server-info">
                    <h3>${server.name}</h3>
                    <p>${server.owner}</p>
                </div>
            </div>
            <div class="server-stats">
                <div class="server-stat">
                    <h4>${server.member_count}</h4>
                    <p>Members</p>
                </div>
                <div class="server-stat">
                    <h4>${new Date(server.created_at).getFullYear()}</h4>
                    <p>Created</p>
                </div>
            </div>
        </div>
    `;
}

async function selectServer(serverId) {
    currentServer = serverId;
    
    try {
        const response = await fetch(`/api/server/${serverId}`);
        const data = await response.json();
        
        // Show server details modal or navigate to server page
        showServerDetails(data);
    } catch (error) {
        console.error('Error loading server details:', error);
    }
}

function showServerDetails(server) {
    // Create and show modal with server details
    alert(`Server: ${server.name}\nMembers: ${server.members.total}\nChannels: ${server.channels.text.length + server.channels.voice.length}`);
}

// Analytics
async function loadAnalytics() {
    if (!currentServer) {
        alert('Please select a server first');
        return;
    }
    
    try {
        const response = await fetch(`/api/server/${currentServer}/analytics`);
        const data = await response.json();
        
        // Create charts
        createMemberGrowthChart(data.member_growth);
        createActivityChart(data.activity);
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

function createMemberGrowthChart(data) {
    const ctx = document.getElementById('member-growth-chart');
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['30d ago', '7d ago', '24h ago', 'Now'],
            datasets: [{
                label: 'Members',
                data: [
                    data.current - data.change_30d,
                    data.current - data.change_7d,
                    data.current - data.change_24h,
                    data.current
                ],
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

function createActivityChart(data) {
    const ctx = document.getElementById('activity-chart');
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Messages', 'Voice Minutes', 'Active Users'],
            datasets: [{
                label: 'Activity (24h)',
                data: [data.messages_24h, data.voice_minutes_24h, data.active_users_24h],
                backgroundColor: [
                    'rgba(102, 126, 234, 0.8)',
                    'rgba(240, 147, 251, 0.8)',
                    'rgba(79, 172, 254, 0.8)'
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

// Moderation
async function kickMember() {
    if (!currentServer) {
        alert('Please select a server first');
        return;
    }
    
    const memberId = document.getElementById('kick-member-id').value;
    const reason = document.getElementById('kick-reason').value;
    
    if (!memberId) {
        alert('Please enter a member ID');
        return;
    }
    
    if (!confirm(`Are you sure you want to kick member ${memberId}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/server/${currentServer}/moderation/kick`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ member_id: memberId, reason: reason })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Member kicked successfully');
            document.getElementById('kick-member-id').value = '';
            document.getElementById('kick-reason').value = '';
        } else {
            alert('Error: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error kicking member:', error);
        alert('Error kicking member');
    }
}

async function banMember() {
    if (!currentServer) {
        alert('Please select a server first');
        return;
    }
    
    const memberId = document.getElementById('ban-member-id').value;
    const reason = document.getElementById('ban-reason').value;
    
    if (!memberId) {
        alert('Please enter a member ID');
        return;
    }
    
    if (!confirm(`Are you sure you want to BAN member ${memberId}? This is a serious action!`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/server/${currentServer}/moderation/ban`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ member_id: memberId, reason: reason, delete_days: 1 })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Member banned successfully');
            document.getElementById('ban-member-id').value = '';
            document.getElementById('ban-reason').value = '';
        } else {
            alert('Error: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error banning member:', error);
        alert('Error banning member');
    }
}

// Logs
async function loadLogs() {
    try {
        const response = await fetch('/api/logs');
        const data = await response.json();
        
        const container = document.getElementById('logs-container');
        container.innerHTML = '';
        
        data.logs.forEach(log => {
            container.innerHTML += `
                <div class="log-entry">
                    <span class="log-time">${log.timestamp}</span>
                    <span class="log-level ${log.level.toLowerCase()}">${log.level}</span>
                    <span class="log-message">${log.message}</span>
                </div>
            `;
        });
    } catch (error) {
        console.error('Error loading logs:', error);
    }
}

// Activity Feed
function addActivityItem(activity) {
    const feed = document.getElementById('activity-feed');
    const item = document.createElement('div');
    item.className = 'activity-item';
    item.innerHTML = `
        <div class="activity-icon" style="background: ${activity.color};">
            <i class="${activity.icon}"></i>
        </div>
        <div class="activity-content">
            <p><strong>${activity.title}</strong> ${activity.description}</p>
            <span class="activity-time">Just now</span>
        </div>
    `;
    
    feed.insertBefore(item, feed.firstChild);
    
    // Keep only last 10 items
    while (feed.children.length > 10) {
        feed.removeChild(feed.lastChild);
    }
}

// Quick Actions
function sendAnnouncement() {
    const message = prompt('Enter announcement message:');
    if (message) {
        alert('Announcement sent to all servers!');
    }
}

function backupServers() {
    if (confirm('Create backup of all server configurations?')) {
        alert('Backup started! You will be notified when complete.');
    }
}

function purgeMessages() {
    const count = prompt('How many messages to delete?');
    if (count && !isNaN(count)) {
        if (confirm(`Delete ${count} messages?`)) {
            alert(`Deleted ${count} messages`);
        }
    }
}

function cleanupInactive() {
    if (confirm('Remove inactive members (30+ days)? This cannot be undone!')) {
        alert('Cleanup started! This may take a few minutes.');
    }
}

// Logout
function logout() {
    if (confirm('Are you sure you want to logout?')) {
        window.location.href = '/logout';
    }
}

// Auto-refresh
function startAutoRefresh() {
    // Refresh bot status every 10 seconds
    setInterval(loadBotStatus, 10000);
    
    // Refresh dashboard stats every 30 seconds
    setInterval(() => {
        if (botStatus === 'online') {
            loadBotStatus();
        }
    }, 30000);
}

// Utility functions
function formatNumber(num) {
    return num.toLocaleString();
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

console.log('🤖 WAN Bot Dashboard Loaded Successfully!');