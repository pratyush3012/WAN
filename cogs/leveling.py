"""
WAN Bot - Leveling/XP System (replaces MEE6)
- XP for every message (with cooldown)
- Level-up announcements
- Level roles (auto-assign on level up)
- /rank, /levels, /xp-config
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, random, asyncio, logging, time

logger = logging.getLogger('discord_bot.leveling')
DATA_FILE = 'leveling_data.json'

def _xp_for_level(lvl: int) -> int:
    """XP needed to reach this level."""
    return 5 * (lvl ** 2) + 50 * lvl + 100

def _level_from_xp(xp: int) -> int:
    lvl = 0
    while xp >= _xp_for_level(lvl):
        xp -= _xp_for_level(lvl)
        lvl += 1
    return lvl

def _xp_progress(xp: int):
    """Returns (level, current_xp, needed_xp)."""
    lvl = 0
    while xp >= _xp_for_level(lvl):
        xp -= _xp_for_level(lvl)
        lvl += 1
    return lvl, xp, _xp_for_level(lvl)


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data: dict = self._load()
        self._cd: dict[str, float] = {}   # "guild_user" -> last_xp_time

    def _load(self) -> dict:
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save(self):
        try:
            with open(DATA_FILE, 'w') as f:
                json.dump(self.data, f)
        except Exception as e:
            logger.error(f"Leveling save error: {e}")

    def _guild(self, gid: int) -> dict:
        key = str(gid)
        if key not in self.data:
            self.data[key] = {'users': {}, 'config': {'level_roles': {}, 'announce_channel': None, 'announce': True}}
        return self.data[key]

    def _user(self, gid: int, uid: int) -> dict:
        g = self._guild(gid)
        key = str(uid)
        if key not in g['users']:
            g['users'][key] = {'xp': 0, 'messages': 0, 'level': 0}
        # Backfill level field for existing users
        u = g['users'][key]
        if 'level' not in u:
            u['level'] = _level_from_xp(u.get('xp', 0))
        return u

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        key = f"{message.guild.id}_{message.author.id}"
        now = time.time()
        if now - self._cd.get(key, 0) < 60:   # 60s cooldown between XP gains
            return
        self._cd[key] = now

        u = self._user(message.guild.id, message.author.id)
        old_level = u.get('level', _level_from_xp(u['xp']))  # use stored level to avoid re-announce on restart
        gain = random.randint(15, 25)
        u['xp'] += gain
        u['messages'] = u.get('messages', 0) + 1
        new_level, cur_xp, needed = _xp_progress(u['xp'])
        # Always keep stored level in sync
        u['level'] = new_level
        self._save()

        if new_level > old_level:
            await self._on_level_up(message, new_level)

    async def _on_level_up(self, message: discord.Message, level: int):
        g = self._guild(message.guild.id)
        cfg = g['config']

        # Assign level role if configured
        role_id = cfg['level_roles'].get(str(level))
        if role_id:
            role = message.guild.get_role(int(role_id))
            if role:
                try:
                    await message.author.add_roles(role, reason=f"Reached level {level}")
                except Exception:
                    pass

        if not cfg.get('announce', True):
            return

        # Try AI Coder generated level-up messages first
        desc = None
        try:
            ai_coder = message.guild._state._get_client().cogs.get("AICoder")
            if ai_coder:
                msgs = ai_coder.get_generated("levelup_messages")
                if msgs:
                    import random as _r
                    template = _r.choice(msgs)
                    desc = template.replace("{user}", message.author.mention).replace("{level}", str(level))
        except Exception:
            pass

        if not desc:
            desc = f"**{message.author.mention}** reached **Level {level}**! 🎉"

        embed = discord.Embed(title="⬆️ Level Up!", description=desc, color=0xf59e0b)
        embed.set_thumbnail(url=message.author.display_avatar.url)

        ch_id = cfg.get('announce_channel')
        ch = message.guild.get_channel(int(ch_id)) if ch_id else message.channel
        try:
            await ch.send(embed=embed)
        except Exception:
            pass

    @app_commands.command(name="rank", description="⭐ Show your XP rank")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        u = self._user(interaction.guild.id, member.id)
        level, cur_xp, needed = _xp_progress(u['xp'])
        g = self._guild(interaction.guild.id)
        sorted_users = sorted(g['users'].items(), key=lambda x: x[1].get('xp', 0), reverse=True)
        rank_pos = next((i+1 for i, (uid, _) in enumerate(sorted_users) if uid == str(member.id)), '?')
        bar_filled = int((cur_xp / needed) * 20)
        bar = '█' * bar_filled + '░' * (20 - bar_filled)
        embed = discord.Embed(title=f"⭐ {member.display_name}'s Rank", color=0xf59e0b)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="Rank", value=f"#{rank_pos}", inline=True)
        embed.add_field(name="Total XP", value=str(u['xp']), inline=True)
        embed.add_field(name=f"Progress ({cur_xp}/{needed} XP)", value=f"`{bar}`", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="levels", description="⭐ Show the XP leaderboard")
    async def levels(self, interaction: discord.Interaction):
        g = self._guild(interaction.guild.id)
        sorted_users = sorted(g['users'].items(), key=lambda x: x[1].get('xp', 0), reverse=True)[:10]
        embed = discord.Embed(title="⭐ XP Leaderboard", color=0xf59e0b)
        lines = []
        medals = ['🥇','🥈','🥉']
        for i, (uid, data) in enumerate(sorted_users):
            member = interaction.guild.get_member(int(uid))
            name = member.display_name if member else f"User {uid}"
            lvl, _, _ = _xp_progress(data.get('xp', 0))
            prefix = medals[i] if i < 3 else f"`{i+1}.`"
            lines.append(f"{prefix} **{name}** — Level {lvl} ({data.get('xp',0)} XP)")
        embed.description = "\n".join(lines) if lines else "No data yet."
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="set-level-role", description="⭐ Assign a role when members reach a level")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def set_level_role(self, interaction: discord.Interaction, level: int, role: discord.Role):
        g = self._guild(interaction.guild.id)
        g['config']['level_roles'][str(level)] = role.id
        self._save()
        await interaction.response.send_message(f"✅ Members will get **{role.name}** at level **{level}**.", ephemeral=True)

    @app_commands.command(name="xp-channel", description="⭐ Set channel for level-up announcements")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def xp_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        g = self._guild(interaction.guild.id)
        g['config']['announce_channel'] = channel.id
        self._save()
        await interaction.response.send_message(f"✅ Level-up announcements → {channel.mention}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Leveling(bot))
