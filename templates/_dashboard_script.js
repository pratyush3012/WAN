// STATE
let currentServer = null, allMembers = [], socket = null;

// API FETCH — always sends session cookie, redirects on 401
async function apiFetch(url, opts) {
    opts = opts || {};
    opts.credentials = 'include';
    const r = await fetch(url, opts);
    if (r.status === 401) { window.location.href = '/login'; throw new Error('Session expired'); }
    return r;
}

// SECTION NAVIGATION
function showSection(name, el) {
    document.querySelectorAll('.section').forEach(s => s.style.display = 'none');
    document.querySelectorAll('.menu-item').forEach(m => m.classList.remove('active'));
    const sec = document.getElementById('sec-' + name);
    if (sec) sec.style.display = 'block';
    if (el) { el.classList.add('active'); }
    else { document.querySelectorAll('.menu-item').forEach(m => { if (m.getAttribute('onclick') && m.getAttribute('onclick').includes("'" + name + "'")) m.classList.add('active'); }); }
    if (name === 'leaderboard' && currentServer) loadLeaderboard('score');
    if (name === 'audit'       && currentServer) loadAuditLog();
    if (name === 'music'       && currentServer) loadMusicStatus();
    if (name === 'announce'    && currentServer) loadTextChannels();
}

// SERVER SELECTION
async function selectServer(id) {
    currentServer = id || null;
    if (!id) return;
    notify('Loading server data...', 'info');
    await Promise.all([loadServerDetails(id), loadBotStatus()]);
    if (socket) socket.emit('subscribe_server', { server_id: id });
}

async function loadServerDetails(id) {
    try {
        const [r1, r2] = await Promise.all([apiFetch('/api/server/' + id), apiFetch('/api/server/' + id + '/members')]);
        if (!r1.ok) { const e = await r1.json().catch(() => ({})); notify('Failed to load server: ' + (e.error || r1.status), 'danger'); return; }
        const d = await r1.json(), md = await r2.json();
        allMembers = md.members || [];
        document.getElementById('statMembers').textContent  = d.members.total;
        document.getElementById('statChannels').textContent = d.channels.text.length + d.channels.voice.length;
        document.getElementById('statRoles').textContent    = d.roles.length;
        document.getElementById('serverSubtitle').textContent = d.name;
        document.getElementById('ovServerName').textContent   = d.name;
        document.getElementById('ovOwner').textContent        = d.owner.name;
        document.getElementById('ovBoost').textContent        = 'Level ' + d.boost_level + ' (' + d.boost_count + ' boosts)';
        document.getElementById('ovVerification').textContent = d.verification_level;
        document.getElementById('ovOnline').textContent       = d.members.online;
        document.getElementById('ovBots').textContent         = d.members.bots;
        renderRoles(d.roles); renderChannels(d.channels); renderMembers(allMembers);
        loadMusicVoiceChannels(d.channels.voice);
    } catch(e) { if (e.message !== 'Session expired') notify('Failed to load server: ' + e.message, 'danger'); }
}

async function loadBotStatus() {
    try {
        const d = await (await apiFetch('/api/bot/status')).json();
        if (d.status === 'online') {
            document.getElementById('statLatency').textContent = d.latency + 'ms';
            document.getElementById('botUptime').textContent   = 'Uptime: ' + d.uptime;
            document.getElementById('botStatusBadge').innerHTML = '<span class="pulse-dot"></span> Online';
            document.getElementById('botStatusBadge').className = 'badge badge-success';
        } else {
            document.getElementById('botStatusBadge').textContent = '● Offline';
            document.getElementById('botStatusBadge').className   = 'badge badge-danger';
        }
    } catch(e) {}
}

// ROLES — IDs as strings to preserve 64-bit snowflake precision
function renderRoles(roles) {
    const c = document.getElementById('rolesContainer');
    if (!roles.length) { c.innerHTML = '<p style="color:var(--text-muted);">No roles found.</p>'; return; }
    c.innerHTML = roles.filter(r => r.name !== '@everyone').map(r => `
        <div class="role-item">
            <div class="role-info">
                <div style="width:20px;height:20px;border-radius:5px;background:${r.color==='#000000'?'#99aab5':r.color};flex-shrink:0;"></div>
                <div><div class="role-name">${escHtml(r.name)}</div><div class="role-members">${r.members} members</div></div>
            </div>
            <div style="display:flex;gap:8px;">
                <button class="btn btn-sm btn-primary" onclick="openEditRole('${r.id}','${escHtml(r.name)}','${r.color}')"><i class="fas fa-edit"></i></button>
                <button class="btn btn-sm btn-danger"  onclick="deleteRole('${r.id}','${escHtml(r.name)}')"><i class="fas fa-trash"></i></button>
            </div>
        </div>`).join('');
}

