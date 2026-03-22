"""
WAN Bot - Reaction Roles (replaces Carl-bot)
React to a message → get a role. Remove reaction → lose role.
/rr-add, /rr-remove, /rr-list, /rr-panel
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging

logger = logging.getLogger('discord_bot.reactionroles')
DATA_FILE = 'reactionroles_data.json'


class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data: dict = self._load()   # {guild_id: {message_id: {emoji: role_id}}}

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
            logger.error(f"RR save error: {e}")

    def _get(self, gid, mid, emoji) -> int | None:
        return self.data.get(str(gid), {}).get(str(mid), {}).get(str(emoji))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        role_id = self._get(payload.guild_id, payload.message_id, str(payload.emoji))
        if not role_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = guild.get_role(int(role_id))
        member = payload.member or guild.get_member(payload.user_id)
        if role and member:
            try:
                await member.add_roles(role, reason="Reaction role")
            except Exception as e:
                logger.warning(f"RR add role failed: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        role_id = self._get(payload.guild_id, payload.message_id, str(payload.emoji))
        if not role_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = guild.get_role(int(role_id))
        member = guild.get_member(payload.user_id)
        if role and member:
            try:
                await member.remove_roles(role, reason="Reaction role removed")
            except Exception as e:
                logger.warning(f"RR remove role failed: {e}")

    @commands.command(name="rr-add")
    async def rr_add(self, ctx,
                     message_id: str, emoji: str, role: discord.Role):
        gid = str(ctx.guild.id)
        if gid not in self.data:
            self.data[gid] = {}
        if message_id not in self.data[gid]:
            self.data[gid][message_id] = {}
        self.data[gid][message_id][emoji] = role.id
        self._save()
        # Add the reaction to the message
        try:
            ch = ctx.channel
            msg = await ch.fetch_message(int(message_id))
            await msg.add_reaction(emoji)
        except Exception as e:
            logger.warning(f"Could not add reaction: {e}")
        await ctx.send(
            f"✅ React {emoji} on message `{message_id}` → **{role.name}**")

    @commands.command(name="rr-remove")
    async def rr_remove(self, ctx, message_id: str, emoji: str):
        gid = str(ctx.guild.id)
        removed = self.data.get(gid, {}).get(message_id, {}).pop(emoji, None)
        self._save()
        if removed:
            await ctx.send(f"✅ Removed reaction role {emoji} from `{message_id}`")
        else:
            await ctx.send("❌ No reaction role found for that emoji/message.")

    @commands.command(name="rr-list")
    async def rr_list(self, ctx):
        gid = str(ctx.guild.id)
        entries = self.data.get(gid, {})
        if not entries:
            return await ctx.send("No reaction roles set up.")
        lines = []
        for mid, emojis in entries.items():
            for emoji, rid in emojis.items():
                role = ctx.guild.get_role(int(rid))
                lines.append(f"Message `{mid}` • {emoji} → **{role.name if role else rid}**")
        embed = discord.Embed(title="🎭 Reaction Roles", description="\n".join(lines), color=0x7c3aed)
        await ctx.send(embed=embed)

    @commands.command(name="rr-panel")
    async def rr_panel(self, ctx,
                       title: str, description: str, channel: discord.TextChannel = None):
        ch = channel or ctx.channel
        embed = discord.Embed(title=title, description=description, color=0x7c3aed)
        embed.set_footer(text="React below to get your roles!")
        msg = await ch.send(embed=embed)
        await ctx.send(
            f"✅ Panel created in {ch.mention}!\nUse `/rr-add {msg.id} <emoji> <role>` to add roles to it.")


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
