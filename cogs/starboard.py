"""
Starboard — messages that get enough ⭐ reactions get posted to a starboard channel (Carl-bot USP)
"""
import discord
from discord.ext import commands
import json, os, logging
from datetime import datetime, timezone

logger = logging.getLogger('discord_bot.starboard')
SB_FILE = 'starboard.json'


def _load():
    if os.path.exists(SB_FILE):
        try:
            with open(SB_FILE) as f: return json.load(f)
        except Exception as e:
            logger.debug(f"Starboard error: {e}")
    return {}

def _save(d):
    with open(SB_FILE, 'w') as f: json.dump(d, f, indent=2)

def _cfg(guild_id):
    data = _load()
    return data.get(str(guild_id), {})

def _save_cfg(guild_id, cfg):
    data = _load()
    data[str(guild_id)] = cfg
    _save(data)


class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) not in ('⭐', '🌟'):
            return
        cfg = _cfg(payload.guild_id)
        if not cfg.get('channel_id'):
            return
        if not cfg.get('enabled', True):
            return

        threshold = cfg.get('threshold', 3)
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        channel = guild.get_channel(payload.channel_id)
        if not channel:
            return

        if str(payload.channel_id) == str(cfg['channel_id']):
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

        star_count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) in ('⭐', '🌟'):
                star_count += reaction.count

        if star_count < threshold:
            return

        sb_channel = guild.get_channel(int(cfg['channel_id']))
        if not sb_channel:
            return

        posted = cfg.get('posted', {})
        msg_id = str(payload.message_id)

        if msg_id in posted:
            try:
                sb_msg = await sb_channel.fetch_message(int(posted[msg_id]))
                await sb_msg.edit(content=f'⭐ **{star_count}** | {channel.mention}')
            except Exception as e:
                logger.debug(f"Starboard update error: {e}")
            return

        embed = discord.Embed(color=0xf59e0b, timestamp=message.created_at)
        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        if message.content:
            embed.description = message.content[:2000]
        if message.attachments:
            embed.set_image(url=message.attachments[0].url)
        embed.add_field(name='Original', value=f'[Jump to message]({message.jump_url})', inline=True)
        embed.set_footer(text=f'ID: {message.id}')

        try:
            sb_msg = await sb_channel.send(
                content=f'⭐ **{star_count}** | {channel.mention}',
                embed=embed
            )
            posted[msg_id] = str(sb_msg.id)
            cfg['posted'] = posted
            _save_cfg(payload.guild_id, cfg)
        except Exception as e:
            logger.warning(f'Starboard post failed: {e}')

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) not in ('⭐', '🌟'):
            return
        cfg = _cfg(payload.guild_id)
        if not cfg.get('channel_id') or not cfg.get('enabled', True):
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        channel = guild.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

        star_count = sum(r.count for r in message.reactions if str(r.emoji) in ('⭐', '🌟'))
        posted = cfg.get('posted', {})
        msg_id = str(payload.message_id)

        if msg_id not in posted:
            return

        sb_channel = guild.get_channel(int(cfg['channel_id']))
        if not sb_channel:
            return

        try:
            sb_msg = await sb_channel.fetch_message(int(posted[msg_id]))
            if star_count < 1:
                await sb_msg.delete()
                del posted[msg_id]
                cfg['posted'] = posted
                _save_cfg(payload.guild_id, cfg)
            else:
                await sb_msg.edit(content=f'⭐ **{star_count}** | {channel.mention}')
        except:
            pass

    @commands.command(name='starboard-setup')
    @commands.has_permissions(manage_guild=True)
    async def setup(self, ctx: commands.Context, channel: discord.TextChannel, threshold: int = 3):
        """Set up the starboard: !starboard-setup #channel [threshold]"""
        cfg = _cfg(ctx.guild.id)
        cfg['channel_id'] = str(channel.id)
        cfg['threshold'] = threshold
        cfg['enabled'] = True
        cfg.setdefault('posted', {})
        _save_cfg(ctx.guild.id, cfg)
        await ctx.send(f'Starboard set to {channel.mention} with **{threshold}** ⭐ threshold.')

    @commands.command(name='starboard-toggle')
    @commands.has_permissions(manage_guild=True)
    async def toggle(self, ctx: commands.Context):
        """Enable or disable the starboard"""
        cfg = _cfg(ctx.guild.id)
        if not cfg.get('channel_id'):
            return await ctx.send('Set up starboard first with `!starboard-setup`.')
        cfg['enabled'] = not cfg.get('enabled', True)
        _save_cfg(ctx.guild.id, cfg)
        state = 'enabled' if cfg['enabled'] else 'disabled'
        await ctx.send(f'Starboard {state}.')

    @commands.command(name='starboard-threshold')
    @commands.has_permissions(manage_guild=True)
    async def threshold(self, ctx: commands.Context, stars: int):
        """Change the star threshold: !starboard-threshold <number>"""
        cfg = _cfg(ctx.guild.id)
        cfg['threshold'] = max(1, stars)
        _save_cfg(ctx.guild.id, cfg)
        await ctx.send(f'Starboard threshold set to **{stars}** ⭐.')

    @commands.command(name='starboard-status')
    @commands.has_permissions(manage_guild=True)
    async def status(self, ctx: commands.Context):
        """View starboard configuration"""
        cfg = _cfg(ctx.guild.id)
        embed = discord.Embed(title='Starboard', color=0xf59e0b)
        embed.add_field(name='Status', value='✅ Enabled' if cfg.get('enabled') else '❌ Disabled', inline=True)
        ch = ctx.guild.get_channel(int(cfg['channel_id'])) if cfg.get('channel_id') else None
        embed.add_field(name='Channel', value=ch.mention if ch else 'Not set', inline=True)
        embed.add_field(name='Threshold', value=f'{cfg.get("threshold", 3)} ⭐', inline=True)
        embed.add_field(name='Total Starred', value=str(len(cfg.get('posted', {}))), inline=True)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Starboard(bot))
