"""
Tickets — support tickets with transcripts, categories, ratings (Ticket Tool USP)
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging, asyncio
from datetime import datetime, timezone

logger = logging.getLogger('discord_bot.tickets')
TICKETS_FILE = 'tickets.json'


def _load():
    if os.path.exists(TICKETS_FILE):
        try:
            with open(TICKETS_FILE) as f: return json.load(f)
        except: pass
    return {}


def _save(d):
    with open(TICKETS_FILE, 'w') as f: json.dump(d, f, indent=2)


def _cfg(guild_id):
    data = _load()
    return data.get(str(guild_id), {})


def _save_cfg(guild_id, cfg):
    data = _load()
    data[str(guild_id)] = cfg
    _save(data)


class RatingView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    async def _rate(self, ctx, rating: int):
        embed = discord.Embed(
            description=f'Thanks for your feedback! You rated this ticket **{rating}/5 ⭐**',
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        self.stop()

    @discord.ui.button(label='⭐', style=discord.ButtonStyle.secondary, custom_id='rate_1')
    async def r1(self, i, b): await self._rate(i, 1)
    @discord.ui.button(label='⭐⭐', style=discord.ButtonStyle.secondary, custom_id='rate_2')
    async def r2(self, i, b): await self._rate(i, 2)
    @discord.ui.button(label='⭐⭐⭐', style=discord.ButtonStyle.secondary, custom_id='rate_3')
    async def r3(self, i, b): await self._rate(i, 3)
    @discord.ui.button(label='⭐⭐⭐⭐', style=discord.ButtonStyle.secondary, custom_id='rate_4')
    async def r4(self, i, b): await self._rate(i, 4)
    @discord.ui.button(label='⭐⭐⭐⭐⭐', style=discord.ButtonStyle.primary, custom_id='rate_5')
    async def r5(self, i, b): await self._rate(i, 5)


class TicketView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Close Ticket', style=discord.ButtonStyle.danger, custom_id='ticket_close_btn', emoji='🔒')
    async def close_btn(self, ctx, button: discord.ui.Button):
        if not (ctx.author.guild_permissions.manage_channels or
                ctx.channel.topic and str(ctx.author.id) in ctx.channel.topic):
            return await ctx.send('Only staff or the ticket owner can close this.')
        await _do_close(ctx.channel, ctx.author, self.bot)
        await ctx.send('Closing ticket...')


class CategorySelectView(discord.ui.View):
    def __init__(self, bot, categories):
        super().__init__(timeout=60)
        self.bot = bot
        options = [discord.SelectOption(label=c['name'], value=c['name'], emoji='🎫') for c in categories[:25]]
        select = discord.ui.Select(placeholder='Choose a category...', options=options, custom_id='ticket_cat_select')
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, ctx):
        chosen = interaction.data['values'][0]
        cfg = _cfg(ctx.guild.id)
        cats = cfg.get('categories', [])
        cat = next((c for c in cats if c['name'] == chosen), None)
        await _open_ticket(interaction, self.bot, cat)


async def _do_close(channel: discord.TextChannel, closer: discord.Member, bot):
    """Generate transcript, DM user, delete channel."""
    cfg = _cfg(channel.guild.id)
    transcript_ch_id = cfg.get('transcript_channel')

    # Build transcript
    lines = [f'Ticket Transcript — #{channel.name}', f'Closed by: {closer}', f'Closed at: {datetime.now(timezone.utc).isoformat()}', '---']
    async for msg in channel.history(limit=500, oldest_first=True):
        ts = msg.created_at.strftime('%Y-%m-%d %H:%M')
        lines.append(f'[{ts}] {msg.author}: {msg.content}')
        for att in msg.attachments:
            lines.append(f'  [Attachment: {att.url}]')

    transcript_text = '\n'.join(lines)
    transcript_file = discord.File(
        fp=__import__('io').BytesIO(transcript_text.encode()),
        filename=f'transcript-{channel.name}.txt'
    )

    # Send to transcript channel
    if transcript_ch_id:
        tr_ch = channel.guild.get_channel(int(transcript_ch_id))
        if tr_ch:
            try:
                await tr_ch.send(f'📄 Transcript for {channel.mention}', file=transcript_file)
            except: pass

    # DM ticket owner with rating request
    topic = channel.topic or ''
    owner_id = None
    for part in topic.split('|'):
        if part.strip().startswith('owner:'):
            try:
                owner_id = int(part.strip().split(':')[1])
            except: pass
    if owner_id:
        owner = channel.guild.get_member(owner_id)
        if owner:
            try:
                embed = discord.Embed(
                    title='Your ticket has been closed',
                    description=f'Ticket `{channel.name}` in **{channel.guild.name}** was closed.\nPlease rate your support experience:',
                    color=0x5865f2
                )
                await owner.send(embed=embed, view=RatingView())
            except: pass

    await asyncio.sleep(3)
    try:
        await channel.delete(reason=f'Ticket closed by {closer}')
    except: pass


async def _open_ticket(interaction: discord.Interaction, bot, category: dict = None):
    """Create a ticket channel."""
    cfg = _cfg(ctx.guild.id)
    cat_id = cfg.get('category_id')
    if not cat_id:
        return await ctx.send('Ticket system not set up. Ask an admin to run `/ticket-setup`.')

    discord_cat = ctx.guild.get_channel(int(cat_id))
    if not discord_cat:
        return await ctx.send('Ticket category not found.')

    # Check for existing ticket
    for ch in discord_cat.text_channels:
        if ch.topic and f'owner:{ctx.author.id}' in ch.topic:
            return await ctx.send(f'You already have an open ticket: {ch.mention}')

    # Determine support role
    support_role_id = cfg.get('support_role_id')
    if category and category.get('role_id'):
        support_role_id = category['role_id']

    counter = cfg.get('counter', 0) + 1
    cfg['counter'] = counter
    _save_cfg(ctx.guild.id, cfg)

    cat_label = f'-{category["name"].lower().replace(" ", "-")}' if category else ''
    ch_name = f'ticket-{counter}{cat_label}'

    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
    }
    if support_role_id:
        role = ctx.guild.get_role(int(support_role_id))
        if role:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    channel = await discord_cat.create_text_channel(
        ch_name,
        overwrites=overwrites,
        topic=f'owner:{ctx.author.id} | opened:{datetime.now(timezone.utc).isoformat()}',
        reason=f'Ticket by {ctx.author}'
    )

    embed = discord.Embed(
        title=f'🎫 Ticket #{counter}{" — " + category["name"] if category else ""}',
        description=f'Welcome {ctx.author.mention}! Support will be with you shortly.\nDescribe your issue in detail.',
        color=0x5865f2,
        timestamp=datetime.now(timezone.utc)
    )
    # Try AI Coder generated ticket responses
    try:
        ai_coder = interaction.client.cogs.get("AICoder")
        if ai_coder:
            responses = ai_coder.get_generated("ticket_responses")
            if responses:
                import random as _r
                ai_msg = _r.choice(responses).replace("{user}", ctx.author.mention)
                embed.description = ai_msg
    except Exception:
        pass
    embed.set_footer(text=f'Ticket #{counter}')
    view = TicketView(bot)
    await channel.send(ctx.author.mention, embed=embed, view=view)

    if support_role_id:
        role = ctx.guild.get_role(int(support_role_id))
        if role:
            await channel.send(f'{role.mention} — new ticket opened!')

    await ctx.send(f'✅ Ticket created: {channel.mention}')


class OpenTicketView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Open Ticket', style=discord.ButtonStyle.success, custom_id='ticket_open_btn', emoji='🎫')
    async def open_btn(self, ctx, button: discord.ui.Button):
        cfg = _cfg(ctx.guild.id)
        cats = cfg.get('categories', [])
        if cats:
            await ctx.send('Select a category:', view=CategorySelectView(self.bot, cats))
        else:
            await _open_ticket(interaction, self.bot)


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(TicketView(bot))
        bot.add_view(OpenTicketView(bot))

    @commands.command(name="ticket-setup")
    async def setup(self, ctx,
                    category: discord.CategoryChannel = None,
                    support_role: discord.Role = None,
                    transcript_channel: discord.TextChannel = None):
        await ctx.defer()
        guild = ctx.guild

        if not category:
            category = await guild.create_category('Tickets')

        cfg = _cfg(guild.id)
        cfg['category_id'] = str(category.id)
        if support_role:
            cfg['support_role_id'] = str(support_role.id)
        if transcript_channel:
            cfg['transcript_channel'] = str(transcript_channel.id)
        cfg.setdefault('counter', 0)
        _save_cfg(guild.id, cfg)

        # Create panel channel
        panel_ch = await category.create_text_channel('open-a-ticket')
        embed = discord.Embed(
            title='🎫 Support Tickets',
            description='Need help? Click the button below to open a private support ticket.',
            color=0x5865f2
        )
        if support_role:
            embed.add_field(name='Support Team', value=support_role.mention, inline=True)
        await panel_ch.send(embed=embed, view=OpenTicketView(self.bot))

        await ctx.send(f'Ticket system set up in {category.mention}. Panel: {panel_ch.mention}')

    @commands.command(name="ticket-category-add")
    async def add_category(self, ctx, name: str, role: discord.Role = None):
        cfg = _cfg(ctx.guild.id)
        cats = cfg.setdefault('categories', [])
        if any(c['name'].lower() == name.lower() for c in cats):
            return await ctx.send('Category already exists.')
        cats.append({'name': name, 'role_id': str(role.id) if role else None})
        _save_cfg(ctx.guild.id, cfg)
        await ctx.send(f'Category `{name}` added.')

    @commands.command(name="ticket-category-remove")
    async def remove_category(self, ctx, name: str):
        cfg = _cfg(ctx.guild.id)
        cats = cfg.get('categories', [])
        new_cats = [c for c in cats if c['name'].lower() != name.lower()]
        if len(new_cats) == len(cats):
            return await ctx.send('Category not found.')
        cfg['categories'] = new_cats
        _save_cfg(ctx.guild.id, cfg)
        await ctx.send(f'Category `{name}` removed.')

    async def close(self, ctx):
        if not ctx.channel.name.startswith('ticket-'):
            return await ctx.send('This is not a ticket channel.')
        if not (ctx.author.guild_permissions.manage_channels or
                (ctx.channel.topic and f'owner:{ctx.author.id}' in ctx.channel.topic)):
            return await ctx.send('Only staff or the ticket owner can close this.')
        await ctx.send('Closing ticket...')
        await _do_close(ctx.channel, ctx.author, self.bot)

    async def add_user(self, ctx, user: discord.Member):
        if not ctx.channel.name.startswith('ticket-'):
            return await ctx.send('Not a ticket channel.')
        await ctx.channel.set_permissions(user, read_messages=True, send_messages=True)
        await ctx.send(f'Added {user.mention} to this ticket.')

    async def remove_user(self, ctx, user: discord.Member):
        if not ctx.channel.name.startswith('ticket-'):
            return await ctx.send('Not a ticket channel.')
        await ctx.channel.set_permissions(user, overwrite=None)
        await ctx.send(f'Removed {user.mention} from this ticket.')


async def setup(bot):
    await bot.add_cog(Tickets(bot))
