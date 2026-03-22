"""
WAN Bot - Translation Cog
React with 🌐 to translate any message to English instantly.
Use /translate for custom language.
"""
import discord
from discord import app_commands
from discord.ext import commands
from deep_translator import GoogleTranslator
import asyncio
import logging
import time
from collections import deque

logger = logging.getLogger('discord_bot.translation')


class TranslationLanguageView(discord.ui.View):
    """Shown after 🌐 reaction — lets user pick a target language."""

    LANGUAGES = [
        ("🇺🇸", "en",  "English"),
        ("🇪🇸", "es",  "Spanish"),
        ("🇫🇷", "fr",  "French"),
        ("🇩🇪", "de",  "German"),
        ("🇯🇵", "ja",  "Japanese"),
        ("🇰🇷", "ko",  "Korean"),
        ("🇷🇺", "ru",  "Russian"),
        ("🇮🇳", "hi",  "Hindi"),
        ("🇧🇷", "pt",  "Portuguese"),
        ("🇨🇳", "zh-CN", "Chinese"),
    ]

    def __init__(self, original_text: str, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.original_text = original_text
        for emoji, code, name in self.LANGUAGES:
            btn = discord.ui.Button(emoji=emoji, label=name,
                                    style=discord.ButtonStyle.secondary, custom_id=code)
            btn.callback = self._make_cb(code, name)
            self.add_item(btn)

    def _make_cb(self, code: str, name: str):
        async def callback(interaction: discord.Interaction):
            await ctx.defer()
            try:
                loop = asyncio.get_event_loop()
                translated = await loop.run_in_executor(
                    None,
                    lambda: GoogleTranslator(source='auto', target=code).translate(self.original_text)
                )
                embed = discord.Embed(
                    title=f"🌐 Translation → {name}",
                    description=translated,
                    color=0x5865f2
                )
                embed.add_field(name="Original", value=self.original_text[:1000], inline=False)
                embed.set_footer(text=f"Translated for {ctx.author.display_name}")
                await ctx.send(embed=embed)
            except Exception as e:
                logger.error(f"Translation error: {e}")
                await ctx.send("❌ Translation failed. Try again later.")
        return callback


class Translation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Simple per-user cooldown (5s)
        self._cooldowns: dict[int, float] = {}

    def _on_cooldown(self, user_id: int) -> bool:
        now = time.time()
        last = self._cooldowns.get(user_id, 0)
        if now - last < 5:
            return True
        self._cooldowns[user_id] = now
        return False

    # ── REACTION HANDLER ─────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Only care about 🌐
        if str(payload.emoji) != "🌐":
            return
        # Ignore bot's own reactions
        if payload.user_id == self.bot.user.id:
            return

        # Per-user cooldown
        if self._on_cooldown(payload.user_id):
            return

        try:
            channel = self.bot.get_channel(payload.channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(payload.channel_id)

            message = await channel.fetch_message(payload.message_id)

            if not message.content or message.author.bot:
                return

            text = message.content.strip()
            if len(text) < 2:
                return

            # Translate to English immediately
            loop = asyncio.get_event_loop()
            translated = await loop.run_in_executor(
                None,
                lambda: GoogleTranslator(source='auto', target='en').translate(text)
            )

            embed = discord.Embed(
                title="🌐 Translation → English",
                description=translated,
                color=0x5865f2
            )
            embed.add_field(name="Original", value=text[:1000], inline=False)
            embed.set_footer(text=f"From #{channel.name} • Pick a language below to retranslate")

            # Also attach a view so they can pick another language
            view = TranslationLanguageView(text)

            # Send privately to the person who reacted — DM first, fallback to temp channel msg
            reactor = payload.member or channel.guild.get_member(payload.user_id)
            if reactor:
                try:
                    await reactor.send(embed=embed, view=view)
                except discord.Forbidden:
                    # DMs closed — send a temporary channel message visible only briefly
                    try:
                        await channel.send(
                            content=f"{reactor.mention} (enable DMs to receive translations privately)",
                            embed=embed,
                            view=view,
                            delete_after=30
                        )
                    except Exception:
                        pass

        except discord.Forbidden:
            logger.debug(f"Missing permissions to send translation in channel {payload.channel_id}")
        except Exception as e:
            logger.error(f"Translation reaction error: {e}", exc_info=True)

    # ── SLASH COMMANDS ────────────────────────────────────────────────────

    @app_commands.command(name="translate", description="Translate text to any language")
    async def translate(self, ctx, text: str, language: str = "en"):
        """Translate text. Language = language code e.g. en, es, fr, de, ja"""
        await ctx.defer()
        try:
            loop = asyncio.get_event_loop()
            translated = await loop.run_in_executor(
                None,
                lambda: GoogleTranslator(source='auto', target=language).translate(text)
            )
            embed = discord.Embed(title=f"🌐 Translation → {language.upper()}",
                                  description=translated, color=0x5865f2)
            embed.add_field(name="Original", value=text[:1000], inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Translate command error: {e}")
            await ctx.send(
                "❌ Translation failed. Check the language code (e.g. `en`, `es`, `fr`, `de`, `ja`, `ko`, `ru`, `hi`, `pt`, `zh-CN`)."
            )

    @commands.command(name="languages")
    async def languages(self, ctx):
        langs = "\n".join(f"{e} **{name}** — `{code}`"
                          for e, code, name in TranslationLanguageView.LANGUAGES)
        embed = discord.Embed(title="🌐 Supported Languages", description=langs, color=0x5865f2)
        embed.set_footer(text="React 🌐 on any message to translate it to English instantly!")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Translation(bot))
