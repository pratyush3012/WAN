/**
 * WAN Bot - Ultimate Dashboard JavaScript
 * Advanced features, animations, and interactions
 */

// ===== Configuration =====
const CONFIG = {
    API_BASE: '/api',
    WS_URL: window.location.origin,
    REFRESH_INTERVAL: 30000, // 30 seconds
    ANIMATION_DURATION: 300,
    CHART_COLORS: [
        '#667eea', '#764ba2', '#f093fb', '#f5576c',
        '#4facfe', '#00f2fe', '#43e97b', '#38f9d7'
    ]
};

// ===== State Management =====
class DashboardState {
    constructor() {
        this.data = {
            servers: [],
            currentServer: null,
            user: null,
            stats: {},
            notifications: []
        };
        this.listeners = new Map();
    }
    
    set(key, value) {
        this.data[key] = value;
        this.notify(key, value);
    }
    
    get(key) {
        return this.data[key];
    }
    
    subscribe(key, callback) {
        if (!this.listeners.has(key)) {
            this.listeners.set(key, []);
        }
        this.listeners.get(key).push(callback);
    }
    
    notify(key, value) {
        if (this.listeners.has(key)) {
            this.listeners.get(key).forEach(callback => callback(value));
        }
    }
}

const state = new DashboardState();

// ===== API Client =====
class APIClient {
    constructor(baseURL) {
        this.baseURL = baseURL;
        this.cache = new Map();
    }
    
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const cacheKey = `${options.method || 'GET'}_${endpoint}`;
        
        // Check cache for GET requests
        if (!options.method || options.method === 'GET') {
            if (this.cache.has(cacheKey)) {
                const cached = this.cache.get(cacheKey);
                if (Date.now() - cached.timestamp < 60000) { // 1 minute cache
                    return cached.data;
                }
            }
        }
        
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Cache GET requests
            if (!options.method || options.method === 'GET') {
                this.cache.set(cacheKey, {
                    data,
                    timestamp: Date.now()
                });
            }
            
            return data;
        } catch (error) {
            console.error('API Error:', error);
            showNotification('Error', error.message, 'error');
            throw error;
        }
    }
    
    get(endpoint) {
        return this.request(endpoint);
    }
    
    post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }
    
    delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE'
        });
    }
    
    clearCache() {
        this.cache.clear();
    }
}

const api = new APIClient(CONFIG.API_BASE);

// ===== WebSocket Manager =====
class WebSocketManager {
    constructor(url) {
        this.url = url;
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.handlers = new Map();
    }
    
    connect() {
        try {
            this.socket = io(this.url, {
                transports: ['websocket', 'polling'],
                reconnection: true,
                reconnectionDelay: this.reconnectDelay,
                reconnectionAttempts: this.maxReconnectAttempts
            });
            
            this.socket.on('connect', () => {
                console.log('✅ WebSocket connected');
                this.reconnectAttempts = 0;
                showNotification('Connected', 'Real-time updates enabled', 'success');
            });
            
            this.socket.on('disconnect', () => {
                console.log('❌ WebSocket disconnected');
                showNotification('Disconnected', 'Attempting to reconnect...', 'warning');
            });
            
            this.socket.on('error', (error) => {
                console.error('WebSocket error:', error);
            });
            
            // Register custom event handlers
            this.handlers.forEach((handler, event) => {
                this.socket.on(event, handler);
            });
            
        } catch (error) {
            console.error('WebSocket connection failed:', error);
        }
    }
    
    on(event, handler) {
        this.handlers.set(event, handler);
        if (this.socket) {
            this.socket.on(event, handler);
        }
    }
    
    emit(event, data) {
        if (this.socket && this.socket.connected) {
            this.socket.emit(event, data);
        }
    }
    
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
    }
}

const ws = new WebSocketManager(CONFIG.WS_URL);

// ===== Notification System =====
class NotificationManager {
    constructor() {
        this.container = this.createContainer();
        this.queue = [];
        this.maxVisible = 5;
    }
    
