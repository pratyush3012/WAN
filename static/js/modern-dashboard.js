// Modern Dashboard JavaScript
class Dashboard {
    constructor() {
        this.currentServer = null;
        this.socket = null;
        this.init();
    }

    async init() {
        await this.loadServers();
        this.setupEventListeners();
        this.startAutoRefresh();
    }

    async loadServers() {
        try {
            const response = await fetch('/api/servers');
            const data = await response.json();
            
            const selector = document.getElementById('serverSelector');
            if (!selector) return;
            
            selector.innerHTML = '<option value="">Select a server...</option>';
            data.servers.forEach(server => {
                const option = document.createElement('option');
                option.value = server.id;
                option.textContent = `${server.name} (${server.member_count} members)`;
                selector.appendChild(option);
            });

            // Auto-select first server
            if (data.servers.length > 0) {
                selector.value = data.servers[0].id;
                await this.selectServer(data.servers[0].id);
            }
        } catch (error) {
            this.showNotification('Failed to load servers', 'danger');
        }
    }

    async selectServer(serverId) {
        this.currentServer = serverId;
        if (!serverId) return;
        
        this.showLoading(true);
        await Promise.all([
            this.loadServerDetails(serverId),
            this.loadServerMembers(serverId),
            this.loadBotStatus()
        ]);
        this.showLoading(false);
    }

    async loadServerDetails(serverId) {
        try {
            const response = await fetch(`/api/server/${serverId}`);
            if (!response.ok) {
                const err = await response.json();
                console.error('Server details error:', err);
                this.showNotification(`Failed to load server details: ${err.error || response.status}`, 'danger');
                return;
            }
            const data = await response.json();
            this.displayServerInfo(data);
            this.displayRoles(data.roles);
            this.displayChannels(data.channels);
        } catch (error) {
            console.error('loadServerDetails error:', error);
            this.showNotification('Failed to load server details', 'danger');
        }
    }

    async loadServerMembers(serverId) {
        try {
            const response = await fetch(`/api/server/${serverId}/members`);
            const data = await response.json();
            this.displayMembers(data.members);
        } catch (error) {
            console.error('Failed to load members:', error);
        }
    }

    loadSection(section) {
        if (!this.currentServer) return;
        if (section === 'members') this.loadServerMembers(this.currentServer);
        if (section === 'roles' || section === 'channels') {
            fetch(`/api/server/${this.currentServer}`)
                .then(r => r.json())
                .then(data => {
                    if (section === 'roles') this.displayRoles(data.roles);
                    if (section === 'channels') this.displayChannels(data.channels);
                })
                .catch(e => console.error('Failed to refresh section:', e));
        }
    }

    async loadBotStatus() {
        try {
            const response = await fetch('/api/bot/status');
            const data = await response.json();
            this.displayBotStatus(data);
        } catch (error) {
            console.error('Failed to load bot status:', error);
        }
    }

    displayServerInfo(server) {
        document.getElementById('serverName').textContent = server.name;
        document.getElementById('serverMemberCount').textContent = server.members.total;
        document.getElementById('serverChannelCount').textContent = 
            server.channels.text.length + server.channels.voice.length;
        document.getElementById('serverRoleCount').textContent = server.roles.length;
        
        if (server.icon) {
            document.getElementById('serverIcon').src = server.icon;
        }
    }

    displayBotStatus(status) {
        if (status.status === 'online') {
            document.getElementById('botStatus').textContent = 'Online';
            document.getElementById('botStatus').className = 'badge badge-success';
            document.getElementById('botLatency').textContent = `${status.latency}ms`;
            document.getElementById('botUptime').textContent = status.uptime;
        }
    }