function openCreateRole() {
    if (!currentServer) { notify('Select a server first', 'warning'); return; }
    showModal('Create Role', `
        <div class="form-group"><label class="form-label">Role Name</label><input id="mRoleName" class="form-control" placeholder="Role name"></div>
        <div class="form-group"><label class="form-label">Color</label><input type="color" id="mRoleColor" class="form-control" value="#99aab5" style="height:44px;"></div>
        <div class="form-group" style="display:flex;gap:20px;"><label><input type="checkbox" id="mRoleHoist"> Hoisted</label><label><input type="checkbox" id="mRoleMention"> Mentionable</label></div>`,
    async () => {
        const name = document.getElementById('mRoleName').value.trim();
        if (!name) { notify('Enter a role name', 'warning'); return; }
        const res = await apiFetch('/api/server/' + currentServer + '/roles', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ name, color: document.getElementById('mRoleColor').value, hoist: document.getElementById('mRoleHoist').checked, mentionable: document.getElementById('mRoleMention').checked }) });
        const d = await res.json();
        if (d.success) { notify('Role created!', 'success'); closeModal(); loadServerDetails(currentServer); }
        else notify(d.error || 'Failed', 'danger');
    });
}

function openEditRole(id, name, color) {
    showModal('Edit Role', `
        <div class="form-group"><label class="form-label">Role Name</label><input id="mRoleName" class="form-control" value="${escHtml(name)}"></div>
        <div class="form-group"><label class="form-label">Color</label><input type="color" id="mRoleColor" class="form-control" value="${color}" style="height:44px;"></div>`,
    async () => {
        const res = await apiFetch('/api/server/' + currentServer + '/roles/' + id, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ name: document.getElementById('mRoleName').value, color: document.getElementById('mRoleColor').value }) });
        const d = await res.json();
        if (d.success) { notify('Role updated!', 'success'); closeModal(); loadServerDetails(currentServer); }
        else notify(d.error || 'Failed', 'danger');
    });
}

async function deleteRole(id, name) {
    if (!confirm('Delete role "' + name + '"?')) return;
    const d = await (await apiFetch('/api/server/' + currentServer + '/roles/' + id, { method:'DELETE' })).json();
    if (d.success) { notify('Role deleted', 'success'); loadServerDetails(currentServer); }
    else notify(d.error || 'Failed', 'danger');
}

// CHANNELS — IDs as strings
function renderChannels(channels) {
    const c = document.getElementById('channelsContainer');
    let html = '';
    if (channels.text.length) {
        html += '<h4 style="margin:0 0 12px;color:var(--text);">📝 Text Channels</h4>';
        html += channels.text.map(ch => `<div class="channel-item"><span style="font-weight:500;"># ${escHtml(ch.name)}${ch.category?' <span style="color:var(--text-muted);font-size:12px;">— '+escHtml(ch.category)+'</span>':''}</span><div style="display:flex;gap:8px;"><button class="btn btn-sm btn-primary" onclick="openEditChannel('${ch.id}','${escHtml(ch.name)}')"><i class="fas fa-edit"></i></button><button class="btn btn-sm btn-danger" onclick="deleteChannel('${ch.id}','${escHtml(ch.name)}')"><i class="fas fa-trash"></i></button></div></div>`).join('');
    }
    if (channels.voice.length) {
        html += '<h4 style="margin:20px 0 12px;color:var(--text);">🔊 Voice Channels</h4>';
        html += channels.voice.map(ch => `<div class="channel-item"><span style="font-weight:500;">🔊 ${escHtml(ch.name)}</span><div style="display:flex;gap:8px;"><button class="btn btn-sm btn-primary" onclick="openEditChannel('${ch.id}','${escHtml(ch.name)}')"><i class="fas fa-edit"></i></button><button class="btn btn-sm btn-danger" onclick="deleteChannel('${ch.id}','${escHtml(ch.name)}')"><i class="fas fa-trash"></i></button></div></div>`).join('');
    }
    c.innerHTML = html || '<p style="color:var(--text-muted);">No channels found.</p>';
}

