"""
WAN Bot - AI Coder
Gemini analyzes every cog daily and:
- Generates improvement suggestions for each feature
- Writes better message templates (welcome, level-up, etc.)
- Improves fallback reply pools
- Logs all improvements with timestamps
- Exposes improvement history to the dashboard
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json, os, logging, asyncio, time
import urllib.request
from datetime import datetime, timezone

logger = logging.getLogger("discord_bot.ai_coder")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(DATA_DIR, "ai_coder_log.json")

# Features the AI Coder monitors and improves
FEATURE_SPECS = {
    "welcome": {
        "name": "Welcome System",
        "desc": "Welcome/goodbye messages for new members",
        "data_file": "welcome_data.json",
        "improve_key": "welcome_messages",
    },
    "leveling": {
        "name": "XP & Leveling",
        "desc": "Level-up announcements and XP system",
        "data_file": "leveling_data.json",
        "improve_key": "levelup_messages",
    },
    "chatbot": {
        "name": "AI Chatbot",
        "desc": "Flirty/chaotic chatbot replies",
        "data_file": "chatbot_data.json",
        "improve_key": "chatbot_personas",
    },
    "moderation": {
        "name": "Moderation",
        "desc": "Auto-moderation and manual mod actions",
        "data_file": None,
        "improve_key": "mod_messages",
    },
    "tickets": {
        "name": "Support Tickets",
        "desc": "Ticket system with AI auto-response",
        "data_file": "tickets.json",
        "improve_key": "ticket_messages",
    },
}


async def _gemini(prompt: str, max_tokens: int = 300, temperature: float = 0.8) -> str | None:
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
            with urllib.request.urlopen(req, timeout=12) as resp:
                return json.loads(resp.read())
        data = await loop.run_in_executor(None, _call)
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.warning(f"AI Coder Gemini error: {e}")
        return None


def _load_log() -> dict:
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {"improvements": [], "suggestions": {}, "generated": {}}


def _save_log(data: dict):
    try:
        with open(LOG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"AI Coder log save error: {e}")


class AICoder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log = _load_log()
        self._running = False
        if GEMINI_API_KEY:
            self.daily_improve.start()
            logger.info("AI Coder loaded — daily improvement cycle active")
        else:
            logger.warning("AI Coder loaded — no GEMINI_API_KEY, improvements disabled")

    def cog_unload(self):
        if self.daily_improve.is_running():
            self.daily_improve.cancel()

    def _record(self, feature: str, improvement_type: str, content: str):
        entry = {
            "feature": feature,
            "type": improvement_type,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.log.setdefault("improvements", []).insert(0, entry)
        self.log["improvements"] = self.log["improvements"][:200]
        _save_log(self.log)

    # ── Daily improvement cycle ───────────────────────────────────────────────

    @tasks.loop(hours=24)
    async def daily_improve(self):
        """Every 24h: Gemini analyzes and improves every feature."""
        await self.bot.wait_until_ready()
        if self._running:
            return
        self._running = True
        logger.info("AI Coder: starting daily improvement cycle")
        try:
            await self._improve_welcome_messages()
            await asyncio.sleep(8)
            await self._improve_levelup_messages()
            await asyncio.sleep(8)
            await self._improve_chatbot_fallbacks()
            await asyncio.sleep(8)
            await self._improve_ticket_responses()
            await asyncio.sleep(8)
            await self._generate_feature_suggestions()
        except Exception as e:
            logger.error(f"AI Coder daily cycle error: {e}")
        finally:
            self._running = False
        logger.info("AI Coder: daily improvement cycle complete")

    @daily_improve.before_loop
    async def before_daily(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(120)  # wait 2 min after startup

    # ── Feature improvers ─────────────────────────────────────────────────────

    async def _improve_welcome_messages(self):
        """Generate 5 new unique welcome messages and store them."""
        prompt = (
            "You are improving a Discord bot's welcome message system.\n"
            "Generate 5 unique, fun, engaging welcome messages for new Discord members.\n"
            "Rules:\n"
            "- Each message 1-2 sentences\n"
            "- Use emojis\n"
            "- Use {user} for mention, {server} for server name, {count} for member count\n"
            "- Mix styles: hype, warm, funny, flirty, chaotic\n"
            "- Make each one completely different\n"
            "- No generic 'Welcome to the server!' type messages\n\n"
            "Return as JSON array: [\"msg1\", \"msg2\", \"msg3\", \"msg4\", \"msg5\"]"
        )
        result = await _gemini(prompt, max_tokens=400)
        if not result:
            return
        try:
            import re
            match = re.search(r'\[.*\]', result, re.DOTALL)
            if match:
                new_msgs = json.loads(match.group())
                if isinstance(new_msgs, list) and len(new_msgs) >= 3:
                    self.log.setdefault("generated", {})["welcome_messages"] = {
                        "messages": new_msgs,
                        "updated": datetime.now(timezone.utc).isoformat()
                    }
                    _save_log(self.log)
                    self._record("welcome", "new_messages",
                                 f"Generated {len(new_msgs)} new welcome messages")
                    logger.info(f"AI Coder: generated {len(new_msgs)} new welcome messages")
        except Exception as e:
            logger.warning(f"AI Coder welcome parse error: {e}")

    async def _improve_levelup_messages(self):
        """Generate better level-up announcement messages."""
        prompt = (
            "You are improving a Discord bot's level-up announcement system.\n"
            "Generate 8 unique, hype level-up messages for when members gain XP levels.\n"
            "Rules:\n"
            "- Each message 1-2 sentences\n"
            "- Use emojis\n"
            "- Use {user} for mention, {level} for the new level\n"
            "- Mix styles: hype, funny, gaming references, motivational\n"
            "- Make each one completely different and exciting\n\n"
            "Return as JSON array: [\"msg1\", \"msg2\", ...]"
        )
        result = await _gemini(prompt, max_tokens=500)
        if not result:
            return
        try:
            import re
            match = re.search(r'\[.*\]', result, re.DOTALL)
            if match:
                new_msgs = json.loads(match.group())
                if isinstance(new_msgs, list) and len(new_msgs) >= 4:
                    self.log.setdefault("generated", {})["levelup_messages"] = {
                        "messages": new_msgs,
                        "updated": datetime.now(timezone.utc).isoformat()
                    }
                    _save_log(self.log)
                    self._record("leveling", "new_messages",
                                 f"Generated {len(new_msgs)} new level-up messages")
        except Exception as e:
            logger.warning(f"AI Coder levelup parse error: {e}")

    async def _improve_chatbot_fallbacks(self):
        """Generate new chatbot fallback replies for each gender."""
        for gender in ("female", "male", "neutral"):
            gender_ctx = {
                "female": "flirty, suggestive, double meanings, obsessed with her, call her queen/baby",
                "male": "savage bro energy, roast him, dirty jokes, hype him up",
                "neutral": "chaotic, unpredictable, funny, slightly dirty-minded",
            }[gender]
            prompt = (
                f"Generate 10 unique Discord chatbot replies for gender={gender}.\n"
                f"Style: {gender_ctx}\n"
                "Rules:\n"
                "- 1-2 sentences each\n"
                "- Use emojis\n"
                "- NEVER be generic or boring\n"
                "- Each must be completely different\n"
                "- Mix in Hindi/Urdu shayari in 2-3 of them\n"
                "- Be unhinged, chaotic, entertaining\n\n"
                "Return as JSON array: [\"reply1\", \"reply2\", ...]"
            )
            result = await _gemini(prompt, max_tokens=600)
            if not result:
                continue
            try:
                import re
                match = re.search(r'\[.*\]', result, re.DOTALL)
                if match:
                    new_replies = json.loads(match.group())
                    if isinstance(new_replies, list) and len(new_replies) >= 5:
                        key = f"chatbot_fallbacks_{gender}"
                        self.log.setdefault("generated", {})[key] = {
                            "replies": new_replies,
                            "updated": datetime.now(timezone.utc).isoformat()
                        }
                        _save_log(self.log)
                        self._record("chatbot", "new_fallbacks",
                                     f"Generated {len(new_replies)} new {gender} fallback replies")
            except Exception as e:
                logger.warning(f"AI Coder chatbot fallback parse error ({gender}): {e}")
            await asyncio.sleep(5)

    async def _improve_ticket_responses(self):
        """Generate better auto-response messages for tickets."""
        prompt = (
            "Generate 5 unique auto-response messages for a Discord support ticket system.\n"
            "These are sent when a ticket is opened, before staff responds.\n"
            "Rules:\n"
            "- Professional but friendly\n"
            "- Use emojis\n"
            "- Use {user} for mention\n"
            "- Reassure them help is coming\n"
            "- Each message different tone: formal, casual, hype, warm, quick\n\n"
            "Return as JSON array: [\"msg1\", \"msg2\", \"msg3\", \"msg4\", \"msg5\"]"
        )
        result = await _gemini(prompt, max_tokens=400)
        if not result:
            return
        try:
            import re
            match = re.search(r'\[.*\]', result, re.DOTALL)
            if match:
                new_msgs = json.loads(match.group())
                if isinstance(new_msgs, list) and len(new_msgs) >= 3:
                    self.log.setdefault("generated", {})["ticket_responses"] = {
                        "messages": new_msgs,
                        "updated": datetime.now(timezone.utc).isoformat()
                    }
                    _save_log(self.log)
                    self._record("tickets", "new_responses",
                                 f"Generated {len(new_msgs)} new ticket auto-responses")
        except Exception as e:
            logger.warning(f"AI Coder ticket parse error: {e}")

    async def _generate_feature_suggestions(self):
        """Ask Gemini what features to add/improve next."""
        cog_list = list(self.bot.cogs.keys())
        prompt = (
            f"You are an AI assistant for a Discord bot called WAN Bot.\n"
            f"Current features (cogs): {', '.join(cog_list)}\n\n"
            "Analyze this bot and suggest 5 specific improvements or new features.\n"
            "Focus on: engagement, automation, AI integration, user experience.\n"
            "Be specific and actionable. Each suggestion under 2 sentences.\n\n"
            "Return as JSON array of objects: "
            '[{"feature": "name", "suggestion": "what to do", "priority": "high|medium|low"}]'
        )
        result = await _gemini(prompt, max_tokens=500)
        if not result:
            return
        try:
            import re
            match = re.search(r'\[.*\]', result, re.DOTALL)
            if match:
                suggestions = json.loads(match.group())
                if isinstance(suggestions, list):
                    self.log["suggestions"] = {
                        "items": suggestions,
                        "updated": datetime.now(timezone.utc).isoformat()
                    }
                    _save_log(self.log)
                    self._record("system", "feature_suggestions",
                                 f"Generated {len(suggestions)} feature improvement suggestions")
        except Exception as e:
            logger.warning(f"AI Coder suggestions parse error: {e}")

    # ── Public API for dashboard ──────────────────────────────────────────────

    def get_status(self) -> dict:
        """Return current AI Coder status for dashboard."""
        improvements = self.log.get("improvements", [])
        generated = self.log.get("generated", {})
        suggestions = self.log.get("suggestions", {})
        return {
            "active": bool(GEMINI_API_KEY),
            "running": self._running,
            "total_improvements": len(improvements),
            "last_run": improvements[0]["timestamp"] if improvements else None,
            "recent_improvements": improvements[:20],
            "suggestions": suggestions.get("items", []),
            "suggestions_updated": suggestions.get("updated"),
            "generated_features": list(generated.keys()),
            "generated": {k: v.get("updated") for k, v in generated.items()},
        }

    def get_generated(self, key: str) -> list:
        """Get generated content for a specific feature."""
        generated = self.log.get("generated", {})
        item = generated.get(key, {})
        return item.get("messages") or item.get("replies") or []

    async def run_cycle_now(self) -> str:
        """Trigger an immediate improvement cycle (called from dashboard)."""
        if self._running:
            return "Already running"
        if not GEMINI_API_KEY:
            return "No GEMINI_API_KEY configured"
        asyncio.create_task(self._run_full_cycle())
        return "Started"

    async def _run_full_cycle(self):
        if self._running:
            return
        self._running = True
        try:
            await self._improve_welcome_messages()
            await asyncio.sleep(5)
            await self._improve_levelup_messages()
            await asyncio.sleep(5)
            await self._improve_chatbot_fallbacks()
            await asyncio.sleep(5)
            await self._improve_ticket_responses()
            await asyncio.sleep(5)
            await self._generate_feature_suggestions()
        except Exception as e:
            logger.error(f"AI Coder manual cycle error: {e}")
        finally:
            self._running = False

    # ── Slash commands ────────────────────────────────────────────────────────

    @app_commands.command(name="ai-coder-status", description="View AI Coder improvement history")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ai_coder_status(self, interaction: discord.Interaction):
        status = self.get_status()
        embed = discord.Embed(
            title="🤖 AI Coder Status",
            color=0x7c3aed if status["active"] else 0x6b7280
        )
        embed.add_field(name="Status",
                        value="✅ Active" if status["active"] else "❌ No API key", inline=True)
        embed.add_field(name="Running",
                        value="🔄 Yes" if status["running"] else "💤 Idle", inline=True)
        embed.add_field(name="Total Improvements",
                        value=str(status["total_improvements"]), inline=True)
        if status["last_run"]:
            embed.add_field(name="Last Run",
                            value=status["last_run"][:16].replace("T", " "), inline=True)
        if status["generated_features"]:
            embed.add_field(name="Generated Content",
                            value="\n".join(f"• {k}" for k in status["generated_features"]),
                            inline=False)
        recent = status["recent_improvements"][:5]
        if recent:
            lines = [f"`{r['timestamp'][:16].replace('T',' ')}` **{r['feature']}**: {r['content'][:50]}"
                     for r in recent]
            embed.add_field(name="Recent Improvements", value="\n".join(lines), inline=False)
        embed.set_footer(text="Runs every 24h • Use /ai-coder-run to trigger now")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ai-coder-run", description="Trigger an AI improvement cycle now")
    @app_commands.checks.has_permissions(administrator=True)
    async def ai_coder_run(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        result = await self.run_cycle_now()
        if result == "Started":
            await interaction.followup.send(
                "🤖 AI Coder improvement cycle started! Check `/ai-coder-status` in a few minutes.",
                ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ {result}", ephemeral=True)

    @app_commands.command(name="ai-coder-suggestions", description="View AI suggestions for bot improvements")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ai_coder_suggestions(self, interaction: discord.Interaction):
        suggestions = self.log.get("suggestions", {}).get("items", [])
        if not suggestions:
            return await interaction.response.send_message(
                "No suggestions yet. Run `/ai-coder-run` to generate some.", ephemeral=True)
        embed = discord.Embed(title="💡 AI Improvement Suggestions", color=0xf59e0b)
        for s in suggestions[:8]:
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                s.get("priority", "medium"), "⚪")
            embed.add_field(
                name=f"{priority_emoji} {s.get('feature', 'Unknown')}",
                value=s.get("suggestion", "")[:200],
                inline=False
            )
        updated = self.log.get("suggestions", {}).get("updated", "")
        if updated:
            embed.set_footer(text=f"Generated: {updated[:16].replace('T', ' ')}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AICoder(bot))
