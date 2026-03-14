"""
WAN Bot - Translation Cog
Translate messages via deep-translator (no API key needed).
Features: /translate command with autocomplete, right-click context menu,
          🌐 reaction handler (replies in-channel, not DM), 30+ languages.
"""
import discord
from discord import app_commands
from discord.ext import commands
from deep_translator import GoogleTranslator
import time
import logging
import asyncio
from collections import deque

logger = logging.getLogger('discord_bot.translation')

# ── Language registry ──────────────────────────────────────────────────────
LANGUAGES = {
    "English":    "en",
    "Hindi":      "hi",
    "Spanish":    "es",
    "French":     "fr",
    "German":     "de",
    "Japanese":   "ja",
    "Korean":     "ko",
    "Chinese (Simplified)":  "zh-CN",
    "Chinese (Traditional)": "zh-TW",
    "Russian":    "ru",
    "Arabic":     "ar",
    "Portuguese": "pt",
    "Italian":    "it",
    "Turkish":    "tr",
    "Dutch":      "nl",
    "Polish":     "pl",
    "Swedish":    "sv",
    "Norwegian":  "no",
    "Danish":     "da",
    "Finnish":    "fi",
    "Greek":      "el",
    "Hebrew":     "iw",
    "Thai":       "th",
    "Vietnamese": "vi",
    "Indonesian": "id",
    "Malay":      "ms",
    "Filipino":   "tl",
    "Bengali":    "bn",
    "Urdu":       "ur",
    "Punjabi":    "pa",
    "Tamil":      "ta",
    "Telugu":     "te",
    "Marathi":    "mr",
    "Gujarati":   "gu",
    "Ukrainian":  "uk",
    "Romanian":   "ro",
    "Hungarian":  "hu",
    "Czech":      "cs",
    "Slovak":     "sk",
    "Croatian":   "hr",
    "Catalan":    "ca",
    "Swahili":    "sw",
}

# Quick-pick buttons shown in the reaction view (most common)
QUICK_LANGS = [
    ("🇺🇸", "en",    "English"),
    ("🇮🇳", "hi",    "Hindi"),
    ("🇪🇸", "es",    "Spanish"),
    ("🇫🇷", "fr",    "French"),
    ("🇩🇪", "de",    "German"),
    ("🇯🇵", "ja",    "Japanese"),
    ("🇰🇷", "ko",    "Korean"),
    ("🇨🇳", "zh-CN", "Chinese"),
    ("🇷🇺", "ru",    "Russian"),
    ("🇸🇦", "ar",    "Arabic"),
]


async def _do_translate(text: str, target: str) -> str:
    """Run translation in executor so it doesn't block the event loop."""
    loop = asyncio.get_event_loop()
    translator = GoogleTranslator(source='auto', target=target)
    return await loop.run_in_executor(None, translator.translate, text)


def _translation_embed(translated: str, original: str, target_name: str, requester: discord.User | discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title=f"🌐 Translation → {target_name}",
        description=translated,
        color=0x5865f2,
    )
    if len(original) <= 1024:
        embed.add_field(name="Original", value=original, inline=False)
    else:
        embed.add_field(name="Original (truncated)", value=original[:1021] + "...", inline=False)
    embed.set_footer(text=f"Requested by {requester.display_name} • Powered by Google Translate")
    return embed


