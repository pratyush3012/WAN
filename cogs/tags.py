"""
Tags — searchable custom responses with aliases (Carl-bot USP)
"""
import discord
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

    @commands.command(name='tag')
    async def tag(self, ctx: commands.Context, *, name: str):
        """Use a tag"""
        data = _load()
        _, t = _get_tag(data, ctx.guild.id, name)
        if not t:
            return await ctx.send(f'Tag `{name}` not found.')
        t['uses'] = t.get('uses', 0) + 1
        _save(data)
        await ctx.send(t['content'])

    @commands.command(name='tag-create')
    @commands.has_permissions(manage_messages=True)
    async def create(self, ctx: commands.Context, name: str, *, content: str):
        """Create a new tag: !tag-create <name> <content>"""
        data = _load()
        gid = str(ctx.guild.id)
        existing_name, _ = _get_tag(data, gid, name)
        if existing_name:
            return await ctx.send(f'Tag `{name}` already exists.')
        data.setdefault(gid, {})[name.lower()] = {
            'content': content,
            'aliases': [],
            'author_id': str(ctx.author.id),
            'uses': 0,
        }
        _save(data)
        await ctx.send(f'Tag `{name}` created.')

    @commands.command(name='tag-edit')
    @commands.has_permissions(manage_messages=True)
    async def edit(self, ctx: commands.Context, name: str, *, content: str):
        """Edit an existing tag: !tag-edit <name> <new content>"""
        data = _load()
        tag_name, t = _get_tag(data, ctx.guild.id, name)
        if not t:
            return await ctx.send(f'Tag `{name}` not found.')
        t['content'] = content
        _save(data)
        await ctx.send(f'Tag `{tag_name}` updated.')

    @commands.command(name='tag-delete')
    @commands.has_permissions(manage_messages=True)
    async def delete(self, ctx: commands.Context, *, name: str):
        """Delete a tag"""
        data = _load()
        gid = str(ctx.guild.id)
        tag_name, _ = _get_tag(data, gid, name)
        if not tag_name:
            return await ctx.send(f'Tag `{name}` not found.')
        del data[gid][tag_name]
        _save(data)
        await ctx.send(f'Tag `{tag_name}` deleted.')

    @commands.command(name='tag-list')
    async def list_tags(self, ctx: commands.Context):
        """List all tags in this server"""
        data = _load()
        tags = data.get(str(ctx.guild.id), {})
        if not tags:
            return await ctx.send('No tags created yet.')
        embed = discord.Embed(title=f'Tags — {ctx.guild.name}', color=0x5865f2)
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
        await ctx.send(embed=embed)

    @commands.command(name='tag-info')
    async def info(self, ctx: commands.Context, *, name: str):
        """Get info about a tag"""
        data = _load()
        tag_name, t = _get_tag(data, ctx.guild.id, name)
        if not t:
            return await ctx.send(f'Tag `{name}` not found.')
        author = ctx.guild.get_member(int(t['author_id'])) if t.get('author_id') else None
        embed = discord.Embed(title=f'Tag: {tag_name}', color=0x5865f2)
        embed.add_field(name='Content', value=t['content'][:500], inline=False)
        embed.add_field(name='Aliases', value=', '.join(t.get('aliases', [])) or 'None', inline=True)
        embed.add_field(name='Uses', value=str(t.get('uses', 0)), inline=True)
        embed.add_field(name='Author', value=author.mention if author else t.get('author_id', 'Unknown'), inline=True)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Tags(bot))
