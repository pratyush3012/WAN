"""
WAN Bot - Translation Cog
React 🌐 on ANY message → translates to English + language picker buttons.
"""
import discord
from discord import app_commands
from discord.ext import commands
from deep_translator import GoogleTranslator
import asyncio
import logging
import time

logger = logging.getLogger('discord_bot.translation')


class LangView(discord.ui.View):
    LANGS = [
        ("🇺🇸","en","English"),("🇪🇸","es","Spanish"),("🇫🇷","fr","French"),
        ("🇩🇪","de","German"),("🇯🇵","ja","Japanese"),("🇰🇷","ko","Korean"),
        ("🇷🇺","ru","Russian"),("🇮🇳","hi","Hindi"),("🇧🇷","pt","Portuguese"),
        ("🇨🇳","zh-CN","Chinese"),
    ]
    def __init__(self, text: str):
        super().__init__(timeout=120)
        self.text = text
        for emoji, code, name in self.LANGS:
            btn = discord.ui.Button(emoji=emoji, label=name,
                                    style=discord.ButtonStyle.secondary)
            btn.callback = self._cb(code, name)
            self.add_item(btn)

    def _cb(self, code, name):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            try:
                translated = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: GoogleTranslator(source='auto', target=code).translate(self.text)
                )
                embed = discord.Embed(title=f"🌐 → {name}", description=translated, color=0x5865f2)
                embed.add_field(name="Original", value=self.text[:900], inline=False)
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"❌ Translation failed: {e}", ephemeral=True)
        return callback


class Translation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cd: dict[int, float] = {}

    def _check_cd(self, uid: int) -> bool:
        now = time.time()
        if now - self._cd.get(uid, 0) < 5:
            return True
        self._cd[uid] = now
        return False

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != "🌐":
            return
        if payload.user_id == self.bot.user.id:
            return
        if self._check_cd(payload.user_id):
            return
        try:
            channel = self.bot.get_channel(payload.channel_id) or \
                      await self.bot.fetch_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)

            # Get text — from content or embeds
            text = message.content.strip()
            if not text and message.embeds:
                text = (message.embeds[0].description or "").strip()
            if not text or len(text) < 2:
                return

            translated = await asyncio.get_event_loop().run_in_executor(
                None, lambda: GoogleTranslator(source='auto', target='en').translate(text)
            )

            embed = discord.Embed(title="🌐 Translation → English",
                                  description=translated, color=0x5865f2)
            embed.add_field(name="Original", value=text[:900], inline=False)
            who = payload.member.display_name if payload.member else "Someone"
            embed.set_footer(text=f"Requested by {who} • Pick another language below")

            await message.reply(embed=embed, view=LangView(text), mention_author=False)

        except discord.Forbidden:
            logger.debug(f"No permission to send translation in {payload.channel_id}")
        except Exception as e:
            logger.error(f"Translation reaction error: {e}", exc_info=True)

    @app_commands.command(name="translate", description="🌐 Translate text to any language")
    async def translate(self, interaction: discord.Interaction, text: str, language: str = "en"):
        await interaction.response.defer(ephemeral=True)
        try:
            translated = await asyncio.get_event_loop().run_in_executor(
                None, lambda: GoogleTranslator(source='auto', target=language).translate(text)
            )
            embed = discord.Embed(title=f"🌐 → {language.upper()}",
                                  description=translated, color=0x5865f2)
            embed.add_field(name="Original", value=text[:900], inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed: {e}", ephemeral=True)

    @app_commands.command(name="languages", description="🌐 Show supported translation languages")
    async def languages(self, interaction: discord.Interaction):
        lines = "\n".join(f"{e} **{n}** — `{c}`" for e, c, n in LangView.LANGS)
        embed = discord.Embed(title="🌐 Supported Languages", description=lines, color=0x5865f2)
        embed.set_footer(text="React 🌐 on any message to translate it instantly!")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Translation(bot))