function openCreateChannel() {
    if (!currentServer) { notify('Select a server first', 'warning'); return; }
    showModal('Create Channel', `
        <div class="form-group"><label class="form-label">Channel Name</label><input id="mChName" class="form-control" placeholder="channel-name"></div>
        <div class="form-group"><label class="form-label">Type</label><select id="mChType" class="form-control"><option value="text">Text Channel</option><option value="voice">Voice Channel</option><option value="category">Category</option></select></div>`,
    async () => {
        const name = document.getElementById('mChName').value.trim();
        if (!name) { notify('Enter a channel name', 'warning'); return; }
        const res = await apiFetch('/api/server/' + currentServer + '/channels', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ name, type: document.getElementById('mChType').value }) });
        const d = await res.json();
        if (d.success) { notify('Channel created!', 'success'); closeModal(); loadServerDetails(currentServer); }
        else notify(d.error || 'Failed', 'danger');
    });
}

function openEditChannel(id, name) {
    showModal('Edit Channel', `<div class="form-group"><label class="form-label">Channel Name</label><input id="mChName" class="form-control" value="${escHtml(name)}"></div>`,
    async () => {
        const res = await apiFetch('/api/server/' + currentServer + '/channels/' + id, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ name: document.getElementById('mChName').value }) });
        const d = await res.json();
        if (d.success) { notify('Channel updated!', 'success'); closeModal(); loadServerDetails(currentServer); }
        else notify(d.error || 'Failed', 'danger');
    });
}

async function deleteChannel(id, name) {
    if (!confirm('Delete channel "' + name + '"?')) return;
    const d = await (await apiFetch('/api/server/' + currentServer + '/channels/' + id, { method:'DELETE' })).json();
    if (d.success) { notify('Channel deleted', 'success'); loadServerDetails(currentServer); }
    else notify(d.error || 'Failed', 'danger');
}

// MEMBERS — IDs as strings
function renderMembers(members) {
    const c = document.getElementById('membersContainer');
    const humans = members.filter(m => !m.bot);
    if (!humans.length) { c.innerHTML = '<p style="color:var(--text-muted);">No members found.</p>'; return; }
    c.innerHTML = `<table class="table"><thead><tr><th>Member</th><th>Status</th><th>Roles</th><th>Actions</th></tr></thead><tbody>${humans.map(m => `
        <tr>
            <td><div style="display:flex;align-items:center;gap:10px;">${m.avatar?`<img src="${m.avatar}" style="width:32px;height:32px;border-radius:50%;">`:'<div style="width:32px;height:32px;border-radius:50%;background:rgba(255,255,255,0.1);display:flex;align-items:center;justify-content:center;font-size:14px;">👤</div>'}<div><div style="font-weight:600;">${escHtml(m.display_name)}</div><div style="color:var(--text-muted);font-size:12px;">${escHtml(m.name)}</div></div></div></td>
            <td><span class="badge badge-${m.status==='online'?'success':m.status==='idle'?'warning':'secondary'}">${m.status}</span></td>
            <td style="max-width:200px;">${m.roles.slice(0,3).map(r=>`<span class="badge badge-primary" style="margin:2px;">${escHtml(r.name)}</span>`).join('')}${m.roles.length>3?`<span style="color:var(--text-muted);font-size:12px;"> +${m.roles.length-3}</span>`:''}</td>
            <td><div style="display:flex;gap:6px;flex-wrap:wrap;">
                <button class="btn btn-sm btn-primary" onclick="openManageRoles('${m.id}','${escHtml(m.display_name)}')">Roles</button>
                <button class="btn btn-sm btn-success" onclick="openAssignBadgeTo('${m.id}','${escHtml(m.display_name)}')">Badge</button>
                <button class="btn btn-sm btn-danger"  onclick="kickMember('${m.id}','${escHtml(m.display_name)}')">Kick</button>
                <button class="btn btn-sm" style="background:#7c3aed;color:white;" onclick="timeoutMember('${m.id}','${escHtml(m.display_name)}')">Timeout</button>
            </div></td>
        </tr>`).join('')}</tbody></table>`;
}

