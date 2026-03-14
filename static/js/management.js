// WAN Bot - Server Management JavaScript
let currentServer = null;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadServers();
});

// Load servers
async function loadServers() {
    try {
        const response = await fetch('/api/servers');
        const data = await response.json();
        
        const selector = document.getElementById('serverSelector');
        selector.innerHTML = '<option value="">Select a server...</option>';
        
        data.servers.forEach(server => {
            const option = document.createElement('option');
            option.value = server.id;
            option.textContent = server.name;
            selector.appendChild(option);
        });
    } catch (error) {
        showNotification('Failed to load servers', 'error');
    }
}

// Select server
function selectServer(serverId) {
    currentServer = serverId;
    if (serverId) {
        loadServerData(serverId);
    }
}

// Load server data
async function loadServerData(serverId) {
    try {
        const response = await fetch(`/api/server/${serverId}`);
        const data = await response.json();
        
        displayServerInfo(data);
        displayRoles(data.roles);
        displayChannels(data.channels);
        displayMembers(serverId);
    } catch (error) {
        showNotification('Failed to load server data', 'error');
    }
}

// Display server info
function displayServerInfo(server) {
    document.getElementById('serverName').textContent = server.name;
    document.getElementById('serverMembers').textContent = server.members.total;
    if (server.icon) {
        document.getElementById('serverIcon').src = server.icon;
    }
}

// Display roles
function displayRoles(roles) {
    const container = document.getElementById('rolesContainer');
    container.innerHTML = '';
    
    roles.forEach(role => {
        const roleCard = document.createElement('div');
        roleCard.className = 'role-card';
        roleCard.innerHTML = `
            <div class="role-color" style="background-color: ${role.color}"></div>
            <div class="role-info">
                <div class="role-name">${role.name}</div>
                <div class="role-members">${role.members} members</div>
            </div>
            <div class="role-actions">
                <button onclick="editRole(${role.id})" class="btn-icon"><i class="fas fa-edit"></i></button>
                <button onclick="deleteRole(${role.id})" class="btn-icon"><i class="fas fa-trash"></i></button>
            </div>
        `;
        container.appendChild(roleCard);
    });
}

// Create role
async function createRole() {
    const name = prompt('Enter role name:');
    if (!name) return;
    
    const color = prompt('Enter color (hex, e.g., #FF5733):', '#99AAB5');
    
    try {
        const response = await fetch(`/api/server/${currentServer}/roles`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, color})
        });
        
        const data = await response.json();
        if (data.success) {
            showNotification(`Role "${name}" created!`, 'success');
            loadServerData(currentServer);
        } else {
            showNotification(data.error || 'Failed to create role', 'error');
        }
    } catch (error) {
        showNotification('Failed to create role', 'error');
    }
}

// Delete role
async function deleteRole(roleId) {
    if (!confirm('Are you sure you want to delete this role?')) return;
    
    try {
        const response = await fetch(`/api/server/${currentServer}/roles/${roleId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        if (data.success) {
            showNotification('Role deleted!', 'success');
            loadServerData(currentServer);
        } else {
            showNotification(data.error || 'Failed to delete role', 'error');
        }
    } catch (error) {
        showNotification('Failed to delete role', 'error');
    }
}

// Create channel
async function createChannel() {
    const name = prompt('Enter channel name:');
    if (!name) return;
    
    const type = prompt('Enter type (text/voice/category):', 'text');
    
    try {
        const response = await fetch(`/api/server/${currentServer}/channels`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, type})
        });
        
        const data = await response.json();
        if (data.success) {
            showNotification(`Channel "${name}" created!`, 'success');
            loadServerData(currentServer);
        } else {
            showNotification(data.error || 'Failed to create channel', 'error');
        }
    } catch (error) {
        showNotification('Failed to create channel', 'error');
    }
}

// Assign badge
async function assignBadge(memberId) {
    const badge = prompt('Enter badge name (Owner/Admin/Manager/Moderator/Helper/Member/VIP):');
    if (!badge) return;
    
    try {
        const response = await fetch(`/api/server/${currentServer}/members/${memberId}/badge`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({badge_name: badge})
        });
        
        const data = await response.json();
        if (data.success) {
            showNotification(data.message, 'success');
        } else {
            showNotification(data.error || 'Failed to assign badge', 'error');
        }
    } catch (error) {
        showNotification('Failed to assign badge', 'error');
    }
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 25px;
        background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3'};
        color: white;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}
