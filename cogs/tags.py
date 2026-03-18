"""
Tags — searchable custom responses with aliases (Carl-bot USP)
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging

logger = logging.getLogger('discord_bot.tags')
TAGS_FILE = 'tags.json'


def _load():
    if os.path.exists(TAGS_FILE):
        try:
            with open(TAGS_FILE) as f: return json.load(f)
        except: pass
    return {}


def _save(d):
    with open(TAGS_FILE, 'w') as f: json.dump(d, f, indent=2)


def _get_tag(data, guild_id, name):
    """Find tag by name or alias."""
    tags = data.get(str(guild_id), {})
    name_lower = name.lower()
    for tag_name, tag in tags.items():
        if tag_name.lower() == name_lower:
            return tag_name, tag
        if name_lower in [a.lower() for a in tag.get('aliases', [])]:
            return tag_name, tag
    return None, None


class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='tag', description='Use a tag')
    @app_commands.describe(name='Tag name or alias')
    async def tag(self, interaction: discord.Interaction, name: str):
        data = _load()
        _, t = _get_tag(data, interaction.guild.id, name)
        if not t:
            return await interaction.response.send_message(f'Tag `{name}` not found.', ephemeral=True)
        # Increment uses
        t['uses'] = t.get('uses', 0) + 1
        _save(data)
        await interaction.response.send_message(t['content'])

    @app_commands.command(name='tag-create', description='Create a new tag')
    @app_commands.describe(name='Tag name', content='Tag content', aliases='Comma-separated aliases (optional)')
    @app_commands.checks.has_permissions(manage_messages=True)
    async def create(self, interaction: discord.Interaction, name: str, content: str, aliases: str = ''):
        data = _load()
        gid = str(interaction.guild.id)
        existing_name, _ = _get_tag(data, gid, name)
        if existing_name:
            return await interaction.response.send_message(f'Tag `{name}` already exists.', ephemeral=True)
        alias_list = [a.strip() for a in aliases.split(',') if a.strip()] if aliases else []
        data.setdefault(gid, {})[name.lower()] = {
            'content': content,
            'aliases': alias_list,
            'author_id': str(interaction.user.id),
            'uses': 0,
        }
        _save(data)
        await interaction.response.send_message(f'Tag `{name}` created.', ephemeral=True)

    @app_commands.command(name='tag-edit', description='Edit an existing tag')
    @app_commands.describe(name='Tag name', content='New content')
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit(self, interaction: discord.Interaction, name: str, content: str):
        data = _load()
        tag_name, t = _get_tag(data, interaction.guild.id, name)
        if not t:
            return await interaction.response.send_message(f'Tag `{name}` not found.', ephemeral=True)
        t['content'] = content
        _save(data)
        await interaction.response.send_message(f'Tag `{tag_name}` updated.', ephemeral=True)

    @app_commands.command(name='tag-delete', description='Delete a tag')
    @app_commands.describe(name='Tag name')
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delete(self, interaction: discord.Interaction, name: str):
        data = _load()
        gid = str(interaction.guild.id)
        tag_name, _ = _get_tag(data, gid, name)
        if not tag_name:
            return await interaction.response.send_message(f'Tag `{name}` not found.', ephemeral=True)
        del data[gid][tag_name]
        _save(data)
        await interaction.response.send_message(f'Tag `{tag_name}` deleted.', ephemeral=True)

    @app_commands.command(name='tag-list', description='List all tags in this server')
    async def list_tags(self, interaction: discord.Interaction):
        data = _load()
        tags = data.get(str(interaction.guild.id), {})
        if not tags:
            return await interaction.response.send_message('No tags created yet.', ephemeral=True)
        embed = discord.Embed(title=f'Tags — {interaction.guild.name}', color=0x5865f2)
        lines = []
        for name, t in sorted(tags.items()):
            aliases = ', '.join(t.get('aliases', []))
            line = f'`{name}`'
            if aliases:
                line += f' (aliases: {aliases})'
            line += f' — {t.get("uses", 0)} uses'
            lines.append(line)
        embed.description = '\n'.join(lines[:30])
        embed.set_footer(text=f'{len(tags)} tag(s) total')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='tag-info', description='Get info about a tag')
    @app_commands.describe(name='Tag name')
    async def info(self, interaction: discord.Interaction, name: str):
        data = _load()
        tag_name, t = _get_tag(data, interaction.guild.id, name)
        if not t:
            return await interaction.response.send_message(f'Tag `{name}` not found.', ephemeral=True)
        author = interaction.guild.get_member(int(t['author_id'])) if t.get('author_id') else None
        embed = discord.Embed(title=f'Tag: {tag_name}', color=0x5865f2)
        embed.add_field(name='Content', value=t['content'][:500], inline=False)
        embed.add_field(name='Aliases', value=', '.join(t.get('aliases', [])) or 'None', inline=True)
        embed.add_field(name='Uses', value=str(t.get('uses', 0)), inline=True)
        embed.add_field(name='Author', value=author.mention if author else t.get('author_id', 'Unknown'), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tags(bot))