class QuickTranslateView(discord.ui.View):
    """Shown when a user reacts 🌐 — quick-pick buttons + a custom language select."""

    def __init__(self, message: discord.Message, cog: "Translation"):
        super().__init__(timeout=120)
        self.message = message
        self.cog = cog

        # Add flag buttons (2 rows of 5)
        for i, (emoji, code, name) in enumerate(QUICK_LANGS):
            btn = discord.ui.Button(
                emoji=emoji,
                label=name,
                style=discord.ButtonStyle.secondary,
                row=i // 5,
            )
            btn.callback = self._make_btn_callback(code, name)
            self.add_item(btn)

        # Custom language select on row 2
        select = discord.ui.Select(
            placeholder="More languages…",
            options=[
                discord.SelectOption(label=name, value=code)
                for name, code in list(LANGUAGES.items())[:25]   # Discord limit: 25
            ],
            row=2,
        )
        select.callback = self._select_callback
        self.add_item(select)

    def _make_btn_callback(self, code: str, name: str):
        async def callback(interaction: discord.Interaction):
            if not await self.cog._check_rate_limit(interaction.user.id):
                return await interaction.response.send_message(
                    "⏳ Please wait a few seconds before translating again.", ephemeral=True
                )
            await interaction.response.defer(ephemeral=True)
            try:
                translated = await _do_translate(self.message.content, code)
                embed = _translation_embed(translated, self.message.content, name, interaction.user)
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as e:
                logger.error(f"Translation error: {e}")
                await interaction.followup.send("❌ Translation failed. Try again later.", ephemeral=True)
        return callback

    async def _select_callback(self, interaction: discord.Interaction):
        code = interaction.data['values'][0]
        name = next((n for n, c in LANGUAGES.items() if c == code), code)
        if not await self.cog._check_rate_limit(interaction.user.id):
            return await interaction.response.send_message(
                "⏳ Please wait a few seconds before translating again.", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        try:
            translated = await _do_translate(self.message.content, code)
            embed = _translation_embed(translated, self.message.content, name, interaction.user)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Translation error: {e}")
            await interaction.followup.send("❌ Translation failed. Try again later.", ephemeral=True)


class Translation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._user_cooldowns: dict[int, float] = {}
        self._api_calls: deque = deque(maxlen=120)
        self._reaction_cooldown: dict[int, float] = {}   # per-channel

    # ── Rate limiting ──────────────────────────────────────────────────────

    async def _check_rate_limit(self, user_id: int, cooldown: float = 5.0) -> bool:
        now = time.time()
        last = self._user_cooldowns.get(user_id, 0)
        if now - last < cooldown:
            return False
        self._user_cooldowns[user_id] = now
        # Prune old entries
        cutoff = now - 120
        self._user_cooldowns = {k: v for k, v in self._user_cooldowns.items() if v > cutoff}
        return True

    async def _check_api_limit(self) -> bool:
        now = time.time()
        while self._api_calls and now - self._api_calls[0] > 60:
            self._api_calls.popleft()
        if len(self._api_calls) >= 60:
            return False
        self._api_calls.append(now)
        return True

    # ── Autocomplete ───────────────────────────────────────────────────────

    async def _lang_autocomplete(self, interaction: discord.Interaction, current: str):
        current_lower = current.lower()
        matches = [
            app_commands.Choice(name=name, value=code)
            for name, code in LANGUAGES.items()
            if current_lower in name.lower() or current_lower in code.lower()
        ]
        return matches[:25]

    # ── /translate ─────────────────────────────────────────────────────────

    @app_commands.command(name="translate", description="🌐 Translate text to another language")
    @app_commands.describe(
        text="The text to translate",
        language="Target language (start typing to search)",
    )
    @app_commands.autocomplete(language=_lang_autocomplete)
    async def translate(self, interaction: discord.Interaction, text: str, language: str):
        if not await self._check_rate_limit(interaction.user.id):
            return await interaction.response.send_message(
                "⏳ Please wait a few seconds before translating again.", ephemeral=True
            )
        if not await self._check_api_limit():
            return await interaction.response.send_message(
                "⚠️ Translation service is busy. Try again in a moment.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)
        try:
            translated = await _do_translate(text, language)
            lang_name = next((n for n, c in LANGUAGES.items() if c == language), language)
            embed = _translation_embed(translated, text, lang_name, interaction.user)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Translate command error: {e}")
            await interaction.followup.send(
                "❌ Could not translate. Check the language and try again.", ephemeral=True
            )

    # ── Context menu: right-click a message → Translate ───────────────────

    @app_commands.context_menu(name="Translate Message")
    async def translate_context(self, interaction: discord.Interaction, message: discord.Message):
        if not message.content:
            return await interaction.response.send_message(
                "❌ This message has no text to translate.", ephemeral=True
            )
        if not await self._check_rate_limit(interaction.user.id):
            return await interaction.response.send_message(
                "⏳ Please wait a few seconds before translating again.", ephemeral=True
            )
        view = QuickTranslateView(message, self)
        await interaction.response.send_message(
            "🌐 Choose a language to translate to:", view=view, ephemeral=True
        )

    # ── 🌐 reaction handler ────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != "🌐":
            return
        if payload.user_id == self.bot.user.id:
            return

        # Per-channel cooldown to prevent spam
        now = time.time()
        ch_id = payload.channel_id
        if now - self._reaction_cooldown.get(ch_id, 0) < 3:
            return
        self._reaction_cooldown[ch_id] = now

        try:
            channel = self.bot.get_channel(ch_id)
            if not channel:
                return
            message = await channel.fetch_message(payload.message_id)
            if not message.content or message.author.bot:
                return

            user = channel.guild.get_member(payload.user_id) if channel.guild else None
            if not user:
                return

            view = QuickTranslateView(message, self)
            # Reply ephemerally in the channel — no DM needed
            await channel.send(
                content=f"{user.mention} Choose a language:",
                view=view,
                delete_after=120,
            )
        except Exception as e:
            logger.debug(f"Reaction translation error: {e}")

    # ── on_message: add 🌐 reaction to longer messages ────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        # Only react to messages that look like they might need translation
        # (longer than 40 chars, not a command, not a URL)
        content = message.content
        if (len(content) < 40
                or content.startswith(('/', '!', 'http://', 'https://'))
                or not content.strip()):
            return

        # Per-guild cooldown — don't spam reactions
        now = time.time()
        gid = message.guild.id
        if now - self._reaction_cooldown.get(gid, 0) < 8:
            return
        self._reaction_cooldown[gid] = now

        try:
            await message.add_reaction("🌐")
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(Translation(bot))