function filterMembers(q) {
    const filtered = q ? allMembers.filter(m => m.display_name.toLowerCase().includes(q.toLowerCase()) || m.name.toLowerCase().includes(q.toLowerCase())) : allMembers;
    renderMembers(filtered);
}

function openManageRoles(memberId, memberName) {
    if (!currentServer) return;
    apiFetch('/api/server/' + currentServer).then(r => r.json()).then(d => {
        const roles = d.roles.filter(r => r.name !== '@everyone');
        showModal('Manage Roles — ' + memberName, `
            <div class="form-group"><label class="form-label">Role</label><select id="mRoleId" class="form-control">${roles.map(r=>`<option value="${r.id}">${escHtml(r.name)}</option>`).join('')}</select></div>
            <div class="form-group"><label class="form-label">Action</label><select id="mRoleAction" class="form-control"><option value="add">Add Role</option><option value="remove">Remove Role</option></select></div>`,
        async () => {
            const res = await apiFetch('/api/server/' + currentServer + '/members/' + memberId + '/roles/' + document.getElementById('mRoleId').value, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ action: document.getElementById('mRoleAction').value }) });
            const d2 = await res.json();
            if (d2.success) { notify(d2.message, 'success'); closeModal(); loadServerDetails(currentServer); }
            else notify(d2.error || 'Failed', 'danger');
        });
    });
}

async function kickMember(id, name) {
    const reason = prompt('Reason for kicking ' + name + '? (optional)');
    if (reason === null) return;
    const d = await (await apiFetch('/api/server/' + currentServer + '/members/' + id + '/kick', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ reason }) })).json();
    if (d.success) { notify(d.message, 'success'); loadServerDetails(currentServer); }
    else notify(d.error || 'Failed', 'danger');
}

function timeoutMember(id, name) {
    showModal('Timeout ' + name, `
        <div class="form-group"><label class="form-label">Duration (minutes)</label><input id="mTimeout" type="number" class="form-control" value="10" min="1" max="40320"></div>
        <div class="form-group"><label class="form-label">Reason</label><input id="mTimeoutReason" class="form-control" placeholder="Optional reason"></div>`,
    async () => {
        const d = await (await apiFetch('/api/server/' + currentServer + '/members/' + id + '/timeout', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ duration: parseInt(document.getElementById('mTimeout').value), reason: document.getElementById('mTimeoutReason').value }) })).json();
        if (d.success) { notify(d.message, 'success'); closeModal(); }
        else notify(d.error || 'Failed', 'danger');
    });
}

// LEADERBOARD
let currentLbCategory = 'score';
async function loadLeaderboard(category) {
    currentLbCategory = category;
    ['score','messages','voice','reactions'].forEach(cat => {
        const btn = document.getElementById('lb-' + cat);
        if (btn) btn.className = cat === category ? 'btn btn-primary btn-sm' : 'btn btn-sm lb-inactive';
    });
    const c = document.getElementById('leaderboardContainer');
    c.innerHTML = '<p style="color:var(--text-muted);">Loading...</p>';
    try {
        const data = await (await apiFetch('/api/leaderboard/' + category)).json();
        if (data.error) { c.innerHTML = '<p style="color:#ef4444;">' + data.error + '</p>'; return; }
        if (!data.leaderboard.length) { c.innerHTML = '<p style="color:var(--text-muted);">No activity tracked yet.</p>'; return; }
        const fmt = e => {
            if (category==='score')    return e.score.toLocaleString() + ' pts';
            if (category==='messages') return e.messages.toLocaleString() + ' msgs';
            if (category==='voice')    { const h=Math.floor(e.voice_seconds/3600),m=Math.floor((e.voice_seconds%3600)/60); return h?h+'h '+m+'m':m+'m'; }
            return e.reactions.toLocaleString() + ' reactions';
        };
        const rankEmoji = ['🥇','🥈','🥉'];
        c.innerHTML = data.leaderboard.map((e,i) => `
            <div class="lb-entry ${i===0?'gold':i===1?'silver':i===2?'bronze':''}">
                <div style="font-size:22px;width:32px;text-align:center;">${i<3?rankEmoji[i]:'<span style="color:var(--text-muted);font-weight:700;">'+(i+1)+'</span>'}</div>
                ${e.avatar?`<img src="${e.avatar}" style="width:36px;height:36px;border-radius:50%;flex-shrink:0;">`:'<div style="width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,0.1);flex-shrink:0;"></div>'}
                <div style="flex:1;min-width:0;"><div style="font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escHtml(e.name)}</div><div style="color:var(--text-muted);font-size:12px;">${fmt(e)}</div></div>
            </div>`).join('');
    } catch(err) { c.innerHTML = '<p style="color:#ef4444;">Failed to load leaderboard</p>'; }
}

