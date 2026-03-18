"""
JoinLeave — join DM, welcome DM, role persistence on rejoin, join/leave logging
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging
from datetime import datetime, timezone

logger = logging.getLogger('discord_bot.joinleave')
JL_FILE = 'joinleave.json'
ROLES_FILE = 'role_persistence.json'


def _load():
    if os.path.exists(JL_FILE):
        try:
            with open(JL_FILE) as f: return json.load(f)
        except: pass
    return {}

def _save(d):
    with open(JL_FILE, 'w') as f: json.dump(d, f, indent=2)

def _load_roles():
    if os.path.exists(ROLES_FILE):
        try:
            with open(ROLES_FILE) as f: return json.load(f)
        except: pass
    return {}

def _save_roles(d):
    with open(ROLES_FILE, 'w') as f: json.dump(d, f, indent=2)

def _fill(text: str, member: discord.Member) -> str:
    return (text
        .replace('{user}', member.mention)
        .replace('{username}', str(member))
        .replace('{displayname}', member.display_name)
        .replace('{server}', member.guild.name)
        .replace('{count}', str(member.guild.member_count))
        .replace('{id}', str(member.id))
    )


class JoinLeave(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        data = _load()
        cfg = data.get(str(member.guild.id), {})

        # Join DM
        if cfg.get('join_dm_enabled') and cfg.get('join_dm_message'):
            try:
                embed = discord.Embed(
                    description=_fill(cfg['join_dm_message'], member),
                    color=int(cfg.get('join_dm_color', '0x5865f2'), 16)
                )
                if cfg.get('join_dm_title'):
                    embed.title = _fill(cfg['join_dm_title'], member)
                embed.set_thumbnail(url=member.guild.icon.url if member.guild.icon else None)
                await member.send(embed=embed)
            except Exception as e:
                logger.debug(f'Join DM failed for {member}: {e}')

        # Role persistence — restore saved roles
        if cfg.get('role_persistence'):
            roles_data = _load_roles()
            saved = roles_data.get(str(member.guild.id), {}).get(str(member.id), [])
            if saved:
                roles_to_add = []
                for rid in saved:
                    role = member.guild.get_role(int(rid))
                    if role and role < member.guild.me.top_role:
                        roles_to_add.append(role)
                if roles_to_add:
                    try:
                        await member.add_roles(*roles_to_add, reason='Role persistence: restored on rejoin')
                    except Exception as e:
                        logger.warning(f'Role persistence failed for {member}: {e}')

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        data = _load()
        cfg = data.get(str(member.guild.id), {})

        # Save roles for persistence
        if cfg.get('role_persistence'):
            roles_data = _load_roles()
            role_ids = [str(r.id) for r in member.roles
                        if r.name != '@everyone' and not r.managed]
            roles_data.setdefault(str(member.guild.id), {})[str(member.id)] = role_ids
            _save_roles(roles_data)

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name='join-dm-set', description='Set a DM message sent to new members on join')
    @app_commands.describe(
        message='Message content (use {user} {username} {server} {count})',
        title='Embed title (optional)',
        enabled='Enable or disable join DMs'
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def join_dm_set(self, interaction: discord.Interaction,
                          message: str, title: str = '', enabled: bool = True):
        data = _load()
        cfg = data.setdefault(str(interaction.guild.id), {})
        cfg['join_dm_enabled'] = enabled
        cfg['join_dm_message'] = message
        cfg['join_dm_title'] = title
        _save(data)
        state = 'enabled' if enabled else 'disabled'
        await interaction.response.send_message(
            f'Join DM {state}.\nVariables: `{{user}}` `{{username}}` `{{displayname}}` `{{server}}` `{{count}}` `{{id}}`',
            ephemeral=True)

    @app_commands.command(name='join-dm-test', description='Test the join DM on yourself')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def join_dm_test(self, interaction: discord.Interaction):
        data = _load()
        cfg = data.get(str(interaction.guild.id), {})
        if not cfg.get('join_dm_message'):
            return await interaction.response.send_message('No join DM configured. Use `/join-dm-set` first.', ephemeral=True)
        try:
            embed = discord.Embed(
                description=_fill(cfg['join_dm_message'], interaction.user),
                color=int(cfg.get('join_dm_color', '0x5865f2'), 16)
            )
            if cfg.get('join_dm_title'):
                embed.title = _fill(cfg['join_dm_title'], interaction.user)
            embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
            await interaction.user.send(embed=embed)
            await interaction.response.send_message('Test DM sent!', ephemeral=True)
        except:
            await interaction.response.send_message('Could not DM you. Check your privacy settings.', ephemeral=True)

    @app_commands.command(name='role-persistence', description='Toggle role persistence (restore roles on rejoin)')
    @app_commands.checks.has_permissions(manage_roles=True)
    async def role_persistence(self, interaction: discord.Interaction, enabled: bool):
        data = _load()
        data.setdefault(str(interaction.guild.id), {})['role_persistence'] = enabled
        _save(data)
        state = 'enabled' if enabled else 'disabled'
        await interaction.response.send_message(
            f'Role persistence {state}. Members who leave and rejoin will {"have their roles restored" if enabled else "not have roles restored"}.',
            ephemeral=True)

    @app_commands.command(name='joinleave-status', description='View join/leave configuration')
    @app_commands.checks.has_permissions(manage_guild=True)
    async def status(self, interaction: discord.Interaction):
        data = _load()
        cfg = data.get(str(interaction.guild.id), {})
        embed = discord.Embed(title='Join/Leave Configuration', color=0x5865f2)
        embed.add_field(name='Join DM', value='✅ Enabled' if cfg.get('join_dm_enabled') else '❌ Disabled', inline=True)
        embed.add_field(name='Role Persistence', value='✅ Enabled' if cfg.get('role_persistence') else '❌ Disabled', inline=True)
        if cfg.get('join_dm_message'):
            embed.add_field(name='DM Preview', value=cfg['join_dm_message'][:200], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(JoinLeave(bot))
