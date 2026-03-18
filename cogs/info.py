"""
Info commands — rich server/user/role/channel info (Statbot/Carl-bot style)
"""
import discord
from discord import app_commands
from discord.ext import commands
from datetime import timezone
import logging

logger = logging.getLogger('discord_bot.info')

BADGES = {
    'staff': '<:staff:🛡>',
    'partner': '🤝',
    'hypesquad': '🏠',
    'bug_hunter': '🐛',
    'nitro': '💎',
    'early_supporter': '⭐',
    'verified_bot_developer': '🔧',
}


def _badge_str(user: discord.User) -> str:
    flags = user.public_flags
    out = []
    if flags.staff:            out.append('Discord Staff')
    if flags.partner:          out.append('Partner')
    if flags.hypesquad:        out.append('HypeSquad')
    if flags.bug_hunter:       out.append('Bug Hunter')
    if flags.early_supporter:  out.append('Early Supporter')
    if flags.verified_bot_developer: out.append('Bot Developer')
    return ', '.join(out) if out else 'None'


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="serverinfo", description="Detailed server information")
    async def serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        embed = discord.Embed(title=g.name, color=0x5865f2)
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        if g.banner:
            embed.set_image(url=g.banner.url)

        embed.add_field(name="Owner", value=f"<@{g.owner_id}>", inline=True)
        embed.add_field(name="Created", value=f"<t:{int(g.created_at.timestamp())}:D>", inline=True)
        embed.add_field(name="Region", value=str(g.preferred_locale), inline=True)

        total = g.member_count
        bots = sum(1 for m in g.members if m.bot)
        humans = total - bots
        embed.add_field(name="Members", value=f"👥 {humans} humans | 🤖 {bots} bots", inline=True)
        embed.add_field(name="Channels", value=(
            f"💬 {len(g.text_channels)} text | "
            f"🔊 {len(g.voice_channels)} voice | "
            f"📁 {len(g.categories)} categories"
        ), inline=True)
        embed.add_field(name="Roles", value=str(len(g.roles)), inline=True)
        embed.add_field(name="Boost Level", value=f"Level {g.premium_tier} ({g.premium_subscription_count} boosts)", inline=True)
        embed.add_field(name="Emojis", value=f"{len(g.emojis)}/{g.emoji_limit}", inline=True)
        embed.add_field(name="Verification", value=str(g.verification_level).title(), inline=True)

        features = [f.replace('_', ' ').title() for f in g.features[:6]]
        if features:
            embed.add_field(name="Features", value=', '.join(features), inline=False)

        embed.set_footer(text=f"ID: {g.id}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="Detailed user information")
    @app_commands.describe(member="The member to look up (defaults to you)")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        m = member or interaction.user
        embed = discord.Embed(title=str(m), color=m.color if m.color.value else 0x5865f2)
        embed.set_thumbnail(url=m.display_avatar.url)

        embed.add_field(name="Display Name", value=m.display_name, inline=True)
        embed.add_field(name="Account Created", value=f"<t:{int(m.created_at.timestamp())}:D>", inline=True)
        embed.add_field(name="Joined Server", value=f"<t:{int(m.joined_at.timestamp())}:D>" if m.joined_at else "Unknown", inline=True)

        roles = [r.mention for r in reversed(m.roles) if r.name != '@everyone']
        embed.add_field(name=f"Roles ({len(roles)})", value=' '.join(roles[:10]) or 'None', inline=False)
        embed.add_field(name="Badges", value=_badge_str(m), inline=True)
        embed.add_field(name="Bot", value="Yes" if m.bot else "No", inline=True)

        status_map = {
            discord.Status.online: '🟢 Online',
            discord.Status.idle: '🟡 Idle',
            discord.Status.dnd: '🔴 Do Not Disturb',
            discord.Status.offline: '⚫ Offline',
        }
        embed.add_field(name="Status", value=status_map.get(m.status, 'Unknown'), inline=True)

        if m.activity:
            embed.add_field(name="Activity", value=str(m.activity.name)[:50], inline=True)

        embed.set_footer(text=f"ID: {m.id}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roleinfo", description="Information about a role")
    @app_commands.describe(role="The role to look up")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        embed = discord.Embed(title=f"Role: {role.name}", color=role.color)
        embed.add_field(name="ID", value=str(role.id), inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Position", value=str(role.position), inline=True)
        embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
        embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
        embed.add_field(name="Managed", value="Yes" if role.managed else "No", inline=True)
        embed.add_field(name="Members", value=str(len(role.members)), inline=True)
        embed.add_field(name="Created", value=f"<t:{int(role.created_at.timestamp())}:D>", inline=True)

        key_perms = []
        p = role.permissions
        if p.administrator:     key_perms.append('Administrator')
        if p.manage_guild:      key_perms.append('Manage Server')
        if p.manage_channels:   key_perms.append('Manage Channels')
        if p.manage_roles:      key_perms.append('Manage Roles')
        if p.manage_messages:   key_perms.append('Manage Messages')
        if p.kick_members:      key_perms.append('Kick Members')
        if p.ban_members:       key_perms.append('Ban Members')
        if p.mention_everyone:  key_perms.append('Mention Everyone')
        embed.add_field(name="Key Permissions", value=', '.join(key_perms) or 'None', inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Get a user's avatar")
    @app_commands.describe(member="The member (defaults to you)")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        m = member or interaction.user
        embed = discord.Embed(title=f"{m.display_name}'s Avatar", color=0x5865f2)
        embed.set_image(url=m.display_avatar.url)
        embed.add_field(name="PNG", value=f"[Link]({m.display_avatar.replace(format='png').url})", inline=True)
        embed.add_field(name="JPG", value=f"[Link]({m.display_avatar.replace(format='jpg').url})", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="banner", description="Get a user's banner")
    @app_commands.describe(member="The member (defaults to you)")
    async def banner(self, interaction: discord.Interaction, member: discord.Member = None):
        m = member or interaction.user
        user = await self.bot.fetch_user(m.id)
        if not user.banner:
            return await interaction.response.send_message("This user has no banner.", ephemeral=True)
        embed = discord.Embed(title=f"{m.display_name}'s Banner", color=0x5865f2)
        embed.set_image(url=user.banner.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        color = 0x2ecc71 if latency < 100 else (0xf39c12 if latency < 200 else 0xe74c3c)
        embed = discord.Embed(title="Pong!", color=color)
        embed.add_field(name="WebSocket", value=f"{latency}ms", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="botinfo", description="Information about this bot")
    async def botinfo(self, interaction: discord.Interaction):
        from datetime import datetime
        bot = self.bot
        uptime = datetime.now(timezone.utc) - bot.start_time
        hours, rem = divmod(int(uptime.total_seconds()), 3600)
        mins, secs = divmod(rem, 60)

        embed = discord.Embed(title=f"{bot.user.name}", color=0x7c3aed)
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
        embed.add_field(name="Users", value=str(sum(g.member_count for g in bot.guilds)), inline=True)
        embed.add_field(name="Uptime", value=f"{hours}h {mins}m {secs}s", inline=True)
        embed.add_field(name="Latency", value=f"{round(bot.latency*1000)}ms", inline=True)
        embed.add_field(name="Commands", value=str(len(bot.tree.get_commands())), inline=True)
        embed.add_field(name="Cogs", value=str(len(bot.cogs)), inline=True)
        embed.set_footer(text=f"ID: {bot.user.id}")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Info(bot))
