"""
WAN Bot - Welcome/Goodbye System (replaces MEE6/Carl-bot)
Custom welcome & goodbye embeds with variables.
/welcome-set, /goodbye-set, /welcome-test
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging
from datetime import datetime, timezone

logger = logging.getLogger('discord_bot.welcome')
DATA_FILE = 'welcome_data.json'


def _fill(template: str, member: discord.Member) -> str:
    return (template
        .replace('{user}', member.mention)
        .replace('{username}', member.display_name)
        .replace('{server}', member.guild.name)
        .replace('{count}', str(member.guild.member_count))
        .replace('{id}', str(member.id))
    )


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data: dict = self._load()

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
            logger.error(f"Welcome save error: {e}")

    def _guild(self, gid: int) -> dict:
        key = str(gid)
        if key not in self.data:
            self.data[key] = {}
        return self.data[key]

    async def _send_embed(self, member: discord.Member, cfg: dict, event: str):
        ch_id = cfg.get(f'{event}_channel')
        if not ch_id:
            return
        ch = member.guild.get_channel(int(ch_id))
        if not ch:
            return
        title = _fill(cfg.get(f'{event}_title', ''), member)
        desc = _fill(cfg.get(f'{event}_message', ''), member)
        # Support both '#rrggbb' (dashboard color picker) and '0xrrggbb' (slash command)
        raw_color = cfg.get(f'{event}_color', '#57f287' if event == 'welcome' else '#ef4444')
        try:
            s = str(raw_color).strip()
            if s.startswith('#'):
                color = int(s[1:], 16)
            elif s.startswith('0x') or s.startswith('0X'):
                color = int(s, 16)
            else:
                color = int(s, 16)
        except Exception:
            color = 0x57f287 if event == 'welcome' else 0xef4444
        embed = discord.Embed(title=title or None, description=desc, color=color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"{member.guild.name} • {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
        try:
            await ch.send(embed=embed)
        except Exception as e:
            logger.warning(f"Welcome send error: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = self._guild(member.guild.id)
        logger.info(f"Member join: {member} in {member.guild.name} — welcome_channel={cfg.get('welcome_channel')}")
        await self._send_embed(member, cfg, 'welcome')
        # Auto-role on join
        role_id = cfg.get('autorole')
        if role_id:
            role = member.guild.get_role(int(role_id))
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except Exception as e:
                    logger.warning(f"Auto-role error: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        cfg = self._guild(member.guild.id)
        await self._send_embed(member, cfg, 'goodbye')

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Detect role promotions and send congrats message."""
        cfg = self._guild(after.guild.id)
        promo_channel_id = cfg.get('promo_channel')
        promo_msg_template = cfg.get('promo_message', '🎉 Congratulations {user}! You\'ve been promoted to **{role}**! Well deserved! 🎊')
        watched_raw = cfg.get('promo_roles', '')
        if not promo_channel_id or not watched_raw:
            return
        watched = [r.strip().lower() for r in watched_raw.split(',') if r.strip()]
        if not watched:
            return
        new_roles = [r for r in after.roles if r not in before.roles]
        for role in new_roles:
            if role.name.lower() in watched:
                ch = after.guild.get_channel(int(promo_channel_id))
                if not ch:
                    return
                msg = promo_msg_template.replace('{user}', after.mention).replace('{username}', after.display_name).replace('{role}', role.name).replace('{server}', after.guild.name)
                embed = discord.Embed(description=msg, color=0xf59e0b)
                embed.set_thumbnail(url=after.display_avatar.url)
                embed.set_footer(text=f"{after.guild.name} • Promotion")
                try:
                    await ch.send(embed=embed)
                except Exception as e:
                    logger.warning(f"Promo congrats send error: {e}")
                break  # only one congrats per update

    @app_commands.command(name="welcome-set", description="👋 Configure welcome messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_set(self, interaction: discord.Interaction,
                          channel: discord.TextChannel,
                          message: str = "Welcome {user} to **{server}**! You are member #{count}.",
                          title: str = "👋 Welcome!",
                          color: str = "0x57f287"):
        cfg = self._guild(interaction.guild.id)
        cfg.update({'welcome_channel': channel.id, 'welcome_message': message,
                    'welcome_title': title, 'welcome_color': color})
        self._save()
        await interaction.response.send_message(
            f"✅ Welcome messages → {channel.mention}\n"
            f"Variables: `{{user}}` `{{username}}` `{{server}}` `{{count}}` `{{id}}`",
            ephemeral=True)

    @app_commands.command(name="goodbye-set", description="👋 Configure goodbye messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def goodbye_set(self, interaction: discord.Interaction,
                          channel: discord.TextChannel,
                          message: str = "**{username}** has left **{server}**. We now have {count} members.",
                          title: str = "👋 Goodbye!"):
        cfg = self._guild(interaction.guild.id)
        cfg.update({'goodbye_channel': channel.id, 'goodbye_message': message, 'goodbye_title': title})
        self._save()
        await interaction.response.send_message(f"✅ Goodbye messages → {channel.mention}", ephemeral=True)

    @app_commands.command(name="autorole", description="👋 Set a role to auto-assign when members join")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole(self, interaction: discord.Interaction, role: discord.Role = None):
        cfg = self._guild(interaction.guild.id)
        if role:
            cfg['autorole'] = role.id
            self._save()
            await interaction.response.send_message(f"✅ New members will get **{role.name}** on join.", ephemeral=True)
        else:
            cfg.pop('autorole', None)
            self._save()
            await interaction.response.send_message("✅ Auto-role disabled.", ephemeral=True)

    @app_commands.command(name="welcome-test", description="👋 Test your welcome message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_test(self, interaction: discord.Interaction):
        cfg = self._guild(interaction.guild.id)
        if not cfg.get('welcome_channel'):
            return await interaction.response.send_message("❌ No welcome channel set. Use `/welcome-set` first.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        await self._send_embed(interaction.user, cfg, 'welcome')
        await interaction.followup.send("✅ Test welcome sent!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
