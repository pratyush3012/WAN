"""
Highlights — keyword DM alerts (Carl-bot USP)
Users get a DM when their tracked keyword is mentioned in any channel.
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger('discord_bot.highlights')
HL_FILE = 'highlights.json'
COOLDOWN_SECONDS = 60  # don't spam DMs — 1 per keyword per minute


def _load():
    if os.path.exists(HL_FILE):
        try:
            with open(HL_FILE) as f: return json.load(f)
        except: pass
    return {}


def _save(d):
    with open(HL_FILE, 'w') as f: json.dump(d, f, indent=2)


class Highlights(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cooldowns = {}  # (user_id, keyword) -> last_sent datetime

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        data = _load()
        gid = str(message.guild.id)
        guild_hl = data.get(gid, {})
        content_lower = message.content.lower()
        now = datetime.now(timezone.utc)

        for uid, keywords in guild_hl.items():
            if uid == str(message.author.id):
                continue  # don't alert the person who sent it
            member = message.guild.get_member(int(uid))
            if not member:
                continue
            # Don't alert if user is online and in the same channel recently
            for kw in keywords:
                if kw.lower() not in content_lower:
                    continue
                # Cooldown check
                key = (uid, kw.lower())
                last = self._cooldowns.get(key)
                if last and (now - last).total_seconds() < COOLDOWN_SECONDS:
                    continue
                self._cooldowns[key] = now
                try:
                    embed = discord.Embed(
                        title=f'🔔 Highlight: `{kw}`',
                        description=f'**{message.author.display_name}** mentioned your keyword in {message.channel.mention}',
                        color=0xf39c12,
                        timestamp=now
                    )
                    embed.add_field(name='Message', value=message.content[:500], inline=False)
                    embed.add_field(name='Jump', value=f'[Click here]({message.jump_url})', inline=True)
                    embed.set_footer(text=f'{message.guild.name}')
                    await member.send(embed=embed)
                except Exception as e:
                    logger.debug(f'Highlight DM failed for {uid}: {e}')

    @app_commands.command(name='highlight-add', description='Get DM when a keyword is mentioned')
    @app_commands.describe(keyword='Word or phrase to track')
    async def add(self, interaction: discord.Interaction, keyword: str):
        data = _load()
        gid = str(interaction.guild.id)
        uid = str(interaction.user.id)
        kws = data.setdefault(gid, {}).setdefault(uid, [])
        if len(kws) >= 20:
            return await interaction.response.send_message('Max 20 highlights per server.', ephemeral=True)
        if keyword.lower() in [k.lower() for k in kws]:
            return await interaction.response.send_message('Already tracking that keyword.', ephemeral=True)
        kws.append(keyword.lower())
        _save(data)
        await interaction.response.send_message(f'Now tracking `{keyword}` in this server.', ephemeral=True)

    @app_commands.command(name='highlight-remove', description='Stop tracking a keyword')
    @app_commands.describe(keyword='Keyword to remove')
    async def remove(self, interaction: discord.Interaction, keyword: str):
        data = _load()
        gid = str(interaction.guild.id)
        uid = str(interaction.user.id)
        kws = data.get(gid, {}).get(uid, [])
        new_kws = [k for k in kws if k.lower() != keyword.lower()]
        if len(new_kws) == len(kws):
            return await interaction.response.send_message('Keyword not found.', ephemeral=True)
        data[gid][uid] = new_kws
        _save(data)
        await interaction.response.send_message(f'Removed `{keyword}` from highlights.', ephemeral=True)

    @app_commands.command(name='highlight-list', description='List your tracked keywords')
    async def list_hl(self, interaction: discord.Interaction):
        data = _load()
        kws = data.get(str(interaction.guild.id), {}).get(str(interaction.user.id), [])
        if not kws:
            return await interaction.response.send_message('No highlights set.', ephemeral=True)
        embed = discord.Embed(title='Your Highlights', description='\n'.join(f'• `{k}`' for k in kws), color=0xf39c12)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='highlight-clear', description='Clear all your highlights in this server')
    async def clear(self, interaction: discord.Interaction):
        data = _load()
        gid = str(interaction.guild.id)
        uid = str(interaction.user.id)
        if gid in data and uid in data[gid]:
            del data[gid][uid]
            _save(data)
        await interaction.response.send_message('All highlights cleared.', ephemeral=True)


async def setup(bot):
    await bot.add_cog(Highlights(bot))
