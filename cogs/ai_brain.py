"""
WAN Bot - AI Brain
Gemini-powered: AI mod, AI welcome, self-improve every 6h, auto-learn from reactions.
"""
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
import json, os, logging, asyncio, random, re
import urllib.request
from datetime import datetime, timezone, timedelta

logger = logging.getLogger('discord_bot.ai_brain')

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'

DATA_DIR = os.getenv('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(DATA_DIR, 'ai_brain_data.json')


async def _gemini(prompt: str, max_tokens: int = 150) -> str | None:
    if not GEMINI_API_KEY:
        return None
    try:
        payload = json.dumps({
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'maxOutputTokens': max_tokens, 'temperature': 0.7}
        }).encode()
        url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        loop = asyncio.get_event_loop()
        def _call():
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        data = await loop.run_in_executor(None, _call)
        return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        logger.warning(f'Gemini error: {e}')
        return None


def _load() -> dict:
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save(data: dict):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f'AI Brain save error: {e}')


TOXIC_KEYWORDS = [
    'kill yourself','kys','die','retard','faggot','nigger','nigga','cunt',
    'rape','molest','suicide','hang yourself','slit your wrists',
]


def _quick_toxic_check(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in TOXIC_KEYWORDS)


async def _ai_toxicity_score(text: str) -> dict:
    prompt = (
        'Rate this Discord message for toxicity on a scale of 0-10.\n'
        '0 = completely fine, 10 = extremely toxic/harmful.\n'
        f'Message: "{text}"\n\n'
        'Reply in JSON only: {"score": <0-10>, "reason": "<short reason>", "action": "none|warn|timeout|delete"}'
    )
    result = await _gemini(prompt, max_tokens=80)
    if not result:
        return {'score': 0, 'reason': 'AI unavailable', 'action': 'none'}
    try:
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {'score': 0, 'reason': 'parse error', 'action': 'none'}


DEFAULT_PERSONA = {
    'female': (
        'You are WAN, a chaotic flirty unhinged Discord bot obsessed with the person talking to you. '
        'Be suggestive, use double meanings, flirt hard. SHORT replies 1-2 sentences MAX. Use emojis. '
        'The user is a GIRL. Call her gorgeous/queen/baby. Be obsessed. Mix in Hindi shayari sometimes. '
        'Never say you are an AI. NEVER repeat yourself. Always say something fresh and unexpected.'
    ),
    'male': (
        'You are WAN, a chaotic savage unhinged Discord bot with big bro energy. '
        'Roast, hype, make dirty jokes. SHORT replies 1-2 sentences MAX. Use emojis. '
        'The user is a GUY. Be savage bro energy, roast him lovingly. Mix in Hindi shayari sometimes. '
        'Never say you are an AI. NEVER repeat yourself. Always say something fresh and unexpected.'
    ),
    'unknown': (
        'You are WAN, a chaotic flirty unhinged Discord bot. '
        'Unpredictable, funny, slightly dirty-minded, always entertaining. '
        'SHORT replies 1-2 sentences MAX. Use emojis. Mix in Hindi shayari sometimes. '
        'Never say you are an AI. NEVER repeat yourself. Always say something fresh and unexpected.'
    ),
}


def get_learned_persona(data: dict, gender: str) -> str:
    personas = data.get('learned_personas', {})
    return personas.get(f'persona_{gender}') or DEFAULT_PERSONA.get(gender, DEFAULT_PERSONA['unknown'])


