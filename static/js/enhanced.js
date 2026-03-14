/**
 * WAN Bot - Enhanced Dashboard JavaScript
 * Features: Theme Toggle, Toast Notifications, Keyboard Shortcuts, Auto-save
 */

// ===== Theme Management =====
class ThemeManager {
    constructor() {
        this.theme = localStorage.getItem('theme') || 'light';
        this.init();
    }
    
    init() {
        this.applyTheme(this.theme);
        this.createToggleButton();
    }
    
    applyTheme(theme) {
        if (theme === 'dark') {
            document.body.classList.add('dark-theme');
        } else {
            document.body.classList.remove('dark-theme');
        }
        this.theme = theme;
        localStorage.setItem('theme', theme);
    }
    
    toggle() {
        const newTheme = this.theme === 'light' ? 'dark' : 'light';
        this.applyTheme(newTheme);
        showToast('Theme changed', `Switched to ${newTheme} mode`, 'success');
    }
    
    createToggleButton() {
        const button = document.createElement('button');
        button.className = 'theme-toggle';
        button.innerHTML = `
            <i class="fas fa-${this.theme === 'light' ? 'moon' : 'sun'}"></i>
            <span>${this.theme === 'light' ? 'Dark' : 'Light'} Mode</span>
        `;
        button.onclick = () => {
            this.toggle();
            button.innerHTML = `
                <i class="fas fa-${this.theme === 'light' ? 'moon' : 'sun'}"></i>
                <span>${this.theme === 'light' ? 'Dark' : 'Light'} Mode</span>
            `;
        };
        document.body.appendChild(button);
    }
}

// ===== Toast Notifications =====
class ToastManager {
    constructor() {
        this.container = this.createContainer();
    }
    
    createContainer() {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }
    