    createContainer() {
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                display: flex;
                flex-direction: column;
                gap: 10px;
                max-width: 400px;
            `;
            document.body.appendChild(container);
        }
        return container;
    }
    
    show(title, message, type = 'info', duration = 5000) {
        const notification = this.createNotification(title, message, type);
        
        // Add to queue if too many visible
        const visible = this.container.children.length;
        if (visible >= this.maxVisible) {
            this.queue.push({ title, message, type, duration });
            return;
        }
        
        this.container.appendChild(notification);
        
        // Animate in
        setTimeout(() => notification.classList.add('show'), 10);
        
        // Auto remove
        if (duration > 0) {
            setTimeout(() => this.remove(notification), duration);
        }
        
        return notification;
    }
    
    createNotification(title, message, type) {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type} glass`;
        
        const icons = {
            success: 'check-circle',
            error: 'times-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        };
        
        const colors = {
            success: '#43e97b',
            error: '#f56565',
            warning: '#ed8936',
            info: '#4facfe'
        };
        
        notification.style.cssText = `
            padding: 1rem 1.5rem;
            border-radius: 15px;
            border-left: 4px solid ${colors[type]};
            display: flex;
            align-items: flex-start;
            gap: 1rem;
            opacity: 0;
            transform: translateX(400px);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer;
        `;
        
        notification.innerHTML = `
            <div style="font-size: 1.5rem; color: ${colors[type]};">
                <i class="fas fa-${icons[type]}"></i>
            </div>
            <div style="flex: 1;">
                <div style="font-weight: 600; margin-bottom: 0.25rem;">${title}</div>
                <div style="font-size: 0.875rem; opacity: 0.8;">${message}</div>
            </div>
            <button onclick="this.parentElement.remove()" style="background: none; border: none; color: white; opacity: 0.6; cursor: pointer; font-size: 1.25rem;">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        notification.onclick = () => this.remove(notification);
        
        return notification;
    }
    
    remove(notification) {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(400px)';
        setTimeout(() => {
            notification.remove();
            // Show next in queue
            if (this.queue.length > 0) {
                const next = this.queue.shift();
                this.show(next.title, next.message, next.type, next.duration);
            }
        }, 300);
    }
}

const notificationManager = new NotificationManager();
function showNotification(title, message, type = 'info', duration = 5000) {
    return notificationManager.show(title, message, type, duration);
}

// ===== Chart Manager =====
class ChartManager {
    constructor() {
        this.charts = new Map();
    }
    
    create(canvasId, config) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;
        
        const ctx = canvas.getContext('2d');
        const chart = new Chart(ctx, {
            ...config,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: 'white',
                            font: {
                                family: 'Inter',
                                size: 12
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleFont: {
                            family: 'Inter',
                            size: 14
                        },
                        bodyFont: {
                            family: 'Inter',
                            size: 12
                        },
                        padding: 12,
                        cornerRadius: 8
                    }
                },
                scales: config.type !== 'pie' && config.type !== 'doughnut' ? {
                    y: {
                        ticks: { 
                            color: 'rgba(255, 255, 255, 0.8)',
                            font: { family: 'Inter' }
                        },
                        grid: { 
                            color: 'rgba(255, 255, 255, 0.1)',
                            drawBorder: false
                        }
                    },
                    x: {
                        ticks: { 
                            color: 'rgba(255, 255, 255, 0.8)',
                            font: { family: 'Inter' }
                        },
                        grid: { 
                            color: 'rgba(255, 255, 255, 0.1)',
                            drawBorder: false
                        }
                    }
                } : {},
                ...config.options
            }
        });
        
        this.charts.set(canvasId, chart);
        return chart;
    }
    
    update(canvasId, data) {
        const chart = this.charts.get(canvasId);
        if (chart) {
            chart.data = data;
            chart.update('active');
        }
    }
    
    destroy(canvasId) {
        const chart = this.charts.get(canvasId);
        if (chart) {
            chart.destroy();
            this.charts.delete(canvasId);
        }
    }
    
    destroyAll() {
        this.charts.forEach(chart => chart.destroy());
        this.charts.clear();
    }
}

const chartManager = new ChartManager();

// ===== Page Manager =====
class PageManager {
    constructor() {
        this.currentPage = 'dashboard';
        this.pages = new Map();
        this.initNavigation();
    }
    
    initNavigation() {
        document.querySelectorAll('.liquid-sidebar-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const page = item.dataset.page;
                this.navigate(page);
            });
        });
    }
    
    navigate(page) {
        if (this.currentPage === page) return;
        
        // Update active nav item
        document.querySelectorAll('.liquid-sidebar-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.page === page) {
                item.classList.add('active');
            }
        });
        
        // Load page content
        this.loadPage(page);
        this.currentPage = page;
        
        // Update URL without reload
        history.pushState({ page }, '', `#${page}`);
    }
    
    async loadPage(page) {
        showNotification('Loading', `Loading ${page} page...`, 'info', 2000);
        
        // Page-specific loading logic
        switch(page) {
            case 'dashboard':
                await this.loadDashboard();
                break;
            case 'servers':
                await this.loadServers();
                break;
            case 'analytics':
                await this.loadAnalytics();
                break;
            case 'moderation':
                await this.loadModeration();
                break;
            // Add more pages...
            default:
                showNotification('Coming Soon', `${page} page is under development`, 'info');
        }
    }
    
    async loadDashboard() {
        try {
            const stats = await api.get('/bot/status');
            updateStats(stats);
        } catch (error) {
            console.error('Failed to load dashboard:', error);
        }
    }
    
    async loadServers() {
        try {
            const data = await api.get('/servers');
            displayServers(data.servers);
        } catch (error) {
            console.error('Failed to load servers:', error);
        }
    }
    
    async loadAnalytics() {
        try {
            const data = await api.get('/analytics');
            displayAnalytics(data);
        } catch (error) {
            console.error('Failed to load analytics:', error);
        }
    }
    
    async loadModeration() {
        try {
            const data = await api.get('/moderation/logs');
            displayModerationLogs(data);
        } catch (error) {
            console.error('Failed to load moderation:', error);
        }
    }
}

const pageManager = new PageManager();

// ===== UI Updates =====
function updateStats(stats) {
    const elements = {
        'total-servers': stats.servers,
        'total-users': stats.users?.toLocaleString(),
        'bot-latency': stats.latency + 'ms',
        'bot-uptime': stats.uptime
    };
    
    Object.entries(elements).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) {
            animateValue(element, value);
        }
    });
}

