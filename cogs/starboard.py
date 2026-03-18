"""
Starboard — messages that get enough ⭐ reactions get posted to a starboard channel (Carl-bot USP)
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging
from datetime import datetime, timezone

logger = logging.getLogger('discord_bot.starboard')
SB_FILE = 'starboard.json'


def _load():
    if os.path.exists(SB_FILE):
        try:
            with open(SB_FILE) as f: return json.load(f)
        except: pass
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

        # Don't star messages in the starboard channel itself
        if str(payload.channel_id) == str(cfg['channel_id']):
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except:
            return

        # Count star reactions
        star_count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) in ('⭐', '🌟'):
                star_count += reaction.count

        if star_count < threshold:
            return

        sb_channel = guild.get_channel(int(cfg['channel_id']))
        if not sb_channel:
            return

        # Check if already posted
        posted = cfg.get('posted', {})
        msg_id = str(payload.message_id)

        if msg_id in posted:
            # Update star count on existing post
            try:
                sb_msg = await sb_channel.fetch_message(int(posted[msg_id]))
                await sb_msg.edit(content=f'⭐ **{star_count}** | {channel.mention}')
            except:
                pass
            return

        # Build starboard embed
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
        except:
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

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name='starboard-setup', description='Set up the starboard')
    @app_commands.describe(channel='Channel to post starred messages', threshold='Stars needed (default 3)')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup(self, interaction: discord.Interaction,
                    channel: discord.TextChannel, threshold: int = 3):
        cfg = _cfg(interaction.guild.id)
        cfg['channel_id'] = str(channel.id)
        cfg['threshold'] = threshold
        cfg['enabled'] = True
        cfg.setdefault('posted', {})
        _save_cfg(interaction.guild.id, cfg)
        await interaction.response.send_message(
            f'Starboard set to {channel.mention} with **{threshold}** ⭐ threshold.', ephemeral=True)

    @app_commands.command(name='starboard-toggle', description='Enable or disable the starboard')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def toggle(self, interaction: discord.Interaction):
        cfg = _cfg(interaction.guild.id)
        if not cfg.get('channel_id'):
            return await interaction.response.send_message('Set up starboard first with `/starboard-setup`.', ephemeral=True)
        cfg['enabled'] = not cfg.get('enabled', True)
        _save_cfg(interaction.guild.id, cfg)
        state = 'enabled' if cfg['enabled'] else 'disabled'
        await interaction.response.send_message(f'Starboard {state}.', ephemeral=True)

    @app_commands.command(name='starboard-threshold', description='Change the star threshold')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def threshold(self, interaction: discord.Interaction, stars: int):
        cfg = _cfg(interaction.guild.id)
        cfg['threshold'] = max(1, stars)
        _save_cfg(interaction.guild.id, cfg)
        await interaction.response.send_message(f'Starboard threshold set to **{stars}** ⭐.', ephemeral=True)

    @app_commands.command(name='starboard-status', description='View starboard configuration')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def status(self, interaction: discord.Interaction):
        cfg = _cfg(interaction.guild.id)
        embed = discord.Embed(title='Starboard', color=0xf59e0b)
        embed.add_field(name='Status', value='✅ Enabled' if cfg.get('enabled') else '❌ Disabled', inline=True)
        ch = interaction.guild.get_channel(int(cfg['channel_id'])) if cfg.get('channel_id') else None
        embed.add_field(name='Channel', value=ch.mention if ch else 'Not set', inline=True)
        embed.add_field(name='Threshold', value=f'{cfg.get("threshold", 3)} ⭐', inline=True)
        embed.add_field(name='Total Starred', value=str(len(cfg.get('posted', {}))), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Starboard(bot))