// MUSIC
function loadMusicVoiceChannels(voiceChannels) {
    const sel = document.getElementById('musicChannel');
    sel.innerHTML = '<option value="">Auto-select first channel</option>';
    (voiceChannels || []).forEach(ch => { const o = document.createElement('option'); o.value = ch.id; o.textContent = '🔊 ' + ch.name; sel.appendChild(o); });
}

async function loadMusicStatus() {
    if (!currentServer) return;
    try { updateMusicUI(await (await apiFetch('/api/server/' + currentServer + '/music/status')).json()); } catch(e) {}
}

function updateMusicUI(d) {
    const statusEl = document.getElementById('musicStatus'), titleEl = document.getElementById('musicTitle'), thumbEl = document.getElementById('musicThumb'), queueEl = document.getElementById('musicQueue');
    if (d.playing) { statusEl.textContent = '▶ Playing'; statusEl.className = 'badge badge-success'; }
    else if (d.paused) { statusEl.textContent = '⏸ Paused'; statusEl.className = 'badge badge-warning'; }
    else { statusEl.textContent = 'Idle'; statusEl.className = 'badge badge-secondary'; }
    if (d.current && d.current.title) { titleEl.textContent = d.current.title; if (d.current.thumbnail) { thumbEl.src = d.current.thumbnail; thumbEl.style.display = 'block'; } else thumbEl.style.display = 'none'; }
    else { titleEl.textContent = 'Nothing playing'; thumbEl.style.display = 'none'; }
    queueEl.textContent = d.queue && d.queue.length ? d.queue.length + ' song(s) in queue' : 'Queue empty';
}

async function playMusic() {
    if (!currentServer) { notify('Select a server first', 'warning'); return; }
    const query = document.getElementById('musicQuery').value.trim();
    if (!query) { notify('Enter a song name or URL', 'warning'); return; }
    notify('Loading...', 'info');
    try {
        const d = await (await apiFetch('/api/server/' + currentServer + '/music/play', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ query, channel_id: document.getElementById('musicChannel').value || null }) })).json();
        if (d.error) { notify(d.error, 'danger'); return; }
        notify(d.status === 'playing' ? '▶ Now playing: ' + d.title : '📋 Queued: ' + d.title, 'success');
        document.getElementById('musicQuery').value = '';
        setTimeout(() => loadMusicStatus(), 1000);
    } catch(e) { notify('Failed to play music', 'danger'); }
}

async function musicControl(action) {
    if (!currentServer) return;
    try {
        const d = await (await apiFetch('/api/server/' + currentServer + '/music/control', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ action }) })).json();
        if (d.error) { notify(d.error, 'danger'); return; }
        notify('Music: ' + action, 'success');
        setTimeout(() => loadMusicStatus(), 500);
    } catch(e) { notify('Failed', 'danger'); }
}

// ANNOUNCEMENTS
async function loadTextChannels() {
    if (!currentServer) return;
    try {
        const d = await (await apiFetch('/api/server/' + currentServer + '/channels/text')).json();
        const sel = document.getElementById('announceChannel');
        sel.innerHTML = '<option value="">Select channel...</option>';
        (d.channels || []).forEach(ch => { const o = document.createElement('option'); o.value = ch.id; o.textContent = '# ' + ch.name; sel.appendChild(o); });
    } catch(e) {}
}

