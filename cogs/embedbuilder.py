"""
EmbedBuilder — create and post rich embeds via prefix command or dashboard
"""
import discord
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

    @commands.command(name='embed')
    @commands.has_permissions(manage_messages=True)
    async def embed(self, ctx: commands.Context, channel: discord.TextChannel, *, description: str):
        """Post a custom embed: !embed #channel <description>"""
        data = {'description': description}
        try:
            e = _build_embed(data)
            await channel.send(embed=e)
            await ctx.send(f'Embed posted to {channel.mention}.')
        except Exception as ex:
            await ctx.send(f'Error: {ex}')

    @commands.command(name='embed-save')
    @commands.has_permissions(manage_messages=True)
    async def embed_save(self, ctx: commands.Context, name: str, *, description: str):
        """Save an embed template: !embed-save <name> <description>"""
        data = _load()
        gid = str(ctx.guild.id)
        data.setdefault(gid, {})[name.lower()] = {
            'description': description,
            'created_by': str(ctx.author.id),
        }
        _save(data)
        await ctx.send(f'Embed template `{name}` saved.')

    @commands.command(name='embed-post')
    @commands.has_permissions(manage_messages=True)
    async def embed_post(self, ctx: commands.Context, name: str, channel: discord.TextChannel):
        """Post a saved embed template: !embed-post <name> #channel"""
        data = _load()
        template = data.get(str(ctx.guild.id), {}).get(name.lower())
        if not template:
            return await ctx.send(f'Template `{name}` not found.')
        try:
            e = _build_embed(template)
            await channel.send(embed=e)
            await ctx.send(f'Posted `{name}` to {channel.mention}.')
        except Exception as ex:
            await ctx.send(f'Error: {ex}')

    @commands.command(name='embed-list')
    @commands.has_permissions(manage_messages=True)
    async def embed_list(self, ctx: commands.Context):
        """List saved embed templates"""
        data = _load()
        templates = data.get(str(ctx.guild.id), {})
        if not templates:
            return await ctx.send('No saved templates.')
        embed = discord.Embed(title='Saved Embed Templates', color=0x5865f2)
        for name, t in templates.items():
            embed.add_field(name=f'`{name}`', value=(t.get('title') or t.get('description', ''))[:80], inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='embed-delete')
    @commands.has_permissions(manage_messages=True)
    async def embed_delete(self, ctx: commands.Context, *, name: str):
        """Delete a saved embed template"""
        data = _load()
        gid = str(ctx.guild.id)
        if gid in data and name.lower() in data[gid]:
            del data[gid][name.lower()]
            _save(data)
            await ctx.send(f'Template `{name}` deleted.')
        else:
            await ctx.send('Template not found.')


async def setup(bot):
    await bot.add_cog(EmbedBuilder(bot))
