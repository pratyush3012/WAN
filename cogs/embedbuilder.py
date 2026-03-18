"""
EmbedBuilder — create and post rich embeds via slash command or dashboard
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging

logger = logging.getLogger('discord_bot.embedbuilder')
EMBEDS_FILE = 'saved_embeds.json'


def _load():
    if os.path.exists(EMBEDS_FILE):
        try:
            with open(EMBEDS_FILE) as f: return json.load(f)
        except: pass
    return {}

def _save(d):
    with open(EMBEDS_FILE, 'w') as f: json.dump(d, f, indent=2)


def _build_embed(data: dict) -> discord.Embed:
    color = 0x5865f2
    if data.get('color'):
        try:
            color = int(data['color'].lstrip('#'), 16)
        except: pass

    embed = discord.Embed(
        title=data.get('title') or None,
        description=data.get('description') or None,
        color=color,
        url=data.get('url') or None,
    )
    if data.get('thumbnail'):
        embed.set_thumbnail(url=data['thumbnail'])
    if data.get('image'):
        embed.set_image(url=data['image'])
    if data.get('footer'):
        embed.set_footer(
            text=data['footer'],
            icon_url=data.get('footer_icon') or None
        )
    if data.get('author'):
        embed.set_author(
            name=data['author'],
            icon_url=data.get('author_icon') or None,
            url=data.get('author_url') or None
        )
    for field in data.get('fields', []):
        embed.add_field(
            name=field.get('name', '\u200b'),
            value=field.get('value', '\u200b'),
            inline=field.get('inline', False)
        )
    return embed


class EmbedBuilder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='embed', description='Post a custom embed to a channel')
    @app_commands.describe(
        channel='Channel to post in',
        title='Embed title',
        description='Embed description (supports markdown)',
        color='Hex color e.g. #ff0000',
        image='Image URL',
        thumbnail='Thumbnail URL',
        footer='Footer text',
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed(self, interaction: discord.Interaction,
                    channel: discord.TextChannel,
                    description: str,
                    title: str = '',
                    color: str = '#5865f2',
                    image: str = '',
                    thumbnail: str = '',
                    footer: str = ''):
        data = {
            'title': title, 'description': description, 'color': color,
            'image': image, 'thumbnail': thumbnail, 'footer': footer,
        }
        try:
            embed = _build_embed(data)
            await channel.send(embed=embed)
            await interaction.response.send_message(f'Embed posted to {channel.mention}.', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'Error: {e}', ephemeral=True)

    @app_commands.command(name='embed-save', description='Save an embed template for reuse')
    @app_commands.describe(name='Template name', title='Title', description='Description', color='Hex color')
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed_save(self, interaction: discord.Interaction,
                         name: str, description: str, title: str = '', color: str = '#5865f2'):
        data = _load()
        gid = str(interaction.guild.id)
        data.setdefault(gid, {})[name.lower()] = {
            'title': title, 'description': description, 'color': color,
            'created_by': str(interaction.user.id),
        }
        _save(data)
        await interaction.response.send_message(f'Embed template `{name}` saved.', ephemeral=True)

    @app_commands.command(name='embed-post', description='Post a saved embed template')
    @app_commands.describe(name='Template name', channel='Channel to post in')
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed_post(self, interaction: discord.Interaction,
                         name: str, channel: discord.TextChannel):
        data = _load()
        template = data.get(str(interaction.guild.id), {}).get(name.lower())
        if not template:
            return await interaction.response.send_message(f'Template `{name}` not found.', ephemeral=True)
        try:
            embed = _build_embed(template)
            await channel.send(embed=embed)
            await interaction.response.send_message(f'Posted `{name}` to {channel.mention}.', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'Error: {e}', ephemeral=True)

    @app_commands.command(name='embed-list', description='List saved embed templates')
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed_list(self, interaction: discord.Interaction):
        data = _load()
        templates = data.get(str(interaction.guild.id), {})
        if not templates:
            return await interaction.response.send_message('No saved templates.', ephemeral=True)
        embed = discord.Embed(title='Saved Embed Templates', color=0x5865f2)
        for name, t in templates.items():
            embed.add_field(name=f'`{name}`', value=(t.get('title') or t.get('description', ''))[:80], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='embed-delete', description='Delete a saved embed template')
    @app_commands.describe(name='Template name')
    @app_commands.checks.has_permissions(manage_messages=True)
    async def embed_delete(self, interaction: discord.Interaction, name: str):
        data = _load()
        gid = str(interaction.guild.id)
        if gid in data and name.lower() in data[gid]:
            del data[gid][name.lower()]
            _save(data)
            await interaction.response.send_message(f'Template `{name}` deleted.', ephemeral=True)
        else:
            await interaction.response.send_message('Template not found.', ephemeral=True)


async def setup(bot):
    await bot.add_cog(EmbedBuilder(bot))
