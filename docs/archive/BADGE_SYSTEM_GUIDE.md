# 🏅 Badge System Guide

## ✅ What's Been Added

A complete badge/role identification system that makes it easy to see who's a member, moderator, admin, etc.

## 🎯 Features

### Available Badges:
- 👑 **Owner** - Server owner
- ⚡ **Administrator** - Full admin permissions
- 🛡️ **Manager** - Server management permissions
- 🔨 **Moderator** - Moderation permissions
- 💚 **Helper** - Message management permissions
- ✅ **Member** - Verified server member
- ⭐ **VIP** - VIP/Premium members
- 💎 **Booster** - Server boosters
- ✓ **Verified** - Verified members
- 👤 **Guest** - No badge (no roles)

## 🚀 Quick Setup (2 Options)

### Option 1: Visual Badge Roles (Recommended)

Creates actual Discord roles that appear in the member list:

```
/assign-badge-role
```

This creates roles like:
- 👑 Owner (Red)
- ⚡ Administrator (Red)
- 🛡️ Manager (Orange)
- 🔨 Moderator (Green)
- 💚 Helper (Cyan)
- ✅ Member (Blue)
- ⭐ VIP (Gold)
- 💎 Booster (Pink)

Then auto-assign them:
```
/auto-assign-badges
```

**Result:** Members now have visual badges in the member list!

### Option 2: Command-Based Badges

Just use the commands - no role creation needed:

```
/badge              - View your badge
/badge @user        - View someone's badge
/badges             - View all available badges
/badge-stats        - View badge distribution (Admin)
```

## 📋 Commands

### For Everyone:

**View Your Badge:**
```
/badge
```
Shows your current badge based on roles and permissions.

**View Someone's Badge:**
```
/badge @username
```
Check what badge another member has.

**View All Badges:**
```
/badges
```
See all available badges and how to get them.

### For Admins:

**Create Badge Roles:**
```
/assign-badge-role
```
Creates visual badge roles in your server.

**Auto-Assign Badges:**
```
/auto-assign-badges
```
Automatically assigns badge roles to all members based on their permissions.

**View Badge Statistics:**
```
/badge-stats
```
See how many members have each badge.

## 🎨 How Badges Are Assigned

### Automatic Detection:

1. **By Permission:**
   - Administrator permission → ⚡ Administrator
   - Manage Server → 🛡️ Manager
   - Moderate Members/Kick → 🔨 Moderator
   - Manage Messages → 💚 Helper

2. **By Role Name:**
   - Role contains "admin" → ⚡ Administrator
   - Role contains "mod" → 🔨 Moderator
   - Role contains "member" → ✅ Member
   - Role contains "vip" → ⭐ VIP
   - etc.

3. **By Status:**
   - Server Owner → 👑 Owner
   - Server Booster → 💎 Booster
   - Has any role → ✅ Member
   - No roles → 👤 Guest

### Priority Order:
```
Owner > Admin > Manager > Moderator > Helper > VIP > Booster > Verified > Member > Guest
```

The highest badge is displayed.

## 💡 Use Cases

### 1. Easy Member Identification

**Before:**
"Is @John a moderator or just a member?"

**After:**
See 🔨 Moderator badge instantly!

### 2. Visual Member List

With badge roles enabled:
```
👑 Owner
  └─ ServerOwner

⚡ Administrator
  └─ Admin1
  └─ Admin2

🔨 Moderator
  └─ Mod1
  └─ Mod2
  └─ Mod3

✅ Member
  └─ Member1
  └─ Member2
  └─ (100+ members)
```

### 3. Quick Role Verification

```
/badge @suspicious_user
```
Instantly see if they're actually staff or just pretending!

### 4. Server Statistics

```
/badge-stats
```
See badge distribution:
- 1 Owner (0.1%)
- 3 Admins (0.3%)
- 10 Moderators (1.0%)
- 50 Members (5.0%)
- 936 Guests (93.6%)

## 🎯 Examples

### Example 1: Check Your Badge
```
User: /badge

Bot: 
👤 Role Badge - YourName
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Current Badge
# ✅ Member

Description
Verified server member

Roles (3)
@Member @Verified @Active
```

### Example 2: Check Moderator
```
User: /badge @ModeratorName

Bot:
👤 Role Badge - ModeratorName
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Current Badge
# 🔨 Moderator

Description
Moderator with moderation permissions

Roles (5)
@Moderator @Staff @Member @Verified @Active
```