async function sendAnnouncement() {
    if (!currentServer) { notify('Select a server first', 'warning'); return; }
    const message = document.getElementById('announceMessage').value.trim();
    if (!message) { notify('Enter a message', 'warning'); return; }
    try {
        const d = await (await apiFetch('/api/server/' + currentServer + '/announce', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ channel_id: document.getElementById('announceChannel').value || null, title: document.getElementById('announceTitle').value.trim(), message, color: document.getElementById('announceColor').value, ping_everyone: document.getElementById('announcePing').checked }) })).json();
        if (d.error) { notify(d.error, 'danger'); return; }
        notify('Announcement sent to #' + d.channel, 'success');
        document.getElementById('announceMessage').value = ''; document.getElementById('announceTitle').value = '';
    } catch(e) { notify('Failed to send announcement', 'danger'); }
}

// AUDIT LOG
async function loadAuditLog() {
    if (!currentServer) return;
    const feed = document.getElementById('auditFeed');
    feed.innerHTML = '<p style="color:var(--text-muted);">Loading...</p>';
    try { renderAuditEvents((await (await apiFetch('/api/server/' + currentServer + '/audit')).json()).events || []); }
    catch(e) { feed.innerHTML = '<p style="color:#ef4444;">Failed to load audit log</p>'; }
}

function renderAuditEvents(events) {
    const feed = document.getElementById('auditFeed');
    if (!events.length) { feed.innerHTML = '<p style="color:var(--text-muted);">No events yet. Activity will appear here in real-time.</p>'; return; }
    feed.innerHTML = events.map(ev => auditEntryHTML(ev)).join('');
}

function auditEntryHTML(ev) {
    const time = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : '';
    const bgMap = { join:'rgba(16,185,129,0.12)', leave:'rgba(239,68,68,0.12)', role:'rgba(167,139,250,0.12)', channel:'rgba(6,182,212,0.12)', mod:'rgba(245,158,11,0.12)', music:'rgba(236,72,153,0.12)' };
    const bg = bgMap[ev.type] || 'rgba(255,255,255,0.04)';
    return `<div class="audit-entry ${ev.type||''}" style="background:${bg};"><div class="audit-icon" style="background:${bg};">${ev.icon||'📋'}</div><div class="audit-body"><div class="audit-title">${escHtml(ev.title||'')}</div><div class="audit-desc">${escHtml(ev.desc||'')}</div></div><div class="audit-time">${time}</div></div>`;
}

function prependAuditEntry(ev) {
    const feed = document.getElementById('auditFeed');
    const p = feed.querySelector('p'); if (p) p.remove();
    feed.insertAdjacentHTML('afterbegin', auditEntryHTML(ev));
    const entries = feed.querySelectorAll('.audit-entry');
    if (entries.length > 50) entries[entries.length-1].remove();
}

// BADGES
function openAssignBadge() {
    if (!currentServer) { notify('Select a server first', 'warning'); return; }
    const humans = allMembers.filter(m => !m.bot);
    const badgeOpts = '<option value="Owner">👑 Owner</option><option value="Admin">⚡ Admin</option><option value="Manager">🛡️ Manager</option><option value="Moderator">🔨 Moderator</option><option value="Helper">💚 Helper</option><option value="VIP">⭐ VIP</option><option value="Booster">💎 Booster</option><option value="Member">✅ Member</option>';
    showModal('Assign Badge', `<div class="form-group"><label class="form-label">Member</label><select id="mBadgeMember" class="form-control">${humans.map(m=>`<option value="${m.id}">${escHtml(m.display_name)}</option>`).join('')}</select></div><div class="form-group"><label class="form-label">Badge</label><select id="mBadgeType" class="form-control">${badgeOpts}</select></div>`,
    async () => {
        const d = await (await apiFetch('/api/server/' + currentServer + '/members/' + document.getElementById('mBadgeMember').value + '/badge', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ badge_name: document.getElementById('mBadgeType').value }) })).json();
        if (d.success) { notify(d.message, 'success'); closeModal(); } else notify(d.error || 'Failed', 'danger');
    });
}

function openAssignBadgeTo(memberId, memberName) {
    const badgeOpts = '<option value="Owner">👑 Owner</option><option value="Admin">⚡ Admin</option><option value="Manager">🛡️ Manager</option><option value="Moderator">🔨 Moderator</option><option value="Helper">💚 Helper</option><option value="VIP">⭐ VIP</option><option value="Booster">💎 Booster</option><option value="Member">✅ Member</option>';
    showModal('Assign Badge to ' + memberName, `<div class="form-group"><label class="form-label">Badge</label><select id="mBadgeType" class="form-control">${badgeOpts}</select></div>`,
    async () => {
        const d = await (await apiFetch('/api/server/' + currentServer + '/members/' + memberId + '/badge', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ badge_name: document.getElementById('mBadgeType').value }) })).json();
        if (d.success) { notify(d.message, 'success'); closeModal(); } else notify(d.error || 'Failed', 'danger');
    });
}