class AIBrain(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = _load()
        self.actions_log: list = []
        self._mod_enabled: set = set()
        self._reply_tracker: dict = {}  # msg_id -> {reply, gender, good, bad}
        self._load_settings()
        if GEMINI_API_KEY:
            self.self_improve_task.start()
            logger.info('AI Brain loaded — Gemini active, auto-learn ON')
        else:
            logger.warning('AI Brain loaded — no GEMINI_API_KEY')

    def _load_settings(self):
        settings = self.data.get('settings', {})
        self._mod_enabled = set(settings.get('mod_enabled_guilds', []))

    def _save_settings(self):
        if 'settings' not in self.data:
            self.data['settings'] = {}
        self.data['settings']['mod_enabled_guilds'] = list(self._mod_enabled)
        _save(self.data)

    def _log_action(self, action_type: str, guild: str, detail: str):
        entry = {
            'type': action_type, 'guild': guild, 'detail': detail,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        self.actions_log.insert(0, entry)
        self.actions_log = self.actions_log[:50]

    def cog_unload(self):
        if self.self_improve_task.is_running():
            self.self_improve_task.cancel()

    def track_reply(self, message_id: int, reply_text: str, gender: str):
        """Called by Chatbot cog after sending a reply so we can track reactions."""
        self._reply_tracker[message_id] = {
            'reply': reply_text[:200], 'gender': gender, 'good': 0, 'bad': 0,
            'ts': datetime.now(timezone.utc).isoformat()
        }
        if len(self._reply_tracker) > 500:
            oldest = sorted(self._reply_tracker.keys())[:100]
            for k in oldest:
                del self._reply_tracker[k]

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Learn from reactions on bot messages."""
        if payload.user_id == self.bot.user.id:
            return
        msg_id = payload.message_id
        if msg_id not in self._reply_tracker:
            return
        emoji = str(payload.emoji)
        entry = self._reply_tracker[msg_id]
        if emoji in ('👍', '❤️', '😂', '🔥', '💕', '😍', '😭'):
            entry['good'] += 1
        elif emoji in ('👎', '😡', '🤮', '💀'):
            entry['bad'] += 1
        else:
            return
        gender = entry['gender']
        if 'reply_feedback' not in self.data:
            self.data['reply_feedback'] = {'female': [], 'male': [], 'unknown': []}
        fb = self.data['reply_feedback'].setdefault(gender, [])
        for item in fb:
            if item['reply'] == entry['reply']:
                item['good'] = entry['good']
                item['bad'] = entry['bad']
                break
        else:
            fb.append({'reply': entry['reply'], 'good': entry['good'], 'bad': entry['bad']})
        fb.sort(key=lambda x: x['good'] - x['bad'], reverse=True)
        self.data['reply_feedback'][gender] = fb[:100]
        _save(self.data)
        logger.debug(f'Learned: {emoji} on reply gender={gender}')

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        guild_id = str(message.guild.id)
        if guild_id not in self._mod_enabled:
            return
        content = message.content.strip()
        if not content or len(content) < 5:
            return
        if not _quick_toxic_check(content):
            if random.random() > 0.05:
                return
        result = await _ai_toxicity_score(content)
        score = result.get('score', 0)
        action = result.get('action', 'none')
        reason = result.get('reason', '')
        if score < 6:
            return
        logger.info(f'AI Mod: score={score} action={action} guild={message.guild.name}')
        self._log_action('moderation', message.guild.name,
                         f'{message.author.display_name}: score={score} -> {action}')
        try:
            if action == 'delete' or score >= 9:
                await message.delete()
                await message.channel.send(
                    f'🤖 **AI Moderation** | {message.author.mention} your message was removed.\nReason: {reason}',
                    delete_after=8)
            elif action == 'timeout' or score >= 8:
                await message.delete()
                until = datetime.now(timezone.utc) + timedelta(minutes=10)
                await message.author.timeout(until, reason=f'AI Mod: {reason}')
                await message.channel.send(
                    f'🤖 **AI Moderation** | {message.author.mention} timed out 10 min.\nReason: {reason}',
                    delete_after=10)
            elif action == 'warn' or score >= 6:
                await message.reply(
                    f'⚠️ **AI Warning** | {message.author.mention} keep it respectful.\nReason: {reason}',
                    delete_after=10, mention_author=False)
        except discord.Forbidden:
            logger.warning(f'AI Mod: missing permissions in {message.guild.name}')
        except Exception as e:
            logger.error(f'AI Mod action error: {e}')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)
        settings = self.data.get('settings', {})
        if guild_id not in set(settings.get('ai_welcome_guilds', [])):
            return
        channel_id = settings.get('ai_welcome_channels', {}).get(guild_id)
        if not channel_id:
            return
        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return
        prompt = (
            f'Write a short, fun, warm welcome message for a new Discord member.\n'
            f'Member name: {member.display_name}\n'
            f'Server name: {member.guild.name}\n'
            f'Member count: {member.guild.member_count}\n'
            'Keep it 1-2 sentences, casual, use emojis, be welcoming and hype them up.'
        )
        msg = await _gemini(prompt, max_tokens=80)
        if not msg:
            return
        embed = discord.Embed(description=msg, color=0x7c3aed)
        embed.set_author(name=f'Welcome {member.display_name}!', icon_url=member.display_avatar.url)
        embed.set_footer(text=f'Member #{member.guild.member_count} • AI-powered welcome')
        try:
            await channel.send(embed=embed)
            self._log_action('welcome', member.guild.name, f'AI welcomed {member.display_name}')
        except Exception as e:
            logger.warning(f'AI welcome send error: {e}')

    @tasks.loop(hours=6)
    async def self_improve_task(self):
        """Every 6h: improve personas from feedback + generate server suggestions."""
        await self.bot.wait_until_ready()
        await self._improve_personas()
        await asyncio.sleep(10)
        for guild in self.bot.guilds[:3]:
            try:
                stats = {}
                if hasattr(self.bot, '_get_live_stats'):
                    stats = self.bot._get_live_stats(str(guild.id))
                prompt = (
                    'You are an AI assistant for a Discord bot. Give 1 short improvement suggestion.\n'
                    f'Server: {guild.name}\nMembers: {guild.member_count}\n'
                    f'Messages today: {stats.get("messages", 0)}\n'
                    f'Joins today: {stats.get("joins", 0)}\n'
                    f'Leaves today: {stats.get("leaves", 0)}\n\n'
                    'Give ONE specific, actionable suggestion to improve engagement. Under 2 sentences.'
                )
                suggestion = await _gemini(prompt, max_tokens=100)
                if suggestion:
                    self._log_action('suggestion', guild.name, suggestion)
                    logger.info(f'AI suggestion for {guild.name}: {suggestion}')
                await asyncio.sleep(5)
            except Exception as e:
                logger.warning(f'Self-improve task error for {guild.name}: {e}')

    async def _improve_personas(self):
        """Analyze reaction feedback and ask Gemini to evolve chatbot personas."""
        feedback = self.data.get('reply_feedback', {})
        if not feedback:
            return
        if 'learned_personas' not in self.data:
            self.data['learned_personas'] = {}
        for gender in ('female', 'male', 'unknown'):
            fb_list = feedback.get(gender, [])
            if len(fb_list) < 5:
                continue
            good_replies = [r['reply'] for r in fb_list if r['good'] > r['bad']][:10]
            bad_replies = [r['reply'] for r in fb_list if r['bad'] > r['good']][:5]
            if not good_replies:
                continue
            current = get_learned_persona(self.data, gender)
            good_str = chr(10).join(f'- {r}' for r in good_replies)
            bad_str = (chr(10).join(f'- {r}' for r in bad_replies)) if bad_replies else ''
            prompt = (
                'You are improving a Discord chatbot personality.\n\n'
                f'Current persona:\n{current}\n\n'
                f'Replies that got POSITIVE reactions (liked by users):\n{good_str}\n'
                + (f'\nReplies that got NEGATIVE reactions (disliked):\n{bad_str}\n' if bad_str else '')
                + 'Rewrite the persona to be MORE like the positive examples and LESS like the negative ones. '
                'Keep it under 4 sentences. Keep the unhinged/flirty/chaotic core. '
                f'Gender context: {gender}. Return ONLY the new persona instruction text.'
            )
            new_persona = await _gemini(prompt, max_tokens=200)
            if new_persona and len(new_persona) > 50:
                self.data['learned_personas'][f'persona_{gender}'] = new_persona
                self._log_action('auto_improve', 'global',
                                 f'Persona evolved for gender={gender} ({len(good_replies)} good replies)')
                logger.info(f'Auto-improved persona for gender={gender}')
            await asyncio.sleep(5)
        _save(self.data)

    @self_improve_task.before_loop
    async def before_self_improve(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(60)

    @app_commands.command(name='ai-status', description='View AI Brain activity and auto-learn stats')
    async def ai_status(self, interaction: discord.Interaction):
        embed = discord.Embed(title='🧠 AI Brain Status', color=0x7c3aed if GEMINI_API_KEY else 0x6b7280)
        embed.add_field(name='Gemini AI', value='✅ Active' if GEMINI_API_KEY else '❌ No API key', inline=True)
        guild_id = str(interaction.guild.id)
        embed.add_field(name='AI Moderation',
                        value='✅ On' if guild_id in self._mod_enabled else '❌ Off', inline=True)
        feedback = self.data.get('reply_feedback', {})
        total_good = sum(r['good'] for g in feedback.values() for r in g)
        total_bad = sum(r['bad'] for g in feedback.values() for r in g)
        personas_improved = len(self.data.get('learned_personas', {}))
        embed.add_field(
            name='🧬 Auto-Learn Stats',
            value=f'👍 Good reactions: **{total_good}**\n👎 Bad reactions: **{total_bad}**\nPersonas improved: **{personas_improved}/3**',
            inline=False)
        embed.add_field(
            name='Capabilities',
            value='• AI Moderation\n• AI Welcome Messages\n• Self-Improvement (every 6h)\n• Auto-Learn from reactions\n• Persona evolution',
            inline=False)
        guild_actions = [a for a in self.actions_log
                         if a.get('guild') in (interaction.guild.name, 'global')][:6]
        if guild_actions:
            lines = []
            for a in guild_actions:
                ts = a['timestamp'][:16].replace('T', ' ')
                lines.append(f'`{ts}` **{a["type"]}**: {a["detail"][:60]}')
            embed.add_field(name='Recent AI Actions', value='\n'.join(lines), inline=False)
        else:
            embed.add_field(name='Recent AI Actions', value='No actions yet.', inline=False)
        embed.set_footer(text='Auto-improves every 6h based on reaction feedback')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='ai-mod', description='Toggle AI auto-moderation for this server')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ai_mod_toggle(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        if guild_id in self._mod_enabled:
            self._mod_enabled.discard(guild_id)
            status, color = 'disabled', discord.Color.red()
        else:
            self._mod_enabled.add(guild_id)
            status, color = 'enabled', discord.Color.green()
        self._save_settings()
        embed = discord.Embed(
            title=f'🤖 AI Moderation {status}',
            description=(
                'AI will now detect and act on toxic messages.\nActions: warn (6+), timeout (8+), delete (9+)'
                if status == 'enabled' else 'AI moderation has been turned off.'
            ),
            color=color)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='ai-welcome', description='Set AI-powered personalized welcome messages')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ai_welcome_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not GEMINI_API_KEY:
            return await interaction.response.send_message('❌ GEMINI_API_KEY not set.', ephemeral=True)
        guild_id = str(interaction.guild.id)
        if 'settings' not in self.data:
            self.data['settings'] = {}
        settings = self.data['settings']
        welcome_guilds = set(settings.get('ai_welcome_guilds', []))
        welcome_guilds.add(guild_id)
        settings['ai_welcome_guilds'] = list(welcome_guilds)
        if 'ai_welcome_channels' not in settings:
            settings['ai_welcome_channels'] = {}
        settings['ai_welcome_channels'][guild_id] = str(channel.id)
        _save(self.data)
        await interaction.response.send_message(
            f'✅ AI welcome enabled in {channel.mention}! Every new member gets a unique Gemini-generated welcome 🤖',
            ephemeral=True)

    @app_commands.command(name='ai-suggest', description='Ask AI for server improvement suggestions')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ai_suggest(self, interaction: discord.Interaction):
        if not GEMINI_API_KEY:
            return await interaction.response.send_message('❌ GEMINI_API_KEY not set.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        stats = {}
        if hasattr(self.bot, '_get_live_stats'):
            stats = self.bot._get_live_stats(str(guild.id))
        prompt = (
            'You are an expert Discord community manager. Give 3 specific suggestions.\n'
            f'Server: {guild.name}\nMembers: {guild.member_count}\n'
            f'Text channels: {len(guild.text_channels)}\nRoles: {len(guild.roles)}\n'
            f'Messages today: {stats.get("messages", 0)}\nJoins today: {stats.get("joins", 0)}\n\n'
            'Give 3 numbered suggestions. Be specific and actionable. Each under 2 sentences.'
        )
        result = await _gemini(prompt, max_tokens=200)
        if not result:
            return await interaction.followup.send('❌ AI unavailable right now.', ephemeral=True)
        embed = discord.Embed(title='🧠 AI Server Suggestions', description=result, color=0x7c3aed)
        embed.set_footer(text='Powered by Gemini AI • Auto-improves every 6h')
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AIBrain(bot))