function animateValue(element, newValue) {
    const oldValue = element.textContent;
    element.style.transform = 'scale(1.1)';
    element.style.transition = 'transform 0.3s';
    
    setTimeout(() => {
        element.textContent = newValue;
        element.style.transform = 'scale(1)';
    }, 150);
}

function displayServers(servers) {
    // Implementation for displaying servers
    console.log('Displaying servers:', servers);
}

function displayAnalytics(data) {
    // Implementation for displaying analytics
    console.log('Displaying analytics:', data);
}

function displayModerationLogs(logs) {
    // Implementation for displaying moderation logs
    console.log('Displaying moderation logs:', logs);
}

// ===== Keyboard Shortcuts =====
class KeyboardShortcutManager {
    constructor() {
        this.shortcuts = new Map();
        this.init();
    }
    
    init() {
        document.addEventListener('keydown', (e) => this.handleKeyPress(e));
        
        // Register shortcuts
        this.register('ctrl+k', () => this.openSearch());
        this.register('ctrl+r', () => this.refresh());
        this.register('ctrl+/', () => this.showShortcuts());
        this.register('ctrl+b', () => this.toggleSidebar());
        this.register('esc', () => this.closeModals());
        this.register('ctrl+1', () => pageManager.navigate('dashboard'));
        this.register('ctrl+2', () => pageManager.navigate('servers'));
        this.register('ctrl+3', () => pageManager.navigate('analytics'));
    }
    
    register(combo, callback) {
        this.shortcuts.set(combo.toLowerCase(), callback);
    }
    
