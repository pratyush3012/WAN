# 🏅 Badge System Guide

## Quick Setup

### 1. Create Badge Roles
```
/assign-badge-role
```

### 2. Auto-Assign to Members
```
/auto-assign-badges
```

### 3. Done!
Members now have visual badges in the member list.

## Available Badges

- 👑 **Owner** - Server owner
- ⚡ **Administrator** - Admin permissions
- 🛡️ **Manager** - Management permissions
- 🔨 **Moderator** - Moderation permissions
- 💚 **Helper** - Message management
- ✅ **Member** - Verified members
- ⭐ **VIP** - VIP/Premium members
- 💎 **Booster** - Server boosters
- 👤 **Guest** - No badge (no roles)

## Commands

**Everyone:**
- `/badge` - View your badge
- `/badge @user` - View someone's badge
- `/badges` - View all badges

**Admins:**
- `/assign-badge-role` - Create badge roles
- `/auto-assign-badges` - Auto-assign to all
- `/badge-stats` - View distribution

## How It Works

Badges are automatically assigned based on:
1. Permissions (admin, moderator, etc.)
2. Role names (contains "mod", "admin", etc.)
3. Special status (owner, booster)

Priority: Owner > Admin > Manager > Moderator > Helper > VIP > Booster > Member > Guest
