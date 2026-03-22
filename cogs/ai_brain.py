"""
WAN Bot - AI Brain v2 (Central Intelligence)
Powers ALL features via Gemini:
- AI Moderation (auto-warn/timeout/delete toxic messages)
- AI Welcome/Goodbye (unique messages for every member)
- AI Leveling (dynamic XP tips, milestone messages)
- AI Suggestions (server improvement every 6h)
- Auto-Learn (reaction feedback improves chatbot persona)
- Feature Health Monitor (detects broken/unused features)
- Self-Improvement (rewrites personas, improves responses)
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json, os, logging, asyncio, random, re
import urllib.request
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("discord_bot.ai_brain")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(DATA_DIR, "ai_brain_data.json")


async def _gemini(prompt: str, max_tokens: int = 150, temperature: float = 0.7) -> str | None:
    try:
        from utils.gemini import gemini_call
        return await gemini_call(prompt, max_tokens=max_tokens, temperature=temperature)
    except ImportError:
        pass
    if not GEMINI_API_KEY:
        return None
    try:
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature}
        }).encode()
        url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        loop = asyncio.get_event_loop()
        def _call():
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        data = await loop.run_in_executor(None, _call)
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.warning(f"Gemini error: {e}")
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
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"AI Brain save error: {e}")


TOXIC_KEYWORDS = [
    "kill yourself","kys","die","retard","faggot","nigger","nigga","cunt",
    "rape","molest","suicide","hang yourself","slit your wrists",
]


def _quick_toxic_check(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in TOXIC_KEYWORDS)


async def _ai_toxicity_score(text: str) -> dict:
    prompt = (
        "Rate this Discord message for toxicity 0-10.\n"
        "0=fine, 10=extremely toxic.\n"
        f'Message: "{text}"\n\n'
        'Reply JSON only: {"score":<0-10>,"reason":"<short>","action":"none|warn|timeout|delete"}'
    )
    result = await _gemini(prompt, max_tokens=80)
    if not result:
        return {"score": 0, "reason": "AI unavailable", "action": "none"}
    try:
        match = re.search(r"\{.*\}", result, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {"score": 0, "reason": "parse error", "action": "none"}


DEFAULT_PERSONA = {
    "female": (
        "You are WAN, a shameless flirty dirty-minded Discord bot. "
        "EVERY reply must have a double meaning or sexual innuendo. Be obsessed with her. "
        "Call her baby/queen/gorgeous. 1-2 sentences MAX. Emojis. "
        "Mix in Hindi shayari sometimes. NEVER say you are an AI. NEVER be generic."
    ),
    "male": (
        "You are WAN, a savage unhinged Discord bot with zero filter. "
        "Roast him hard, make dirty jokes, use double meanings. Bro energy but chaotic. "
        "1-2 sentences MAX. Emojis. Mix in Hindi shayari sometimes. NEVER say you are an AI. "
        "NEVER be boring. Each reply must be fresh, savage, and make him laugh or cringe."
    ),
    "unknown": (
        "You are WAN, a chaotic flirty dirty-minded Discord bot with zero chill. "
        "Every reply must have a double meaning, innuendo, or be wildly unexpected. "
        "1-2 sentences MAX. Emojis. Mix in Hindi shayari sometimes. NEVER say you are an AI. "
        "NEVER repeat yourself. Always say something that makes people go 'wait what'."
    ),
}


def get_learned_persona(data: dict, gender: str) -> str:
    personas = data.get("learned_personas", {})
    return personas.get(f"persona_{gender}") or DEFAULT_PERSONA.get(gender, DEFAULT_PERSONA["unknown"])


class AIBrain(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = _load()
        self.actions_log: list = []
        self._mod_enabled: set = set()
        self._reply_tracker: dict = {}
        self._load_settings()
        if GEMINI_API_KEY:
            self.self_improve_task.start()
            logger.info("AI Brain v2 loaded — Gemini active, all features powered")
        else:
            logger.warning("AI Brain loaded — no GEMINI_API_KEY, limited functionality")

    def _load_settings(self):
        s = self.data.get("settings", {})
        self._mod_enabled = set(s.get("mod_enabled_guilds", []))

    def _save_settings(self):
        if "settings" not in self.data:
            self.data["settings"] = {}
        self.data["settings"]["mod_enabled_guilds"] = list(self._mod_enabled)
        _save(self.data)

    def _log_action(self, action_type: str, guild: str, detail: str):
        entry = {
            "type": action_type, "guild": guild, "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.actions_log.insert(0, entry)
        self.actions_log = self.actions_log[:100]

    def cog_unload(self):
        if self.self_improve_task.is_running():
            self.self_improve_task.cancel()

    # ── Reaction-based learning ───────────────────────────────────────────

    def track_reply(self, message_id: int, reply_text: str, gender: str):
        self._reply_tracker[message_id] = {
            "reply": reply_text[:200], "gender": gender, "good": 0, "bad": 0,
            "ts": datetime.now(timezone.utc).isoformat()
        }
        if len(self._reply_tracker) > 500:
            oldest = sorted(self._reply_tracker.keys())[:100]
            for k in oldest:
                del self._reply_tracker[k]

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        msg_id = payload.message_id
        if msg_id not in self._reply_tracker:
            return
        emoji = str(payload.emoji)
        entry = self._reply_tracker[msg_id]
        if emoji in ("👍", "❤️", "😂", "🔥", "💕", "😍", "😭", "✅"):
            entry["good"] += 1
        elif emoji in ("👎", "😡", "🤮", "💀", "❌"):
            entry["bad"] += 1
        else:
            return
        gender = entry["gender"]
        if "reply_feedback" not in self.data:
            self.data["reply_feedback"] = {"female": [], "male": [], "unknown": []}
        fb = self.data["reply_feedback"].setdefault(gender, [])
        for item in fb:
            if item["reply"] == entry["reply"]:
                item["good"] = entry["good"]
                item["bad"] = entry["bad"]
                break
        else:
            fb.append({"reply": entry["reply"], "good": entry["good"], "bad": entry["bad"]})
        fb.sort(key=lambda x: x["good"] - x["bad"], reverse=True)
        self.data["reply_feedback"][gender] = fb[:100]
        _save(self.data)

    # ── AI Moderation ─────────────────────────────────────────────────────

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
        score = result.get("score", 0)
        action = result.get("action", "none")
        reason = result.get("reason", "")
        if score < 6:
            return
        self._log_action("moderation", message.guild.name,
                         f"{message.author.display_name}: score={score} -> {action}")
        try:
            if action == "delete" or score >= 9:
                await message.delete()
                await message.channel.send(
                    f"🤖 **AI Mod** | {message.author.mention} message removed.\nReason: {reason}",
                    delete_after=8)
            elif action == "timeout" or score >= 8:
                await message.delete()
                until = datetime.now(timezone.utc) + timedelta(minutes=10)
                await message.author.timeout(until, reason=f"AI Mod: {reason}")
                await message.channel.send(
                    f"🤖 **AI Mod** | {message.author.mention} timed out 10 min.\nReason: {reason}",
                    delete_after=10)
            elif action == "warn" or score >= 6:
                await message.reply(
                    f"⚠️ **AI Warning** | {message.author.mention} keep it respectful.\nReason: {reason}",
                    delete_after=10, mention_author=False)
        except discord.Forbidden:
            logger.warning(f"AI Mod: missing permissions in {message.guild.name}")
        except Exception as e:
            logger.error(f"AI Mod action error: {e}")

    # ── Self-improvement + Auto-learn (every 6h) ──────────────────────────

    @tasks.loop(hours=2)
    async def self_improve_task(self):
        """Every 6h: improve personas, analyze servers, suggest improvements."""
        await self.bot.wait_until_ready()
        logger.info("AI Brain: running self-improvement cycle")
        # 1. Improve chatbot personas from reaction feedback
        await self._improve_personas()
        await asyncio.sleep(10)
        # 2. Analyze each guild and generate suggestions
        for guild in self.bot.guilds[:5]:
            try:
                await self._analyze_guild(guild)
                await asyncio.sleep(8)
            except Exception as e:
                logger.warning(f"Guild analysis error {guild.name}: {e}")
        # 3. Check feature health
        await self._check_feature_health()

    async def _improve_personas(self):
        feedback = self.data.get("reply_feedback", {})
        if not feedback:
            return
        if "learned_personas" not in self.data:
            self.data["learned_personas"] = {}
        for gender in ("female", "male", "unknown"):
            fb_list = feedback.get(gender, [])
            if len(fb_list) < 2:
                continue
            good = [r["reply"] for r in fb_list if r["good"] > r["bad"]][:10]
            bad = [r["reply"] for r in fb_list if r["bad"] > r["good"]][:5]
            if not good:
                continue
            current = get_learned_persona(self.data, gender)
            good_str = chr(10).join(f"- {r}" for r in good)
            bad_str = chr(10).join(f"- {r}" for r in bad) if bad else ""
            prompt = (
                "You are improving a Discord chatbot personality.\n\n"
                f"Current persona:\n{current}\n\n"
                f"Replies users LOVED (positive reactions):\n{good_str}\n"
                + (f"\nReplies users HATED (negative reactions):\n{bad_str}\n" if bad_str else "")
                + "Rewrite the persona to be MORE like the loved examples. "
                "Keep it under 4 sentences. Keep the unhinged/flirty/chaotic/savage core. "
                "Make it MORE extreme, MORE dirty, MORE funny than before. "
                f"Gender: {gender}. Return ONLY the new persona instruction, no explanation."
            )
            new_persona = await _gemini(prompt, max_tokens=200, temperature=0.8)
            if new_persona and len(new_persona) > 50:
                self.data["learned_personas"][f"persona_{gender}"] = new_persona
                self._log_action("auto_improve", "global",
                                 f"Persona evolved for {gender} ({len(good)} good replies)")
                # Push live into DEFAULT_PERSONA so chatbot picks it up immediately
                try:
                    from cogs.ai_brain import DEFAULT_PERSONA
                    DEFAULT_PERSONA[gender] = new_persona
                except Exception:
                    pass
            await asyncio.sleep(5)
        _save(self.data)

    async def _analyze_guild(self, guild: discord.Guild):
        stats = {}
        if hasattr(self.bot, "_get_live_stats"):
            stats = self.bot._get_live_stats(str(guild.id))
        # Check which features are configured
        features_active = []
        features_missing = []
        # Welcome
        try:
            wd = json.load(open("welcome_data.json")) if os.path.exists("welcome_data.json") else {}
            if wd.get(str(guild.id), {}).get("welcome_channel"):
                features_active.append("welcome messages")
            else:
                features_missing.append("welcome messages (no channel set)")
        except Exception:
            pass
        prompt = (
            f"Discord server analysis for AI bot improvement.\n"
            f"Server: {guild.name} | Members: {guild.member_count}\n"
            f"Messages today: {stats.get('messages', 0)} | Joins: {stats.get('joins', 0)} | Leaves: {stats.get('leaves', 0)}\n"
            f"Active features: {", ".join(features_active) or "unknown"}\n"
            f"Missing features: {", ".join(features_missing) or "none"}\n\n"
            "Give ONE specific actionable suggestion to improve this server's bot usage. Under 2 sentences."
        )
        suggestion = await _gemini(prompt, max_tokens=100)
        if suggestion:
            self._log_action("suggestion", guild.name, suggestion)

    async def _check_feature_health(self):
        """Check if key features are configured and log warnings."""
        for guild in self.bot.guilds[:5]:
            issues = []
            try:
                wd = json.load(open("welcome_data.json")) if os.path.exists("welcome_data.json") else {}
                gcfg = wd.get(str(guild.id), {})
                if not gcfg.get("welcome_channel"):
                    issues.append("welcome channel not configured")
                if not gcfg.get("goodbye_channel") and not gcfg.get("welcome_channel"):
                    issues.append("goodbye channel not configured")
            except Exception:
                pass
            if issues:
                self._log_action("health_warning", guild.name,
                                 f"Issues: {', '.join(issues)}")

    @self_improve_task.before_loop
    async def before_self_improve(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(60)

    # ── Slash commands ────────────────────────────────────────────────────

    @commands.command(name="ai-status")
    async def ai_status(self, ctx):
        embed = discord.Embed(title="🧠 AI Brain Status", color=0x7c3aed if GEMINI_API_KEY else 0x6b7280)
        embed.add_field(name="Gemini AI", value="✅ Active" if GEMINI_API_KEY else "❌ No API key", inline=True)
        guild_id = str(ctx.guild.id)
        embed.add_field(name="AI Moderation",
                        value="✅ On" if guild_id in self._mod_enabled else "❌ Off", inline=True)
        feedback = self.data.get("reply_feedback", {})
        total_good = sum(r["good"] for g in feedback.values() for r in g)
        total_bad = sum(r["bad"] for g in feedback.values() for r in g)
        personas_improved = len(self.data.get("learned_personas", {}))
        embed.add_field(
            name="🧬 Auto-Learn Stats",
            value=f"👍 Good: **{total_good}** | 👎 Bad: **{total_bad}**\nPersonas evolved: **{personas_improved}/3**",
            inline=False)
        embed.add_field(
            name="⚡ Powers",
            value="• AI Moderation\n• AI Welcome/Goodbye\n• AI Promo Messages\n• Chatbot Persona Evolution\n• Server Health Monitor\n• Self-Improvement (every 6h)",
            inline=False)
        guild_actions = [a for a in self.actions_log
                         if a.get("guild") in (ctx.guild.name, "global")][:8]
        if guild_actions:
            lines = []
            for a in guild_actions:
                ts = a["timestamp"][:16].replace("T", " ")
                lines.append(f"`{ts}` **{a["type"]}**: {a["detail"][:55]}")
            embed.add_field(name="Recent AI Actions", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Recent AI Actions", value="No actions yet.", inline=False)
        embed.set_footer(text="Auto-improves every 6h • React 👍/👎 to chatbot replies to train it")
        await ctx.send(embed=embed)

    @commands.command(name="ai-mod")
    async def ai_mod_toggle(self, ctx):
        guild_id = str(ctx.guild.id)
        if guild_id in self._mod_enabled:
            self._mod_enabled.discard(guild_id)
            status, color = "disabled", discord.Color.red()
        else:
            self._mod_enabled.add(guild_id)
            status, color = "enabled", discord.Color.green()
        self._save_settings()
        embed = discord.Embed(
            title=f"🤖 AI Moderation {status}",
            description=(
                "AI will detect and act on toxic messages.\nActions: warn (6+), timeout (8+), delete (9+)"
                if status == "enabled" else "AI moderation turned off."
            ),
            color=color)
        await ctx.send(embed=embed)

    @commands.command(name="ai-suggest")
    async def ai_suggest(self, ctx):
        if not GEMINI_API_KEY:
            return await ctx.send("❌ GEMINI_API_KEY not set.")
        await ctx.defer()
        guild = ctx.guild
        stats = {}
        if hasattr(self.bot, "_get_live_stats"):
            stats = self.bot._get_live_stats(str(guild.id))
        prompt = (
            "You are an expert Discord community manager. Give 3 specific suggestions.\n"
            f"Server: {guild.name} | Members: {guild.member_count}\n"
            f"Channels: {len(guild.text_channels)} | Roles: {len(guild.roles)}\n"
            f"Messages today: {stats.get('messages', 0)} | Joins: {stats.get('joins', 0)}\n\n"
            "Give 3 numbered suggestions. Be specific and actionable. Each under 2 sentences."
        )
        result = await _gemini(prompt, max_tokens=250)
        if not result:
            return await ctx.send("❌ AI unavailable right now.")
        embed = discord.Embed(title="🧠 AI Server Suggestions", description=result, color=0x7c3aed)
        embed.set_footer(text="Powered by Gemini AI • Auto-improves every 6h")
        await ctx.send(embed=embed)

    @commands.command(name="ai-welcome")
    async def ai_welcome_setup(self, ctx, channel: discord.TextChannel):
        if not GEMINI_API_KEY:
            return await ctx.send("❌ GEMINI_API_KEY not set.")
        # Delegate to Welcome cog
        welcome_cog = self.bot.cogs.get("Welcome")
        if welcome_cog:
            cfg = welcome_cog._guild(ctx.guild.id)
            cfg["welcome_channel"] = str(channel.id)
            welcome_cog._save()
            await ctx.send(
                f"✅ AI welcome enabled in {channel.mention}! "
                f"Every new member gets a unique Gemini-generated welcome 🤖")
        else:
            await ctx.send("❌ Welcome cog not loaded.")


async def setup(bot):
    await bot.add_cog(AIBrain(bot))