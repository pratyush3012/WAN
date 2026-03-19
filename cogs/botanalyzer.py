"""
Bot Analyzer Cog — Watches other bots in the server, learns their commands/patterns,
and lets WAN Bot mirror or respond to those patterns.
"""
import discord
from discord.ext import commands, tasks
import json
import os
import re
from datetime import datetime, timezone
from collections import defaultdict

DATA_FILE = 'bot_analyzer.json'

def _load():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

class BotAnalyzer(commands.Cog):
    """Analyzes other bots' behavior and learns their command patterns."""

    def __init__(self, bot):
        self.bot = bot
        self.data = _load()
        self._pending_save = False

    def _guild(self, guild_id: int) -> dict:
        gid = str(guild_id)
        if gid not in self.data:
            self.data[gid] = {}
        return self.data[gid]

    def _bot_entry(self, guild_id: int, bot_member: discord.Member) -> dict:
        g = self._guild(guild_id)
        bid = str(bot_member.id)
        if bid not in g:
            g[bid] = {
                'id': bid,
                'name': bot_member.name,
                'display_name': bot_member.display_name,
                'avatar': str(bot_member.display_avatar.url),
                'commands': {},
                'prefixes': [],
                'slash_commands': [],
                'message_count': 0,
                'first_seen': datetime.now(timezone.utc).isoformat(),
                'last_seen': datetime.now(timezone.utc).isoformat(),
            }
        g[bid]['name'] = bot_member.name
        g[bid]['last_seen'] = datetime.now(timezone.utc).isoformat()
        return g[bid]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track bot messages and detect command patterns."""
        if not message.guild or not message.author.bot:
            return
        if message.author.id == self.bot.user.id:
            return

        entry = self._bot_entry(message.guild.id, message.author)
        entry['message_count'] = entry.get('message_count', 0) + 1

        if message.reference and message.reference.resolved:
            ref = message.reference.resolved
            if isinstance(ref, discord.Message) and not ref.author.bot:
                content = ref.content.strip()
                m = re.match(r'^([^a-zA-Z0-9\s]{1,3})', content)
                if m:
                    prefix = m.group(1)
                    if prefix not in entry['prefixes']:
                        entry['prefixes'].append(prefix)
                    cmd_match = re.match(r'^[^a-zA-Z0-9\s]{1,3}(\w+)', content)
                    if cmd_match:
                        cmd_name = cmd_match.group(1).lower()
                        if cmd_name not in entry['commands']:
                            entry['commands'][cmd_name] = {
                                'count': 0,
                                'last_used': None,
                                'example_trigger': content[:100],
                                'example_response': '',
                            }
                        entry['commands'][cmd_name]['count'] += 1
                        entry['commands'][cmd_name]['last_used'] = datetime.now(timezone.utc).isoformat()
                        if message.embeds:
                            entry['commands'][cmd_name]['example_response'] = (
                                message.embeds[0].title or message.embeds[0].description or ''
                            )[:200]
                        else:
                            entry['commands'][cmd_name]['example_response'] = message.content[:200]

        if message.interaction:
            cmd_name = message.interaction.name
            if cmd_name not in entry['commands']:
                entry['commands'][cmd_name] = {
                    'count': 0,
                    'last_used': None,
                    'example_trigger': f'/{cmd_name}',
                    'example_response': '',
                    'is_slash': True,
                }
            entry['commands'][cmd_name]['count'] += 1
            entry['commands'][cmd_name]['last_used'] = datetime.now(timezone.utc).isoformat()
            if message.embeds:
                entry['commands'][cmd_name]['example_response'] = (
                    message.embeds[0].title or message.embeds[0].description or ''
                )[:200]
            else:
                entry['commands'][cmd_name]['example_response'] = message.content[:200]

        self._pending_save = True

    @tasks.loop(minutes=2)
    async def _auto_save(self):
        if self._pending_save:
            _save(self.data)
            self._pending_save = False

    async def cog_load(self):
        self._auto_save.start()

    async def cog_unload(self):
        self._auto_save.cancel()
        _save(self.data)

    @commands.command(name='bot-scan')
    @commands.has_permissions(manage_guild=True)
    async def scan_bots(self, ctx: commands.Context):
        """Scan all bots in this server and show what they do"""
        guild = ctx.guild
        bots = [m for m in guild.members if m.bot and m.id != self.bot.user.id]

        if not bots:
            return await ctx.send('No other bots found in this server.')

        embed = discord.Embed(
            title=f'🤖 Bot Analysis — {guild.name}',
            description=f'Found **{len(bots)}** other bots. Tracking their activity...',
            color=0x7c3aed
        )

        for bot_member in bots[:10]:
            entry = self._bot_entry(guild.id, bot_member)
            cmd_count = len(entry.get('commands', {}))
            msg_count = entry.get('message_count', 0)
            top_cmds = sorted(entry.get('commands', {}).items(), key=lambda x: x[1].get('count', 0), reverse=True)[:3]
            top_str = ', '.join(f'`{k}`' for k, _ in top_cmds) if top_cmds else 'None detected yet'
            embed.add_field(
                name=f'{bot_member.display_name}',
                value=f'📨 {msg_count} msgs • 🔧 {cmd_count} cmds\nTop: {top_str}',
                inline=True
            )

        _save(self.data)
        await ctx.send(embed=embed)

    @commands.command(name='bot-report')
    @commands.has_permissions(manage_guild=True)
    async def report_bot(self, ctx: commands.Context, bot_user: discord.Member):
        """Get a detailed report on a specific bot: !bot-report @bot"""
        if not bot_user.bot:
            return await ctx.send('That is not a bot.')

        g = self._guild(ctx.guild.id)
        entry = g.get(str(bot_user.id))
        if not entry:
            return await ctx.send(
                f'No data collected for {bot_user.display_name} yet. Use `!bot-scan` first.')

        embed = discord.Embed(
            title=f'📊 {bot_user.display_name} Report',
            color=0x5865f2
        )
        embed.set_thumbnail(url=bot_user.display_avatar.url)
        embed.add_field(name='Messages Sent', value=str(entry.get('message_count', 0)), inline=True)
        embed.add_field(name='Commands Detected', value=str(len(entry.get('commands', {}))), inline=True)
        embed.add_field(name='Last Seen', value=entry.get('last_seen', 'Unknown')[:10], inline=True)

        prefixes = entry.get('prefixes', [])
        if prefixes:
            embed.add_field(name='Detected Prefixes', value=' '.join(f'`{p}`' for p in prefixes[:5]), inline=False)

        cmds = sorted(entry.get('commands', {}).items(), key=lambda x: x[1].get('count', 0), reverse=True)[:10]
        if cmds:
            cmd_lines = '\n'.join(f'`{k}` — used {v.get("count",0)}x' for k, v in cmds)
            embed.add_field(name='Top Commands', value=cmd_lines, inline=False)

        await ctx.send(embed=embed)

    def get_guild_data(self, guild_id: int) -> dict:
        """Return analyzer data for a guild (used by dashboard API)."""
        return self._guild(guild_id)