    show(title, message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icons = {
            success: 'check-circle',
            warning: 'exclamation-triangle',
            danger: 'times-circle',
            info: 'info-circle'
        };
        
        toast.innerHTML = `
            <div class="toast-icon">
                <i class="fas fa-${icons[type]}"></i>
            </div>
            <div class="toast-content">
                <div class="toast-title">${title}</div>
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        this.container.appendChild(toast);
        
        // Trigger animation
        setTimeout(() => toast.classList.add('show'), 10);
        
        // Auto remove
        if (duration > 0) {
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }
        
        return toast;
    }
}

// Global toast function
const toastManager = new ToastManager();
function showToast(title, message, type = 'info', duration = 3000) {
    return toastManager.show(title, message, type, duration);
}

// ===== Keyboard Shortcuts =====
class KeyboardShortcuts {
    constructor() {
        this.shortcuts = new Map();
        this.init();
    }
    
    init() {
        document.addEventListener('keydown', (e) => this.handleKeyPress(e));
        
        // Register default shortcuts
        this.register('ctrl+k', () => this.openSearch());
        this.register('ctrl+/', () => this.showShortcuts());
        this.register('ctrl+b', () => this.toggleSidebar());
        this.register('ctrl+t', () => themeManager.toggle());
        this.register('esc', () => this.closeModals());
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
        const searchBox = document.querySelector('.search-box input');
        if (searchBox) {
            searchBox.focus();
            searchBox.select();
        }
    }
    
    showShortcuts() {
        const shortcuts = [
            { keys: 'Ctrl + K', action: 'Open search' },
            { keys: 'Ctrl + /', action: 'Show shortcuts' },
            { keys: 'Ctrl + B', action: 'Toggle sidebar' },
            { keys: 'Ctrl + T', action: 'Toggle theme' },
            { keys: 'Esc', action: 'Close modals' }
        ];
        
        let html = '<div class="shortcuts-modal"><h3>Keyboard Shortcuts</h3><ul>';
        shortcuts.forEach(s => {
            html += `<li><kbd>${s.keys}</kbd><span>${s.action}</span></li>`;
        });
        html += '</ul></div>';
        
        showToast('Keyboard Shortcuts', html, 'info', 0);
    }
    
    toggleSidebar() {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.toggle('collapsed');
        }
    }
    
    closeModals() {
        document.querySelectorAll('.modal, .toast').forEach(el => el.remove());
    }
}

// ===== Auto-save Manager =====
class AutoSaveManager {
    constructor() {
        this.timers = new Map();
        this.delay = 2000; // 2 seconds
    }
    
    enable(formId) {
        const form = document.getElementById(formId);
        if (!form) return;
        
        form.addEventListener('input', (e) => {
            this.scheduleAutoSave(formId, form);
        });
    }
    
    scheduleAutoSave(formId, form) {
        // Clear existing timer
        if (this.timers.has(formId)) {
            clearTimeout(this.timers.get(formId));
        }
        
        // Set new timer
        const timer = setTimeout(() => {
            this.save(form);
        }, this.delay);
        
        this.timers.set(formId, timer);
    }
    
    async save(form) {
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);
        
        try {
            // Save to localStorage as backup
            localStorage.setItem(`autosave_${form.id}`, JSON.stringify(data));
            
            // Show subtle notification
            const indicator = document.createElement('span');
            indicator.className = 'autosave-indicator';
            indicator.textContent = '✓ Saved';
            indicator.style.cssText = 'position: fixed; bottom: 20px; right: 20px; padding: 8px 16px; background: var(--accent-success); color: white; border-radius: 8px; font-size: 14px; opacity: 0; transition: opacity 0.3s;';
            document.body.appendChild(indicator);
            
            setTimeout(() => indicator.style.opacity = '1', 10);
            setTimeout(() => {
                indicator.style.opacity = '0';
                setTimeout(() => indicator.remove(), 300);
            }, 2000);
            
        } catch (error) {
            console.error('Auto-save failed:', error);
        }
    }
    
    restore(formId) {
        const saved = localStorage.getItem(`autosave_${formId}`);
        if (!saved) return false;
        
        try {
            const data = JSON.parse(saved);
            const form = document.getElementById(formId);
            if (!form) return false;
            
            Object.entries(data).forEach(([key, value]) => {
                const input = form.querySelector(`[name="${key}"]`);
                if (input) input.value = value;
            });
            
            showToast('Draft Restored', 'Your previous changes have been restored', 'info');
            return true;
        } catch (error) {
            console.error('Restore failed:', error);
            return false;
        }
    }
}

// ===== Advanced Search =====
class SearchManager {
    constructor() {
        this.searchBox = null;
        this.results = [];
    }
    
    init(searchBoxSelector) {
        this.searchBox = document.querySelector(searchBoxSelector);
        if (!this.searchBox) return;
        
        this.searchBox.addEventListener('input', (e) => {
            this.search(e.target.value);
        });
    }
    
    search(query) {
        if (!query || query.length < 2) {
            this.hideResults();
            return;
        }
        
        // Fuzzy search implementation
        const items = this.getSearchableItems();
        const results = items.filter(item => {
            return this.fuzzyMatch(query.toLowerCase(), item.text.toLowerCase());
        });
        
        this.showResults(results);
    }
    
    fuzzyMatch(query, text) {
        let queryIndex = 0;
        for (let i = 0; i < text.length && queryIndex < query.length; i++) {
            if (text[i] === query[queryIndex]) {
                queryIndex++;
            }
        }
        return queryIndex === query.length;
    }
    
    getSearchableItems() {
        // Get all searchable elements
        const items = [];
        document.querySelectorAll('[data-searchable]').forEach(el => {
            items.push({
                element: el,
                text: el.textContent,
                type: el.dataset.searchType || 'general'
            });
        });
        return items;
    }
    
    showResults(results) {
        // Implementation for showing search results
        console.log('Search results:', results);
    }
    
    hideResults() {
        // Implementation for hiding search results
    }
}

// ===== Loading States =====
function showLoading(element) {
    if (typeof element === 'string') {
        element = document.querySelector(element);
    }
    if (!element) return;
    
    element.classList.add('loading-state');
    element.innerHTML = '<div class="loading"></div>';
}

function hideLoading(element, content) {
    if (typeof element === 'string') {
        element = document.querySelector(element);
    }
    if (!element) return;
    
    element.classList.remove('loading-state');
    if (content) {
        element.innerHTML = content;
    }
}

// ===== API Helper =====
class APIClient {
    constructor(baseURL = '/api') {
        this.baseURL = baseURL;
    }
    
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };
        
        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Request failed');
            }
            
            return await response.json();
        } catch (error) {
            showToast('Error', error.message, 'danger');
            throw error;
        }
    }
    
    get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
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
        return this.request(endpoint, { method: 'DELETE' });
    }
}

// ===== Utility Functions =====
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (days > 7) {
        return date.toLocaleDateString();
    }
    if (days > 0) {
        return `${days} day${days > 1 ? 's' : ''} ago`;
    }
    if (hours > 0) {
        return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    }
    if (minutes > 0) {
        return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
    }
    return 'Just now';
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// ===== Initialize Everything =====
let themeManager, keyboardShortcuts, autoSaveManager, searchManager, apiClient;

document.addEventListener('DOMContentLoaded', () => {
    // Initialize managers
    themeManager = new ThemeManager();
    keyboardShortcuts = new KeyboardShortcuts();
    autoSaveManager = new AutoSaveManager();
    searchManager = new SearchManager();
    apiClient = new APIClient();
    
    // Initialize search
    searchManager.init('.search-box input');
    
    // Add animation classes to elements
    document.querySelectorAll('.card').forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
        card.classList.add('animate-slide-up');
    });
    
    // Log initialization
    console.log('🚀 WAN Bot Dashboard Enhanced - Initialized');
    console.log('✨ Features: Theme Toggle, Toasts, Keyboard Shortcuts, Auto-save');
});

// Export for use in other scripts
window.WanBot = {
    themeManager,
    showToast,
    keyboardShortcuts,
    autoSaveManager,
    searchManager,
    apiClient,
    formatNumber,
    formatDate,
    debounce,
    throttle,
    showLoading,
    hideLoading
};