    displayRoles(roles) {
        const container = document.getElementById('rolesContainer');
        if (!container) return;
        
        container.innerHTML = '';
        roles.forEach(role => {
            if (role.name === '@everyone') return;
            
            const roleEl = document.createElement('div');
            roleEl.className = 'role-item';
            roleEl.innerHTML = `
                <div class="role-info">
                    <div class="role-color" style="background-color: ${role.color}"></div>
                    <div>
                        <div class="role-name">${role.name}</div>
                        <div class="role-members">${role.members} members</div>
                    </div>
                </div>
                <div class="role-actions">
                    <button class="btn btn-sm btn-primary" onclick="dashboard.editRole(${role.id}, '${role.name}')">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="dashboard.deleteRole(${role.id}, '${role.name}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
            container.appendChild(roleEl);
        });
    }

    displayChannels(channels) {
        const container = document.getElementById('channelsContainer');
        if (!container) return;
        
        container.innerHTML = '';
        
        // Display text channels
        if (channels.text && channels.text.length > 0) {
            const textSection = document.createElement('div');
            textSection.innerHTML = '<h4>📝 Text Channels</h4>';
            channels.text.forEach(channel => {
                textSection.innerHTML += `
                    <div class="channel-item">
                        <span># ${channel.name}</span>
                        <div>
                            <button class="btn btn-sm btn-primary" onclick="dashboard.editChannel(${channel.id})">Edit</button>
                            <button class="btn btn-sm btn-danger" onclick="dashboard.deleteChannel(${channel.id})">Delete</button>
                        </div>
                    </div>
                `;
            });
            container.appendChild(textSection);
        }
        
        // Display voice channels
        if (channels.voice && channels.voice.length > 0) {
            const voiceSection = document.createElement('div');
            voiceSection.innerHTML = '<h4 style="margin-top: 20px;">🔊 Voice Channels</h4>';
            channels.voice.forEach(channel => {
                voiceSection.innerHTML += `
                    <div class="channel-item">
                        <span>🔊 ${channel.name}</span>
                        <div>
                            <button class="btn btn-sm btn-primary" onclick="dashboard.editChannel(${channel.id})">Edit</button>
                            <button class="btn btn-sm btn-danger" onclick="dashboard.deleteChannel(${channel.id})">Delete</button>
                        </div>
                    </div>
                `;
            });
            container.appendChild(voiceSection);
        }
    }

    displayMembers(members) {
        const container = document.getElementById('membersContainer');
        if (!container) return;
        
        container.innerHTML = '';
        const table = document.createElement('table');
        table.className = 'table';
        table.innerHTML = `
            <thead>
                <tr>
                    <th>Member</th>
                    <th>Status</th>
                    <th>Roles</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody id="membersTableBody"></tbody>
        `;
        container.appendChild(table);
        
        const tbody = document.getElementById('membersTableBody');
        members.slice(0, 50).forEach(member => {
            if (member.bot) return;
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        ${member.avatar ? `<img src="${member.avatar}" style="width: 32px; height: 32px; border-radius: 50%;">` : ''}
                        <span>${member.display_name}</span>
                    </div>
                </td>
                <td><span class="badge badge-${member.status === 'online' ? 'success' : 'secondary'}">${member.status}</span></td>
                <td>${member.roles.slice(0, 3).map(r => `<span class="badge badge-primary">${r.name}</span>`).join(' ')}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="dashboard.manageRoles(${member.id}, '${member.name}')">Roles</button>
                    <button class="btn btn-sm btn-success" onclick="dashboard.assignBadge(${member.id}, '${member.name}')">Badge</button>
                </td>
            `;
            tbody.appendChild(row);
        });
    }