### Example 3: View All Badges
```
User: /badges

Bot:
🏅 Server Badge System
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Available Badges
👑 Owner
⚡ Administrator
🛡️ Manager
🔨 Moderator
💚 Helper
✅ Member
⭐ VIP
💎 Server Booster
✓ Verified

How to Get Badges
👑 Owner - Be the server owner
⚡ Administrator - Have administrator permission
🛡️ Manager - Have manage server permission
...
```

### Example 4: Badge Statistics
```
Admin: /badge-stats

Bot:
📊 Server Badge Statistics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Badge Distribution

⚡ Administrator
████░░░░░░░░░░░░░░░░ 3 (0.3%)

🔨 Moderator
████████░░░░░░░░░░░░ 10 (1.0%)

✅ Member
████████████░░░░░░░░ 50 (5.0%)

👤 Guests
████████████████████ 937 (93.7%)
```

## 🔧 Advanced Setup

### Custom Badge Roles

You can create your own badge roles:

1. **Create Role:**
   - Server Settings → Roles → Create Role
   - Name: "🎮 Gamer" (with emoji)
   - Color: Choose your color
   - Enable "Display role members separately"

2. **Assign to Members:**
   - Right-click member → Roles → Add role

3. **Badge System Will Detect:**
   - If role name contains keywords, badge auto-assigns
   - Or use `/auto-assign-badges` to sync

### Integration with Other Systems

The badge system works with:
- ✅ Roblox integration (shows badges in stats)
- ✅ Economy system (badges in leaderboards)
- ✅ Leveling system (badges in rank cards)
- ✅ Web dashboard (badges displayed)

## 🎨 Customization

### Change Badge Emojis

Edit `cogs/badges.py`:

```python
self.badges = {
    'moderator': {'emoji': '🛡️', 'name': 'Moderator', 'color': 0x00FF00},
    # Change to:
    'moderator': {'emoji': '⚔️', 'name': 'Moderator', 'color': 0x00FF00},
}
```

### Add New Badge Types

```python
self.badges = {
    # ... existing badges ...
    'developer': {'emoji': '💻', 'name': 'Developer', 'color': 0x7289DA},
}

self.role_keywords = {
    # ... existing keywords ...
    'developer': ['dev', 'developer', 'programmer'],
}
```

### Change Badge Priority

Edit the `get_user_badge` method to change which badge shows first.

## 📊 Badge Statistics

Track badge distribution over time:

```
Week 1:
- 50 Members
- 5 Moderators
- 2 Admins

Week 2:
- 75 Members (+25)
- 8 Moderators (+3)
- 3 Admins (+1)
```

Use `/badge-stats` regularly to monitor growth!

## 🔒 Security Features

### Prevents Impersonation:
- Badges based on actual permissions
- Can't fake admin badge without permissions
- Visual verification in member list

### Easy Verification:
- `/badge @user` to verify staff
- Check before trusting commands
- Identify fake staff accounts

## 💡 Tips

1. **Use Visual Roles:**
   - Makes member list organized
   - Easy to see staff at a glance
   - Professional appearance

2. **Regular Updates:**
   - Run `/auto-assign-badges` weekly
   - Keeps badges synced with permissions
   - Removes badges from demoted members

3. **Combine with Permissions:**
   - Badge shows role
   - Permissions control what they can do
   - Both work together

4. **Member Onboarding:**
   - New members see badge system
   - Know who to ask for help
   - Understand server hierarchy

## 🐛 Troubleshooting

### Badge not showing?
- Check if member has any roles
- Verify permissions are correct
- Run `/auto-assign-badges` to sync

### Wrong badge assigned?
- Check role names for keywords
- Verify permission levels
- Manually adjust role if needed

### Badge roles not appearing?
- Check bot has "Manage Roles" permission
- Bot's role must be above badge roles
- Re-run `/assign-badge-role`

## 🎉 Benefits

✅ **Easy Identification** - See roles at a glance
✅ **Professional Look** - Organized member list
✅ **Security** - Verify staff quickly
✅ **Automatic** - Updates with permissions
✅ **Customizable** - Add your own badges
✅ **Integrated** - Works with all bot features

## 🚀 Quick Start

1. **Create badge roles:**
   ```
   /assign-badge-role
   ```

2. **Auto-assign to members:**
   ```
   /auto-assign-badges
   ```

3. **Check your badge:**
   ```
   /badge
   ```

4. **View statistics:**
   ```
   /badge-stats
   ```

Done! Your server now has a professional badge system! 🎉

---

**Questions?** Use `/badges` to see all available badges and how to get them!