    handleKeyPress(e) {
        const key = [];
        if (e.ctrlKey || e.metaKey) key.push('ctrl');
        if (e.shiftKey) key.push('shift');
        if (e.altKey) key.push('alt');
        key.push(e.key.toLowerCase());
        
        const combo = key.join('+');
        const callback = this.shortcuts.get(combo);
        
        if (callback) {
            e.preventDefault();
            callback();
        }
    }
    
    openSearch() {
        showNotification('Search', 'Search feature coming soon!', 'info');
    }
    
    refresh() {
        location.reload();
    }
    
    showShortcuts() {
        const shortcuts = [
            { keys: 'Ctrl + K', action: 'Open search' },
            { keys: 'Ctrl + R', action: 'Refresh page' },
            { keys: 'Ctrl + /', action: 'Show shortcuts' },
            { keys: 'Ctrl + B', action: 'Toggle sidebar' },
            { keys: 'Ctrl + 1-3', action: 'Navigate pages' },
            { keys: 'Esc', action: 'Close modals' }
        ];
        
        let html = '<div style="padding: 1rem;"><h3 style="margin-bottom: 1rem;">Keyboard Shortcuts</h3>';
        shortcuts.forEach(s => {
            html += `<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                <kbd style="padding: 0.25rem 0.5rem; background: rgba(255,255,255,0.1); border-radius: 4px;">${s.keys}</kbd>
                <span style="opacity: 0.8;">${s.action}</span>
            </div>`;
        });
        html += '</div>';
        
        showNotification('Keyboard Shortcuts', html, 'info', 0);
    }
    
    toggleSidebar() {
        const sidebar = document.querySelector('.liquid-sidebar');
        if (sidebar) {
            sidebar.classList.toggle('collapsed');
        }
    }
    
    closeModals() {
        document.querySelectorAll('.modal, .notification').forEach(el => el.remove());
    }
}

const keyboardManager = new KeyboardShortcutManager();

// ===== Auto Refresh =====
class AutoRefreshManager {
    constructor(interval) {
        this.interval = interval;
        this.timer = null;
        this.enabled = true;
    }
    
    start() {
        if (this.timer) return;
        
        this.timer = setInterval(async () => {
            if (this.enabled && document.visibilityState === 'visible') {
                try {
                    const stats = await api.get('/bot/status');
                    updateStats(stats);
                } catch (error) {
                    console.error('Auto-refresh failed:', error);
                }
            }
        }, this.interval);
    }
    
    stop() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }
    
    toggle() {
        this.enabled = !this.enabled;
        showNotification(
            'Auto-refresh',
            `Auto-refresh ${this.enabled ? 'enabled' : 'disabled'}`,
            'info'
        );
    }
}

const autoRefresh = new AutoRefreshManager(CONFIG.REFRESH_INTERVAL);

// ===== Initialize Dashboard =====
async function initDashboard() {
    console.log('🚀 Initializing Ultimate Dashboard...');
    
    try {
        // Connect WebSocket
        ws.connect();
        
        // Setup WebSocket handlers
        ws.on('bot_update', (data) => {
            updateStats(data);
            showNotification('Update', 'Bot stats updated', 'success', 2000);
        });
        
        ws.on('notification', (data) => {
            showNotification(data.title, data.message, data.type);
        });
        
        // Load initial data
        await pageManager.loadDashboard();
        
        // Start auto-refresh
        autoRefresh.start();
        
        // Handle browser back/forward
        window.addEventListener('popstate', (e) => {
            if (e.state && e.state.page) {
                pageManager.navigate(e.state.page);
            }
        });
        
        // Handle visibility change
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                pageManager.loadPage(pageManager.currentPage);
            }
        });
        
        console.log('✅ Dashboard initialized successfully');
        showNotification('Welcome', 'Dashboard loaded successfully!', 'success');
        
    } catch (error) {
        console.error('❌ Dashboard initialization failed:', error);
        showNotification('Error', 'Failed to initialize dashboard', 'error');
    }
}

// ===== Export Global API =====
window.WanDashboard = {
    state,
    api,
    ws,
    showNotification,
    chartManager,
    pageManager,
    keyboardManager,
    autoRefresh,
    initDashboard
};

// ===== Auto-initialize on DOM ready =====
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDashboard);
} else {
    initDashboard();
}