// SETTINGS
async function saveSettings() {
    if (!currentServer) { notify('Select a server first', 'warning'); return; }
    const d = await (await apiFetch('/api/server/' + currentServer + '/settings', { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ name: document.getElementById('settingName').value.trim(), description: document.getElementById('settingDesc').value.trim(), icon_url: document.getElementById('settingIcon').value.trim() }) })).json();
    if (d.success) notify('Settings saved!', 'success'); else notify(d.error || 'Failed', 'danger');
}

// MODAL
function showModal(title, body, onConfirm) {
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalBody').innerHTML    = body;
    document.getElementById('modalConfirm').onclick   = onConfirm;
    document.getElementById('modal').classList.add('active');
}
function closeModal() { document.getElementById('modal').classList.remove('active'); }

// NOTIFICATIONS
const notifColors = { success:'linear-gradient(135deg,#059669,#10b981)', danger:'linear-gradient(135deg,#dc2626,#ef4444)', warning:'linear-gradient(135deg,#d97706,#f59e0b)', info:'linear-gradient(135deg,#2563eb,#3b82f6)' };
let notifOffset = 20;
function notify(msg, type) {
    type = type || 'info';
    const el = document.createElement('div'); el.className = 'notification';
    el.style.background = notifColors[type] || notifColors.info; el.style.top = notifOffset + 'px'; el.textContent = msg;
    document.body.appendChild(el); notifOffset += 60;
    setTimeout(() => { el.style.opacity='0'; el.style.transform='translateX(120%)'; setTimeout(()=>{ el.remove(); notifOffset = Math.max(20, notifOffset-60); }, 300); }, 3000);
}

// HELPERS
function escHtml(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }

// SOCKET.IO
socket = io({ withCredentials: true });
socket.on('connect', () => { if (currentServer) socket.emit('subscribe_server', { server_id: currentServer }); });
socket.on('member_join',    () => { if (currentServer) loadServerDetails(currentServer); });
socket.on('member_leave',   () => { if (currentServer) loadServerDetails(currentServer); });
socket.on('member_update',  () => { if (currentServer) loadServerDetails(currentServer); });
socket.on('channel_create', () => { if (currentServer) loadServerDetails(currentServer); });
socket.on('channel_delete', () => { if (currentServer) loadServerDetails(currentServer); });
socket.on('role_create',    () => { if (currentServer) loadServerDetails(currentServer); });
socket.on('role_delete',    () => { if (currentServer) loadServerDetails(currentServer); });
socket.on('music_update',   d  => { if (currentServer && String(d.guild_id) === String(currentServer)) updateMusicUI(d); });
socket.on('audit', ev => { if (!currentServer || String(ev.guild_id) !== String(currentServer)) return; prependAuditEntry(ev); if (['mod','leave'].includes(ev.type)) notify(ev.title, ev.type==='mod'?'warning':'info'); });

// INIT
(async function init() {
    const userRole = '{{ session.get("role", "admin") }}';
    const isAdmin  = ['admin','manager','owner'].includes(userRole) || userRole === 'admin';
    if (!isAdmin) document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'none');
    loadBotStatus();
    setInterval(loadBotStatus, 15000);
    setInterval(() => { if (currentServer) loadMusicStatus(); }, 10000);
    try {
        const data = await (await apiFetch('/api/servers')).json();
        const sel  = document.getElementById('serverSelector');
        (data.servers || []).forEach(s => { const o = document.createElement('option'); o.value = s.id; o.textContent = s.name + ' (' + s.member_count + ' members)'; sel.appendChild(o); });
        if (data.servers && data.servers.length > 0) { sel.value = data.servers[0].id; await selectServer(data.servers[0].id); }
        else notify('No servers found — make sure the bot is in at least one server.', 'warning');
    } catch(e) { if (e.message !== 'Session expired') notify('Failed to load servers: ' + e.message, 'danger'); }
})();
