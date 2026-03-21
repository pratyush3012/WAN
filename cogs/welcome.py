"""
WAN Bot - Welcome/Goodbye System
Gender-aware randomized welcome messages — flirty for girls, cool/hype for guys.
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging, random
from datetime import datetime, timezone

logger = logging.getLogger('discord_bot.welcome')
DATA_FILE = 'welcome_data.json'

# ── Gender detection via Discord username heuristics ─────────────────────────
# We check the display name for common feminine/masculine name patterns.
# This is a best-effort heuristic — not perfect, but fun.

FEMININE_NAMES = {
    'emma','olivia','ava','isabella','sophia','mia','charlotte','amelia','harper',
    'evelyn','abigail','emily','elizabeth','mila','ella','avery','sofia','camila',
    'aria','scarlett','victoria','madison','luna','grace','chloe','penelope',
    'layla','riley','zoey','nora','lily','eleanor','hannah','lillian','addison',
    'aubrey','ellie','stella','natalie','zoe','leah','hazel','violet','aurora',
    'savannah','audrey','brooklyn','bella','claire','skylar','lucy','paisley',
    'everly','anna','caroline','nova','genesis','emilia','kennedy','samantha',
    'maya','willow','kinsley','naomi','aaliyah','elena','sarah','ariana','allison',
    'gabriella','alice','madelyn','cora','ruby','eva','serenity','autumn','adeline',
    'hailey','gianna','valentina','isla','eliana','quinn','nevaeh','ivy','sadie',
    'piper','lydia','alexa','josephine','emery','julia','delilah','arianna',
    'vivian','kaylee','sophie','brielle','madeline','peyton','rylee','clara',
    'hadley','melanie','mackenzie','reagan','adalynn','liliana','aubree','jade',
    'katherine','isabelle','natalia','raelynn','jasmine','faith','alexandra',
    'morgan','khloe','london','destiny','ximena','ashley','brianna','ariel',
    'alyssa','andrea','vanessa','jessica','taylor','amber','brittany','tiffany',
    'priya','ananya','divya','pooja','neha','shreya','riya','aisha','fatima',
    'zara','sara','nadia','lena','nina','diana','vera','kate','amy','lisa',
    'mary','anna','rose','grace','hope','joy','faith','dawn','eve','iris',
    'jade','ruby','pearl','opal','crystal','amber','sandy','cindy','wendy',
    'mandy','candy','brandy','mindy','lindy','sindy','randi','candi','sandi',
}

MASCULINE_NAMES = {
    'liam','noah','william','james','oliver','benjamin','elijah','lucas','mason',
    'ethan','alexander','henry','jacob','michael','daniel','logan','jackson',
    'sebastian','jack','aiden','owen','samuel','ryan','nathan','luke','gabriel',
    'anthony','isaac','grayson','dylan','leo','jaxon','julian','levi','matthew',
    'wyatt','andrew','joshua','lincoln','christopher','joseph','theodore','caleb',
    'hunter','christian','eli','jonathan','connor','landon','adrian','asher',
    'cameron','colton','easton','gael','evan','kayden','angel','roman','eli',
    'dominic','austin','ian','adam','nolan','brayden','thomas','charles','jace',
    'miles','brody','xavier','bentley','tyler','declan','carter','jason','cooper',
    'ryder','ayden','kevin','zachary','parker','blake','jose','chase','cole',
    'weston','hudson','jordan','greyson','bryson','zion','sawyer','emmett',
    'silas','micah','rowan','beau','tristan','ivan','alex','max','jake','sam',
    'ben','tom','tim','jim','bob','rob','joe','dan','ken','ron','don','ray',
    'jay','kay','lee','rex','rex','ace','ash','kai','zak','zac','zach',
    'arjun','rahul','rohan','vikram','aditya','karan','nikhil','siddharth',
    'pratik','pratyush','raj','amit','ankit','aman','akash','ayush','harsh',
    'yash','varun','tarun','arun','pavan','ravi','suresh','mahesh','ganesh',
    'ramesh','dinesh','naresh','mukesh','rakesh','lokesh','yogesh','umesh',
    'omar','ali','hassan','ahmed','khalid','tariq','bilal','hamza','usman',
    'mike','john','david','chris','mark','paul','steve','brian','kevin','eric',
    'jeff','scott','gary','larry','jerry','terry','barry','harry','larry',
}

def _detect_gender(member: discord.Member) -> str:
    """Returns 'female', 'male', or 'unknown' based on display name heuristics."""
    name = member.display_name.lower().strip()
    # Check first word of name
    first = name.split()[0] if name.split() else name
    # Remove common suffixes/numbers
    first_clean = ''.join(c for c in first if c.isalpha())
    if first_clean in FEMININE_NAMES:
        return 'female'
    if first_clean in MASCULINE_NAMES:
        return 'male'
    # Check if name ends in common feminine suffixes
    if any(first_clean.endswith(s) for s in ('ette','elle','ine','ina','ia','ya','ie','ee','i')):
        return 'female'
    return 'unknown'


# ── Welcome messages by gender ────────────────────────────────────────────────

WELCOME_TITLES_FEMALE = [
    "💕 A queen has entered the chat!",
    "✨ She arrived and the vibe shifted!",
    "👑 Royalty just walked in!",
    "🌸 A new star has joined us!",
    "💫 The server just got prettier!",
    "🔥 She's here and we're not ready!",
    "🌟 The legend herself has arrived!",
    "😍 Oh wow, look who just showed up!",
    "💅 She walked in like she owns the place!",
    "🎀 A new member and she's already iconic!",
]

WELCOME_MESSAGES_FEMALE = [
    "Hey {user} 💕 We've been waiting for you~ Make yourself at home in **{server}**!",
    "Oh look who decided to grace us with her presence 😏 Welcome, {user}! You're member **#{count}** — iconic.",
    "{user} just walked in and honestly? The whole vibe just improved 10x. Welcome to **{server}**! 🌸",
    "Careful everyone, {user} just arrived and she looks dangerous 😈 Welcome to the crew!",
    "The server was missing something... turns out it was you, {user}! Welcome to **{server}** 💫",
    "{user} has entered the chat. Everyone act cool 😎 Welcome to **{server}**!",
    "Plot twist: {user} just joined and now **{server}** is officially better 🎉",
    "We don't know you yet, {user}, but we already like you 😌 Welcome, queen!",
    "{user} just dropped in! You're our **#{count}** member — make it count 👑",
    "Roses are red, the server is lit, {user} just joined and we love it 💕",
    "New member alert 🚨 {user} has arrived! Say hi before she thinks we're boring 😂",
    "{user} walked in like she owns the place. Honestly? Respect. Welcome to **{server}**! 💪",
    "Hey {user}! Fair warning — we're a little chaotic here. You'll fit right in 😏",
    "The stars aligned and brought {user} to **{server}**. Coincidence? We think not ✨",
    "{user} just joined! Quick everyone, look busy 😅 Welcome to the crew, queen!",
]

WELCOME_TITLES_MALE = [
    "🔥 A new legend has arrived!",
    "💥 Someone just walked in!",
    "👊 The squad just got stronger!",
    "🚀 New member incoming!",
    "💪 The server just leveled up!",
    "😎 Look who decided to show up!",
    "⚡ A new challenger has appeared!",
    "🎮 Player 2 has entered the game!",
    "🏆 A new legend joins the ranks!",
    "🔱 The crew just got bigger!",
]

WELCOME_MESSAGES_MALE = [
    "Hey {user}! We've been waiting for you 👀 Make yourself at home in **{server}**!",
    "Oh look who decided to show up 😏 Welcome, {user}! You're member **#{count}** — not bad.",
    "{user} just walked in and honestly? The vibe just improved. Welcome to **{server}**! 🔥",
    "Careful everyone, {user} just arrived and he looks dangerous 😈 Welcome!",
    "The server was missing something... turns out it was you, {user}! Welcome to **{server}** 💫",
    "{user} has entered the chat. Everyone act cool 😎 Welcome to **{server}**!",
    "Plot twist: {user} just joined and now **{server}** is officially better 🎉",
    "We don't know who you are yet, {user}, but we already like you 😌 Welcome!",
    "{user} just dropped in! You're our **#{count}** member — make it count 👑",
    "New member alert 🚨 {user} has arrived! Say hi before he thinks we're boring 😂",
    "{user} walked in like he owns the place. Honestly? Respect. Welcome to **{server}**! 💪",
    "Hey {user}! Fair warning — we're a little chaotic here. You'll fit right in 😏",
    "The stars aligned and brought {user} to **{server}**. Coincidence? We think not ✨",
    "{user} just joined! Quick everyone, look busy 😅 Welcome to the crew!",
    "Player {user} has entered the game. **{server}** just got more interesting 🎮",
]

# Fallback (gender unknown)
WELCOME_TITLES_NEUTRAL = [
    "✨ A new legend has arrived!",
    "🔥 Someone just walked in!",
    "💫 Look who just showed up!",
    "👑 Royalty has entered the chat!",
    "🎉 The squad just got bigger!",
    "😏 Well well well...",
    "🚀 New member incoming!",
    "💥 The server just leveled up!",
    "🌟 A star has joined us!",
    "🎊 Welcome to the family!",
]

WELCOME_MESSAGES_NEUTRAL = [
    "Hey {user}! We've been waiting for you 👀 Make yourself at home in **{server}**!",
    "Oh look who decided to show up 😏 Welcome, {user}! You're member **#{count}** — not bad.",
    "{user} just walked in and honestly? The vibe just improved. Welcome to **{server}**! 🔥",
    "Careful everyone, {user} just arrived and they look dangerous 😈 Welcome!",
    "The server was missing something... turns out it was you, {user}! Welcome to **{server}** 💫",
    "{user} has entered the chat. Everyone act cool 😎 Welcome to **{server}**!",
    "Plot twist: {user} just joined and now **{server}** is officially better 🎉",
    "We don't know who you are yet, {user}, but we already like you 😌 Welcome!",
    "{user} just dropped in! You're our **#{count}** member — make it count 👑",
    "Roses are red, the server is lit, {user} just joined and we love it 💕",
    "New member alert 🚨 {user} has arrived! Say hi before they think we're boring 😂",
    "{user} walked in like they own the place. Honestly? Respect. Welcome to **{server}**! 💪",
    "Hey {user}! Fair warning — we're a little chaotic here. You'll fit right in 😏",
    "The stars aligned and brought {user} to **{server}**. Coincidence? We think not ✨",
    "{user} just joined! Quick everyone, look busy 😅 Welcome to the crew!",
]

GOODBYE_MESSAGES = [
    "**{username}** has left the building 👋 We'll miss you (a little).",
    "**{username}** dipped. **{server}** has {count} members now.",
    "And just like that, **{username}** was gone 💨 Take care out there!",
    "**{username}** left. The vibe took a small hit ngl 😔",
    "**{username}** has logged off from **{server}**. Until next time! 👋",
]


def _fill(template: str, member: discord.Member) -> str:
    return (template
        .replace('{user}', member.mention)
        .replace('{username}', member.display_name)
        .replace('{server}', member.guild.name)
        .replace('{count}', str(member.guild.member_count))
        .replace('{id}', str(member.id))
    )


def _parse_color(raw, default: int) -> int:
    try:
        s = str(raw).strip()
        if s.startswith('#'):
            return int(s[1:], 16)
        elif s.lower().startswith('0x'):
            return int(s, 16)
        else:
            return int(s, 16)
    except Exception:
        return default


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

        # Use custom message if set, otherwise pick gender-aware random one
        if event == 'welcome':
            if cfg.get('welcome_title') or cfg.get('welcome_message'):
                # Custom message set — use it
                raw_title = cfg.get('welcome_title') or random.choice(WELCOME_TITLES_NEUTRAL)
                raw_desc  = cfg.get('welcome_message') or random.choice(WELCOME_MESSAGES_NEUTRAL)
            else:
                # Auto gender detection
                gender = _detect_gender(member)
                if gender == 'female':
                    raw_title = random.choice(WELCOME_TITLES_FEMALE)
                    raw_desc  = random.choice(WELCOME_MESSAGES_FEMALE)
                elif gender == 'male':
                    raw_title = random.choice(WELCOME_TITLES_MALE)
                    raw_desc  = random.choice(WELCOME_MESSAGES_MALE)
                else:
                    raw_title = random.choice(WELCOME_TITLES_NEUTRAL)
                    raw_desc  = random.choice(WELCOME_MESSAGES_NEUTRAL)
            default_color = 0x57f287
        else:
            raw_title = cfg.get('goodbye_title') or '👋 See you around!'
            raw_desc  = cfg.get('goodbye_message') or random.choice(GOODBYE_MESSAGES)
            default_color = 0xef4444

        title = _fill(raw_title, member)
        desc  = _fill(raw_desc, member)
        color = _parse_color(cfg.get(f'{event}_color', default_color), default_color)

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"{member.guild.name} • {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
        try:
            await ch.send(embed=embed)
        except Exception as e:
            logger.warning(f"Welcome send error ({event}): {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = self._guild(member.guild.id)
        logger.info(f"Member join: {member} in {member.guild.name} — welcome_channel={cfg.get('welcome_channel')}")
        await self._send_embed(member, cfg, 'welcome')
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
        cfg = self._guild(after.guild.id)
        promo_channel_id = cfg.get('promo_channel')
        promo_msg_template = cfg.get('promo_message', '🎉 Congratulations {user}! You\'ve been promoted to **{role}**! Well deserved! 🎊')
        watched_raw = cfg.get('promo_roles', '')
        if not promo_channel_id or not watched_raw:
            return
        watched = [r.strip().lower() for r in watched_raw.split(',') if r.strip()]
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
                    logger.warning(f"Promo send error: {e}")
                break

    # ── Slash commands ─────────────────────────────────────────────────────────

    @app_commands.command(name="welcome-set", description="👋 Configure welcome messages (leave blank for random)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_set(self, interaction: discord.Interaction,
                          channel: discord.TextChannel,
                          message: str = "",
                          title: str = "",
                          color: str = "#57f287"):
        cfg = self._guild(interaction.guild.id)
        cfg.update({
            'welcome_channel': str(channel.id),
            'welcome_message': message,
            'welcome_title': title,
            'welcome_color': color,
        })
        self._save()
        note = "Random messages enabled (no custom message set)." if not message else f"Custom message saved."
        await interaction.response.send_message(
            f"✅ Welcome → {channel.mention}\n{note}\n"
            f"Variables: `{{user}}` `{{username}}` `{{server}}` `{{count}}` `{{id}}`",
            ephemeral=True)

    @app_commands.command(name="goodbye-set", description="👋 Configure goodbye messages")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def goodbye_set(self, interaction: discord.Interaction,
                          channel: discord.TextChannel,
                          message: str = "",
                          title: str = ""):
        cfg = self._guild(interaction.guild.id)
        cfg.update({'goodbye_channel': str(channel.id), 'goodbye_message': message, 'goodbye_title': title})
        self._save()
        await interaction.response.send_message(f"✅ Goodbye → {channel.mention}", ephemeral=True)

    @app_commands.command(name="autorole", description="👋 Set a role to auto-assign when members join")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole(self, interaction: discord.Interaction, role: discord.Role = None):
        cfg = self._guild(interaction.guild.id)
        if role:
            cfg['autorole'] = str(role.id)
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