    // Role Management
    async createRole() {
        const modal = this.showModal('Create Role', `
            <div class="form-group">
                <label class="form-label">Role Name</label>
                <input type="text" id="roleName" class="form-control" placeholder="Enter role name">
            </div>
            <div class="form-group">
                <label class="form-label">Role Color</label>
                <input type="color" id="roleColor" class="form-control" value="#99AAB5">
            </div>
            <div class="form-group">
                <label class="form-label">
                    <input type="checkbox" id="roleHoist"> Display separately (hoisted)
                </label>
            </div>
            <div class="form-group">
                <label class="form-label">
                    <input type="checkbox" id="roleMentionable"> Mentionable
                </label>
            </div>
        `, async () => {
            const name = document.getElementById('roleName').value;
            const color = document.getElementById('roleColor').value;
            const hoist = document.getElementById('roleHoist').checked;
            const mentionable = document.getElementById('roleMentionable').checked;
            
            if (!name) {
                this.showNotification('Please enter a role name', 'warning');
                return;
            }
            
            try {
                const response = await fetch(`/api/server/${this.currentServer}/roles`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name, color, hoist, mentionable})
                });
                
                const data = await response.json();
                if (data.success) {
                    this.showNotification(`Role "${name}" created successfully!`, 'success');
                    this.loadServerDetails(this.currentServer);
                    this.closeModal();
                } else {
                    this.showNotification(data.error || 'Failed to create role', 'danger');
                }
            } catch (error) {
                this.showNotification('Failed to create role', 'danger');
            }
        });
    }

    async deleteRole(roleId, roleName) {
        if (!confirm(`Are you sure you want to delete the role "${roleName}"?`)) return;
        
        try {
            const response = await fetch(`/api/server/${this.currentServer}/roles/${roleId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            if (data.success) {
                this.showNotification(`Role "${roleName}" deleted!`, 'success');
                this.loadServerDetails(this.currentServer);
            } else {
                this.showNotification(data.error || 'Failed to delete role', 'danger');
            }
        } catch (error) {
            this.showNotification('Failed to delete role', 'danger');
        }
    }

    // Channel Management
    async createChannel() {
        const modal = this.showModal('Create Channel', `
            <div class="form-group">
                <label class="form-label">Channel Name</label>
                <input type="text" id="channelName" class="form-control" placeholder="Enter channel name">
            </div>
            <div class="form-group">
                <label class="form-label">Channel Type</label>
                <select id="channelType" class="form-control">
                    <option value="text">Text Channel</option>
                    <option value="voice">Voice Channel</option>
                    <option value="category">Category</option>
                </select>
            </div>
        `, async () => {
            const name = document.getElementById('channelName').value;
            const type = document.getElementById('channelType').value;
            
            if (!name) {
                this.showNotification('Please enter a channel name', 'warning');
                return;
            }
            
            try {
                const response = await fetch(`/api/server/${this.currentServer}/channels`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name, type})
                });
                
                const data = await response.json();
                if (data.success) {
                    this.showNotification(`Channel "${name}" created!`, 'success');
                    this.loadServerDetails(this.currentServer);
                    this.closeModal();
                } else {
                    this.showNotification(data.error || 'Failed to create channel', 'danger');
                }
            } catch (error) {
                this.showNotification('Failed to create channel', 'danger');
            }
        });
    }

    async deleteChannel(channelId) {
        if (!confirm('Are you sure you want to delete this channel?')) return;
        
        try {
            const response = await fetch(`/api/server/${this.currentServer}/channels/${channelId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            if (data.success) {
                this.showNotification('Channel deleted!', 'success');
                this.loadServerDetails(this.currentServer);
            } else {
                this.showNotification(data.error || 'Failed to delete channel', 'danger');
            }
        } catch (error) {
            this.showNotification('Failed to delete channel', 'danger');
        }
    }

    // Badge Management
    async assignBadge(memberId, memberName) {
        const badges = ['Owner', 'Admin', 'Manager', 'Moderator', 'Helper', 'Member', 'VIP', 'Booster'];
        
        const modal = this.showModal(`Assign Badge to ${memberName}`, `
            <div class="form-group">
                <label class="form-label">Select Badge</label>
                <select id="badgeSelect" class="form-control">
                    ${badges.map(b => `<option value="${b}">${b}</option>`).join('')}
                </select>
            </div>
        `, async () => {
            const badge = document.getElementById('badgeSelect').value;
            
            try {
                const response = await fetch(`/api/server/${this.currentServer}/members/${memberId}/badge`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({badge_name: badge})
                });
                
                const data = await response.json();
                if (data.success) {
                    this.showNotification(data.message, 'success');
                    this.closeModal();
                } else {
                    this.showNotification(data.error || 'Failed to assign badge', 'danger');
                }
            } catch (error) {
                this.showNotification('Failed to assign badge', 'danger');
            }
        });
    }

    // UI Helpers
    showModal(title, content, onConfirm) {
        const modal = document.getElementById('modal');
        document.getElementById('modalTitle').textContent = title;
        document.getElementById('modalBody').innerHTML = content;
        
        const confirmBtn = document.getElementById('modalConfirm');
        confirmBtn.onclick = onConfirm;
        
        modal.classList.add('active');
    }

    closeModal() {
        document.getElementById('modal').classList.remove('active');
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification bg-${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => notification.remove(), 3000);
    }

    showLoading(show) {
        const loader = document.getElementById('loader');
        if (loader) {
            loader.style.display = show ? 'block' : 'none';
        }
    }

    setupEventListeners() {
        document.getElementById('serverSelector')?.addEventListener('change', (e) => {
            this.selectServer(e.target.value);
        });
        
        document.getElementById('modalClose')?.addEventListener('click', () => {
            this.closeModal();
        });
        
        document.getElementById('modalCancel')?.addEventListener('click', () => {
            this.closeModal();
        });
    }

    startAutoRefresh() {
        // Connect to Socket.IO for real-time updates
        this.socket = io();

        this.socket.on('connect', () => {
            console.log('🔴 Real-time connected');
            if (this.currentServer) {
                this.socket.emit('subscribe_server', { server_id: this.currentServer });
            }
        });

        // Re-subscribe when server changes
        const origSelect = this.selectServer?.bind(this);
        if (origSelect) {
            this.selectServer = async (serverId) => {
                if (this.currentServer && this.socket) {
                    this.socket.emit('unsubscribe_server', { server_id: this.currentServer });
                }
                await origSelect(serverId);
                if (this.socket?.connected) {
                    this.socket.emit('subscribe_server', { server_id: serverId });
                }
            };
        }

        // Real-time event handlers — refresh relevant section automatically
        this.socket.on('member_join', () => this.currentServer && this.loadSection('members'));
        this.socket.on('member_leave', () => this.currentServer && this.loadSection('members'));
        this.socket.on('member_update', () => this.currentServer && this.loadSection('members'));
        this.socket.on('channel_create', () => this.currentServer && this.loadSection('channels'));
        this.socket.on('channel_delete', () => this.currentServer && this.loadSection('channels'));
        this.socket.on('role_create', () => this.currentServer && this.loadSection('roles'));
        this.socket.on('role_delete', () => this.currentServer && this.loadSection('roles'));

        // Fallback polling every 15s for bot status
        setInterval(() => {
            if (this.currentServer) {
                this.loadBotStatus();
            }
        }, 15000);
    }
}

// Initialize dashboard
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new Dashboard();
});
