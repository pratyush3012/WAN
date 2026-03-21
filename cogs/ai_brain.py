"""
WAN Bot - AI Brain
Gemini-powered intelligence layer:
- AI moderation: auto-warn/timeout toxic messages
- AI welcome: personalized welcome messages
- AI leveling: dynamic XP multipliers based on activity
- Self-improvement: background analysis + suggestions
- /ai-status command
"""
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
import json, os, logging, asyncio, random
import urllib.request
from datetime import datetime, timezone, timedelta

logger = logging.getLogger('discord_bot.ai_brain')

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'

DATA_DIR = os.getenv('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(DATA_DIR, 'ai_brain_data.json')

# ── Gemini helper ─────────────────────────────────────────────────────────────

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
        logger.warning(f"Gemini error: {e}")
        return None

# ── Data helpers ──────────────────────────────────────────────────────────────

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
        logger.error(f"AI Brain save error: {e}")

# ── Toxicity check ────────────────────────────────────────────────────────────

TOXIC_KEYWORDS = [
    'kill yourself','kys','die','retard','faggot','nigger','nigga','cunt',
    'rape','molest','suicide','hang yourself','slit your wrists',
]

def _quick_toxic_check(text: str) -> bool:
    """Fast keyword check before calling Gemini."""
    lower = text.lower()
    return any(kw in lower for kw in TOXIC_KEYWORDS)

async def _ai_toxicity_score(text: str) -> dict:
    """Ask Gemini to rate toxicity 0-10 and suggest action."""
    prompt = (
        f"Rate this Discord message for toxicity on a scale of 0-10.\n"
        f"0 = completely fine, 10 = extremely toxic/harmful.\n"
        f"Message: \"{text}\"\n\n"
        f"Reply in JSON only: {{\"score\": <0-10>, \"reason\": \"<short reason>\", \"action\": \"none|warn|timeout|delete\"}}"
    )
    result = await _gemini(prompt, max_tokens=80)
    if not result:
        return {'score': 0, 'reason': 'AI unavailable', 'action': 'none'}
    try:
        # Extract JSON from response
        import re
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {'score': 0, 'reason': 'parse error', 'action': 'none'}

# ── AI Brain Cog ──────────────────────────────────────────────────────────────

class AIBrain(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = _load()
        self.actions_log: list = []  # recent AI actions for /ai-status
        self._mod_enabled: set = set()  # guild IDs with AI mod enabled
        self._load_settings()
        if GEMINI_API_KEY:
            self.self_improve_task.start()
            logger.info("AI Brain loaded — Gemini active")
        else:
            logger.warning("AI Brain loaded — no GEMINI_API_KEY, limited functionality")

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
            'type': action_type,
            'guild': guild,
            'detail': detail,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        self.actions_log.insert(0, entry)
        self.actions_log = self.actions_log[:50]  # keep last 50

    def cog_unload(self):
        if self.self_improve_task.is_running():
            self.self_improve_task.cancel()

    # ── AI Moderation ──────────────────────────────────────────────────────────

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

        # Fast keyword check first (avoid Gemini calls for clean messages)
        if not _quick_toxic_check(content):
            # Only call Gemini for borderline cases (random 5% sample for performance)
            if random.random() > 0.05:
                return

        result = await _ai_toxicity_score(content)
        score = result.get('score', 0)
        action = result.get('action', 'none')
        reason = result.get('reason', '')

        if score < 6:
            return

        logger.info(f"AI Mod: score={score} action={action} guild={message.guild.name} user={message.author}")
        self._log_action('moderation', message.guild.name, f"{message.author.display_name}: score={score} → {action}")

        try:
            if action == 'delete' or score >= 9:
                await message.delete()
                await message.channel.send(
                    f"🤖 **AI Moderation** | {message.author.mention} your message was removed.\n"
                    f"Reason: {reason}",
                    delete_after=8
                )
            elif action == 'timeout' or score >= 8:
                await message.delete()
                until = datetime.now(timezone.utc) + timedelta(minutes=10)
                await message.author.timeout(until, reason=f"AI Mod: {reason}")
                await message.channel.send(
                    f"🤖 **AI Moderation** | {message.author.mention} has been timed out for 10 minutes.\n"
                    f"Reason: {reason}",
                    delete_after=10
                )
            elif action == 'warn' or score >= 6:
                await message.reply(
                    f"⚠️ **AI Warning** | {message.author.mention} please keep it respectful.\n"
                    f"Reason: {reason}",
                    delete_after=10,
                    mention_author=False
                )
        except discord.Forbidden:
            logger.warning(f"AI Mod: missing permissions in {message.guild.name}")
        except Exception as e:
            logger.error(f"AI Mod action error: {e}")

    # ── AI Welcome ─────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Generate a personalized AI welcome message."""
        guild_id = str(member.guild.id)
        settings = self.data.get('settings', {})
        welcome_guilds = set(settings.get('ai_welcome_guilds', []))
        if guild_id not in welcome_guilds:
            return

        channel_id = settings.get('ai_welcome_channels', {}).get(guild_id)
        if not channel_id:
            return
        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return

        prompt = (
            f"Write a short, fun, warm welcome message for a new Discord member.\n"
            f"Member name: {member.display_name}\n"
            f"Server name: {member.guild.name}\n"
            f"Member count: {member.guild.member_count}\n"
            f"Keep it 1-2 sentences, casual, use emojis, be welcoming and hype them up."
        )
        msg = await _gemini(prompt, max_tokens=80)
        if not msg:
            return

        embed = discord.Embed(description=msg, color=0x7c3aed)
        embed.set_author(name=f"Welcome {member.display_name}!", icon_url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{member.guild.member_count} • AI-powered welcome")
        try:
            await channel.send(embed=embed)
            self._log_action('welcome', member.guild.name, f"AI welcomed {member.display_name}")
        except Exception as e:
            logger.warning(f"AI welcome send error: {e}")

    # ── Self-improvement background task ───────────────────────────────────────

    @tasks.loop(hours=6)
    async def self_improve_task(self):
        """Every 6 hours, analyze server activity and log AI suggestions."""
        await self.bot.wait_until_ready()
        if not self.bot.guilds:
            return

        for guild in self.bot.guilds[:3]:  # limit to 3 guilds per cycle
            try:
                stats = {}
                if hasattr(self.bot, '_get_live_stats'):
                    stats = self.bot._get_live_stats(str(guild.id))

                prompt = (
                    f"You are an AI assistant for a Discord bot. Analyze this server activity and give 1 short improvement suggestion.\n"
                    f"Server: {guild.name}\n"
                    f"Members: {guild.member_count}\n"
                    f"Messages today: {stats.get('messages', 0)}\n"
                    f"Joins today: {stats.get('joins', 0)}\n"
                    f"Leaves today: {stats.get('leaves', 0)}\n\n"
                    f"Give ONE specific, actionable suggestion to improve engagement. Keep it under 2 sentences."
                )
                suggestion = await _gemini(prompt, max_tokens=100)
                if suggestion:
                    self._log_action('suggestion', guild.name, suggestion)
                    logger.info(f"AI suggestion for {guild.name}: {suggestion}")

                await asyncio.sleep(5)  # rate limit between guilds
            except Exception as e:
                logger.warning(f"Self-improve task error for {guild.name}: {e}")

    @self_improve_task.before_loop
    async def before_self_improve(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(60)  # wait 1 min after startup

    # ── Slash commands ─────────────────────────────────────────────────────────

    @app_commands.command(name="ai-status", description="🤖 View AI Brain activity and recent actions")
    async def ai_status(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🧠 AI Brain Status",
            color=0x7c3aed if GEMINI_API_KEY else 0x6b7280
        )
        embed.add_field(
            name="Gemini AI",
            value="✅ Active" if GEMINI_API_KEY else "❌ No API key set",
            inline=True
        )
        guild_id = str(interaction.guild.id)
        embed.add_field(
            name="AI Moderation",
            value="✅ On" if guild_id in self._mod_enabled else "❌ Off",
            inline=True
        )
        embed.add_field(
            name="Capabilities",
            value="• AI Moderation\n• AI Welcome Messages\n• Self-Improvement Analysis\n• Chatbot (Gemini-powered)",
            inline=False
        )

        # Recent actions for this guild
        guild_actions = [a for a in self.actions_log if a.get('guild') == interaction.guild.name][:5]
        if guild_actions:
            lines = []
            for a in guild_actions:
                ts = a['timestamp'][:16].replace('T', ' ')
                lines.append(f"`{ts}` **{a['type']}**: {a['detail'][:60]}")
            embed.add_field(name="Recent AI Actions", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Recent AI Actions", value="No actions yet.", inline=False)

        embed.set_footer(text="Use /ai-mod to toggle AI moderation")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ai-mod", description="🤖 Toggle AI auto-moderation for this server")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ai_mod_toggle(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        if guild_id in self._mod_enabled:
            self._mod_enabled.discard(guild_id)
            status = "disabled"
            color = discord.Color.red()
        else:
            self._mod_enabled.add(guild_id)
            status = "enabled"
            color = discord.Color.green()
        self._save_settings()
        embed = discord.Embed(
            title=f"🤖 AI Moderation {status}",
            description=(
                "AI will now automatically detect and act on toxic messages.\n"
                "Actions: warn (score 6+), timeout (score 8+), delete (score 9+)"
                if status == "enabled" else
                "AI moderation has been turned off for this server."
            ),
            color=color
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ai-welcome", description="🤖 Set AI-powered personalized welcome messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ai_welcome_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not GEMINI_API_KEY:
            return await interaction.response.send_message("❌ GEMINI_API_KEY not set. AI welcome requires Gemini.", ephemeral=True)
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
            f"✅ AI welcome messages enabled in {channel.mention}!\n"
            f"Every new member will get a unique, personalized welcome generated by Gemini AI 🤖",
            ephemeral=True
        )

    @app_commands.command(name="ai-suggest", description="🤖 Ask AI for a server improvement suggestion")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ai_suggest(self, interaction: discord.Interaction):
        if not GEMINI_API_KEY:
            return await interaction.response.send_message("❌ GEMINI_API_KEY not set.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        stats = {}
        if hasattr(self.bot, '_get_live_stats'):
            stats = self.bot._get_live_stats(str(guild.id))
        prompt = (
            f"You are an expert Discord community manager. Give 3 specific suggestions to improve this server.\n"
            f"Server: {guild.name}\n"
            f"Members: {guild.member_count}\n"
            f"Text channels: {len(guild.text_channels)}\n"
            f"Roles: {len(guild.roles)}\n"
            f"Messages today: {stats.get('messages', 0)}\n"
            f"Joins today: {stats.get('joins', 0)}\n\n"
            f"Give 3 numbered suggestions. Be specific and actionable. Keep each under 2 sentences."
        )
        result = await _gemini(prompt, max_tokens=200)
        if not result:
            return await interaction.followup.send("❌ AI unavailable right now. Try again later.", ephemeral=True)
        embed = discord.Embed(
            title="🧠 AI Server Suggestions",
            description=result,
            color=0x7c3aed
        )
        embed.set_footer(text="Powered by Gemini AI")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AIBrain(bot))
