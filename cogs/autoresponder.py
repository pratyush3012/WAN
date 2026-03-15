"""
WAN Bot - Auto Responder (replaces Dyno/YAGPDB)
Bot replies to keyword triggers automatically.
/ar-add, /ar-remove, /ar-list
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging, re

logger = logging.getLogger('discord_bot.autoresponder')
DATA_FILE = 'autoresponder_data.json'


class AutoResponder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data: dict = self._load()   # {guild_id: [{trigger, response, exact, enabled}]}

    def _load(self) -> dict:
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save(self):
        try:
            with open(DATA_FILE, 'w') as f:
                json.dump(self.data, f)
        except Exception as e:
            logger.error(f"AR save error: {e}")

    def _guild(self, gid: int) -> list:
        key = str(gid)
        if key not in self.data:
            self.data[key] = []
        return self.data[key]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        rules = self._guild(message.guild.id)
        content = message.content.lower()
        for rule in rules:
            if not rule.get('enabled', True):
                continue
            trigger = rule['trigger'].lower()
            if rule.get('exact'):
                match = content == trigger
            else:
                match = trigger in content
            if match:
                response = rule['response']
                # Replace variables
                response = response.replace('{user}', message.author.mention)
                response = response.replace('{username}', message.author.display_name)
                response = response.replace('{server}', message.guild.name)
                try:
                    await message.channel.send(response)
                except Exception:
                    pass
                break  # only first match

    @app_commands.command(name="ar-add", description="🤖 Add an auto-response trigger")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def ar_add(self, interaction: discord.Interaction,
                     trigger: str, response: str,
                     exact_match: bool = False):
        rules = self._guild(interaction.guild.id)
        # Check for duplicate
        if any(r['trigger'].lower() == trigger.lower() for r in rules):
            return await interaction.response.send_message(
                f"❌ Trigger `{trigger}` already exists. Remove it first with `/ar-remove`.", ephemeral=True)
        rules.append({'trigger': trigger, 'response': response, 'exact': exact_match, 'enabled': True})
        self._save()
        await interaction.response.send_message(
            f"✅ Auto-response added!\n**Trigger:** `{trigger}`\n**Response:** {response}\n**Exact match:** {exact_match}",
            ephemeral=True)

    @app_commands.command(name="ar-remove", description="🤖 Remove an auto-response trigger")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def ar_remove(self, interaction: discord.Interaction, trigger: str):
        rules = self._guild(interaction.guild.id)
        before = len(rules)
        self.data[str(interaction.guild.id)] = [r for r in rules if r['trigger'].lower() != trigger.lower()]
        self._save()
        if len(self.data[str(interaction.guild.id)]) < before:
            await interaction.response.send_message(f"✅ Removed trigger `{trigger}`.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Trigger `{trigger}` not found.", ephemeral=True)

    @app_commands.command(name="ar-list", description="🤖 List all auto-response triggers")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def ar_list(self, interaction: discord.Interaction):
        rules = self._guild(interaction.guild.id)
        if not rules:
            return await interaction.response.send_message("No auto-responses set up.", ephemeral=True)
        lines = [f"`{r['trigger']}` → {r['response'][:50]}{'...' if len(r['response'])>50 else ''} {'(exact)' if r.get('exact') else ''}"
                 for r in rules]
        embed = discord.Embed(title="🤖 Auto Responses", description="\n".join(lines), color=0x06b6d4)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoResponder(bot))
