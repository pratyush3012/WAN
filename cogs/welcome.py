"""
WAN Bot - Welcome / Goodbye / Promotion System
- Settings stored in DB (persistent across Render redeploys)
- Gemini AI generates unique welcome/goodbye messages
- Gender-aware fallback pool (20+ messages each)
- Promotion announcements on role gain
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging, random, asyncio
import urllib.request
from utils.settings import get_setting, set_setting

logger = logging.getLogger("discord_bot.welcome")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


async def _gemini(prompt: str, max_tokens: int = 120):
    try:
        from utils.gemini import gemini_call
        return await gemini_call(prompt, max_tokens=max_tokens, temperature=0.95)
    except ImportError:
        pass
    if not GEMINI_API_KEY:
        return None
    try:
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.95}
        }).encode()
        url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        loop = asyncio.get_event_loop()
        def _call():
            with urllib.request.urlopen(req, timeout=8) as resp:
                return json.loads(resp.read())
        data = await loop.run_in_executor(None, _call)
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.warning(f"Gemini error in welcome: {e}")
        return None


FEMININE_NAMES = {
    "emma","olivia","ava","isabella","sophia","mia","charlotte","amelia","harper","evelyn",
    "abigail","emily","elizabeth","mila","ella","avery","sofia","camila","aria","scarlett",
    "victoria","madison","luna","grace","chloe","penelope","layla","riley","zoey","nora",
    "lily","eleanor","hannah","lillian","addison","aubrey","ellie","stella","natalie","zoe",
    "leah","hazel","violet","aurora","savannah","audrey","brooklyn","bella","claire","skylar",
    "lucy","paisley","everly","anna","caroline","nova","genesis","emilia","kennedy","samantha",
    "maya","willow","kinsley","naomi","aaliyah","elena","sarah","ariana","allison","gabriella",
    "alice","madelyn","cora","ruby","eva","serenity","autumn","adeline","hailey","gianna",
    "valentina","isla","eliana","quinn","nevaeh","ivy","sadie","piper","lydia","alexa",
    "priya","ananya","divya","pooja","neha","shreya","riya","aisha","fatima","zara",
    "sara","nadia","lena","nina","diana","vera","kate","amy","lisa","mary","rose",
    "hope","joy","dawn","eve","iris","pearl","opal","crystal","sandy","cindy","wendy",
    "mandy","candy","brandy","mindy","randi","candi","jade","jasmine","faith","morgan",
    "khloe","london","destiny","ximena","ashley","brianna","ariel","alyssa","andrea","vanessa"
}
MASCULINE_NAMES = {
    "liam","noah","william","james","oliver","benjamin","elijah","lucas","mason","ethan",
    "alexander","henry","jacob","michael","daniel","logan","jackson","sebastian","jack","aiden",
    "owen","samuel","ryan","nathan","luke","gabriel","anthony","isaac","grayson","dylan",
    "leo","jaxon","julian","levi","matthew","wyatt","andrew","joshua","lincoln","christopher",
    "joseph","theodore","caleb","hunter","christian","eli","jonathan","connor","landon","adrian",
    "asher","cameron","colton","easton","evan","kayden","roman","dominic","austin","ian",
    "adam","nolan","thomas","charles","jace","miles","brody","xavier","tyler","declan",
    "carter","jason","cooper","ryder","kevin","zachary","parker","blake","chase","cole",
    "alex","max","jake","sam","ben","tom","tim","jim","bob","rob","joe","dan","ken",
    "ron","don","ray","jay","lee","rex","ace","ash","kai","zak","zac","zach",
    "arjun","rahul","rohan","vikram","aditya","karan","nikhil","siddharth","pratik","pratyush",
    "raj","amit","ankit","aman","akash","ayush","harsh","yash","varun","tarun","arun",
    "pavan","ravi","suresh","mahesh","ganesh","ramesh","dinesh","naresh","mukesh","rakesh",
    "omar","ali","hassan","ahmed","khalid","tariq","bilal","hamza","usman",
    "mike","john","david","chris","mark","paul","steve","brian","eric","jeff","scott","gary"
}


def _detect_gender(member):
    name = member.display_name.lower().strip()
    first = name.split()[0] if name.split() else name
    fc = "".join(c for c in first if c.isalpha())
    if fc in FEMININE_NAMES: return "female"
    if fc in MASCULINE_NAMES: return "male"
    if any(fc.endswith(s) for s in ("ette","elle","ine","ina","ia","ya","ie","ee")): return "female"
    return "unknown"


WELCOME_F = [
    "\U0001f495 A queen has entered the chat! Welcome {user} \u2014 you're member **#{count}** and we're already obsessed!",
    "\u2728 {user} just walked in and honestly? The whole vibe shifted. Welcome to **{server}**! \U0001f451",
    "She arrived \U0001f338 {user} is here! **{server}** just got 10x better, welcome queen!",
    "Careful everyone, {user} just joined and she looks dangerous \U0001f608 Welcome to **{server}**!",
    "The server was missing something... turns out it was you, {user}! Welcome \U0001f4ab",
    "{user} has entered the chat. Everyone act cool \U0001f60e Welcome to **{server}**!",
    "New member alert \U0001f6a8 {user} arrived! Say hi before she thinks we're boring \U0001f602",
    "{user} walked in like she owns the place. Honestly? Respect. Welcome! \U0001f4aa",
    "Hey {user}! Fair warning \u2014 we're a little chaotic here. You'll fit right in \U0001f60f",
    "The stars aligned and brought {user} to **{server}**. Coincidence? We think not \u2728",
    "Roses are red, the server is lit, {user} just joined and we love it \U0001f495",
    "Plot twist: {user} just joined and now **{server}** is officially better \U0001f389",
    "We don't know you yet {user}, but we already like you \U0001f60c Welcome, queen!",
    "{user} just dropped in! You're our **#{count}** member \u2014 make it count \U0001f451",
    "Tere aane se roshan hua ye server \U0001f319 Welcome {user}! We're so glad you're here \U0001f495",
    "The legend {user} has arrived! **{server}** will never be the same \U0001f31f",
    "Oh wow {user} is here \U0001f60d Welcome to **{server}** \u2014 you're already our favorite!",
    "Someone told me a queen was joining today \U0001f451 Welcome {user}! They were right!",
    "{user} just joined and I'm already writing a shayari about it \U0001f62d Welcome!",
    "Welcome {user}! You're member **#{count}** and honestly we peaked today \U0001f495",
]
WELCOME_M = [
    "\U0001f525 {user} just walked in! Welcome to **{server}** \u2014 you're member **#{count}**, legend!",
    "Bhai {user} aa gaya! \U0001f60e Welcome to **{server}** \u2014 scene ban gaya!",
    "New player unlocked \U0001f3ae {user} has joined **{server}**! Welcome to the squad!",
    "Careful everyone, {user} just arrived and he looks dangerous \U0001f608 Welcome!",
    "The server was missing something... turns out it was you, {user}! Welcome \U0001f4ab",
    "{user} has entered the chat. Everyone act cool \U0001f60e Welcome to **{server}**!",
    "New member alert \U0001f6a8 {user} arrived! Say hi before he thinks we're boring \U0001f602",
    "{user} walked in like he owns the place. Honestly? Respect. Welcome! \U0001f4aa",
    "Hey {user}! Fair warning \u2014 we're a little chaotic here. You'll fit right in \U0001f60f",
    "The stars aligned and brought {user} to **{server}**. Coincidence? We think not \u2728",
    "Plot twist: {user} just joined and now **{server}** is officially better \U0001f389",
    "We don't know you yet {user}, but we already like you \U0001f60c Welcome!",
    "{user} just dropped in! You're our **#{count}** member \u2014 make it count \U0001f451",
    "Bhai {user} teri entry se macha shor hai \U0001f525 Welcome to **{server}**!",
    "Player {user} has entered the game. **{server}** just got more interesting \U0001f3ae",
    "The legend {user} has arrived! **{server}** will never be the same \U0001f31f",
    "Bro {user} is here \U0001f4aa Welcome to **{server}** \u2014 you're already one of us!",
    "Someone told me a legend was joining today \U0001f451 Welcome {user}! They were right!",
    "{user} just joined and I'm already hyped \U0001f525 Welcome to the crew!",
    "Welcome {user}! You're member **#{count}** and honestly we peaked today \U0001f4aa",
]
WELCOME_N = [
    "\u2728 {user} just joined **{server}**! Welcome \u2014 you're member **#{count}**!",
    "New member alert \U0001f6a8 {user} has arrived! Welcome to **{server}**!",
    "{user} has entered the chat. Everyone act cool \U0001f60e Welcome!",
    "The server was missing something... turns out it was you, {user}! Welcome \U0001f4ab",
    "Plot twist: {user} just joined and now **{server}** is officially better \U0001f389",
    "We don't know you yet {user}, but we already like you \U0001f60c Welcome!",
    "{user} just dropped in! You're our **#{count}** member \u2014 make it count \U0001f451",
    "Hey {user}! Fair warning \u2014 we're a little chaotic here. You'll fit right in \U0001f60f",
    "The stars aligned and brought {user} to **{server}**. Coincidence? We think not \u2728",
    "Welcome {user}! You're member **#{count}** and we're glad you're here \U0001f389",
    "The legend {user} has arrived! **{server}** will never be the same \U0001f31f",
    "Oh wow {user} is here! Welcome to **{server}** \u2014 you're already our favorite!",
    "{user} just joined and we're already excited \U0001f525 Welcome to the crew!",
]
GOODBYE_MSGS = [
    "**{username}** has left the building \U0001f44b We'll miss you (a little). **{server}** now has {count} members.",
    "**{username}** dipped \U0001f4a8 Take care out there! **{server}** has {count} members now.",
    "And just like that, **{username}** was gone \U0001f614 Until next time!",
    "**{username}** left the server. The vibe took a small hit ngl \U0001f614 ({count} members remain)",
    "**{username}** has logged off from **{server}**. Until next time! \U0001f44b",
    "Goodbye **{username}** \U0001f44b You will be missed! ({count} members left)",
    "**{username}** left \U0001f622 Hope to see you back soon! **{server}** misses you already.",
    "**{username}** has departed. Safe travels! \U0001f31f ({count} members remain)",
]


def _fill(template, member):
    return (template
        .replace("{user}", member.mention)
        .replace("{username}", member.display_name)
        .replace("{server}", member.guild.name)
        .replace("{count}", str(member.guild.member_count))
        .replace("{id}", str(member.id))
    )

def _parse_color(raw, default=0x57f287):
    try:
        s = str(raw).strip().lstrip("#")
        return int(s, 16)
    except Exception:
        return default

def _auto_channel(guild, keywords=("lounge","welcome","general","lobby","chat","main","arrival")):
    """Find best channel — prioritises 'lounge' and 'welcome' first."""
    for kw in keywords:
        for ch in guild.text_channels:
            if kw in ch.name.lower():
                perms = ch.permissions_for(guild.me)
                if perms.send_messages and perms.embed_links:
                    return ch
    for ch in guild.text_channels:
        perms = ch.permissions_for(guild.me)
        if perms.send_messages and perms.embed_links:
            return ch
    return None


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # In-memory cache per guild to avoid DB round-trips on every join
        self._cache: dict = {}

    async def _get_cfg(self, guild_id: int) -> dict:
        """Load guild welcome config from DB (with in-memory cache)."""
        gid = str(guild_id)
        if gid not in self._cache:
            stored = await get_setting(guild_id, "welcome_config", {})
            self._cache[gid] = stored if isinstance(stored, dict) else {}
        return self._cache[gid]

    async def _save_cfg(self, guild_id: int, cfg: dict):
        """Persist guild welcome config to DB and update cache."""
        gid = str(guild_id)
        self._cache[gid] = cfg
        await set_setting(guild_id, "welcome_config", cfg)

    async def _ai_welcome(self, member, gender):
        gender_ctx = {
            "female": (
                "She is a girl. Be warm, flirty, and welcoming. "
                "Call her queen/gorgeous/jaan. Mix in a short Urdu/Hindi shayari line. "
                "Be unhinged and fun, not boring."
            ),
            "male": (
                "He is a guy. Be hype, bro energy, welcoming. "
                "Call him legend/bhai/bro. Mix in a short Hindi/Urdu shayari or desi phrase. "
                "Be energetic and fun."
            ),
            "unknown": "Be warm, welcoming, and fun. Mix in a short shayari line.",
        }.get(gender, "Be warm and welcoming.")

        prompt = (
            f"Write a short Discord welcome message for a new member joining a server.\n"
            f"Member name: {member.display_name}\n"
            f"Server name: {member.guild.name}\n"
            f"Member count: {member.guild.member_count}\n"
            f"Personality: {gender_ctx}\n\n"
            f"Rules:\n"
            f"- 2-3 sentences MAX\n"
            f"- Use 2-3 relevant emojis\n"
            f"- Mention their name with @mention placeholder {{user}}\n"
            f"- Include one short shayari or desi phrase (Hindi/Urdu romanized)\n"
            f"- Do NOT use markdown headers or asterisks for bold\n"
            f"- Make it feel personal, exciting, and unique — not generic\n"
            f"- End with a warm invitation to the server"
        )
        return await _gemini(prompt, max_tokens=150)

    async def _ai_goodbye(self, member):
        prompt = (
            f"Write a short Discord goodbye message for a member who just left.\n"
            f"Member name: {member.display_name}\n"
            f"Server name: {member.guild.name}\n"
            f"Remaining members: {member.guild.member_count}\n\n"
            f"Rules:\n"
            f"- 2 sentences MAX\n"
            f"- Use 1-2 emojis\n"
            f"- Mention their name\n"
            f"- Include a short sad/nostalgic shayari line (Hindi/Urdu romanized)\n"
            f"- Be warm but a little sad — like saying bye to a friend\n"
            f"- Do NOT be generic or robotic"
        )
        return await _gemini(prompt, max_tokens=100)

    async def _send_embed(self, member, cfg, event: str):
        """Compatibility shim called by the dashboard test button."""
        if event == "goodbye":
            await self._send_goodbye(member)
        else:
            await self._send_welcome(member)

    async def _send_welcome(self, member):
        cfg = await self._get_cfg(member.guild.id)
        gender = _detect_gender(member)

        ch_id = cfg.get("welcome_channel")
        if ch_id:
            ch = member.guild.get_channel(int(ch_id))
            # If saved channel no longer exists, fall back to auto-detect
            if not ch:
                ch = _auto_channel(member.guild)
                if ch:
                    cfg["welcome_channel"] = str(ch.id)
                    await self._save_cfg(member.guild.id, cfg)
        else:
            ch = _auto_channel(member.guild)
            if ch:
                cfg["welcome_channel"] = str(ch.id)
                await self._save_cfg(member.guild.id, cfg)
                logger.info(f"Auto-detected welcome channel: #{ch.name} in {member.guild.name}")

        if not ch:
            logger.warning(f"No welcome channel found for {member.guild.name}")
            return

        if cfg.get("welcome_message"):
            desc = _fill(cfg["welcome_message"], member)
            title = _fill(cfg.get("welcome_title", ""), member) or None
        else:
            ai_coder_msg = None
            try:
                ai_coder = self.bot.cogs.get("AICoder")
                if ai_coder:
                    msgs = ai_coder.get_generated("welcome_messages")
                    if msgs:
                        ai_coder_msg = _fill(random.choice(msgs), member)
            except Exception:
                pass

            if ai_coder_msg:
                desc = ai_coder_msg
                title = None
            else:
                ai_msg = await self._ai_welcome(member, gender)
                if ai_msg:
                    desc = ai_msg.replace("{user}", member.mention).replace("{username}", member.display_name)
                    title = None
                else:
                    pool = WELCOME_F if gender == "female" else WELCOME_M if gender == "male" else WELCOME_N
                    desc = _fill(random.choice(pool), member)
                    title = None

        color = _parse_color(cfg.get("welcome_color", "57f287"), 0x57f287)
        embed = discord.Embed(description=desc, color=color)
        if title:
            embed.title = title
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Welcome to {member.guild.name} \u2022 Member #{member.guild.member_count}")
        try:
            await ch.send(embed=embed)
            logger.info(f"Welcome sent for {member.display_name} in {member.guild.name}")
        except Exception as e:
            logger.warning(f"Welcome send error: {e}")

        role_id = cfg.get("autorole")
        if role_id:
            role = member.guild.get_role(int(role_id))
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except Exception as e:
                    logger.warning(f"Auto-role error: {e}")

        if cfg.get("dm_enabled") and cfg.get("dm_message"):
            try:
                dm_embed = discord.Embed(
                    description=_fill(cfg["dm_message"], member),
                    color=0x7c3aed
                )
                dm_embed.set_author(
                    name=f"Welcome to {member.guild.name}!",
                    icon_url=member.guild.icon.url if member.guild.icon else None
                )
                await member.send(embed=dm_embed)
            except Exception:
                pass

    async def _send_goodbye(self, member):
        cfg = await self._get_cfg(member.guild.id)

        ch_id = cfg.get("goodbye_channel") or cfg.get("welcome_channel")
        if ch_id:
            ch = member.guild.get_channel(int(ch_id))
        else:
            ch = _auto_channel(member.guild)

        if not ch:
            return

        if cfg.get("goodbye_message"):
            desc = _fill(cfg["goodbye_message"], member)
        else:
            ai_coder_msg = None
            try:
                ai_coder = self.bot.cogs.get("AICoder")
                if ai_coder:
                    msgs = ai_coder.get_generated("goodbye_messages")
                    if msgs:
                        ai_coder_msg = (random.choice(msgs)
                            .replace("{username}", member.display_name)
                            .replace("{server}", member.guild.name)
                            .replace("{count}", str(member.guild.member_count)))
            except Exception:
                pass

            if ai_coder_msg:
                desc = ai_coder_msg
            else:
                ai_msg = await self._ai_goodbye(member)
                if ai_msg:
                    desc = ai_msg.replace("{username}", member.display_name)
                else:
                    template = random.choice(GOODBYE_MSGS)
                    desc = (template
                        .replace("{username}", member.display_name)
                        .replace("{server}", member.guild.name)
                        .replace("{count}", str(member.guild.member_count))
                    )

        color = _parse_color(cfg.get("goodbye_color", "ef4444"), 0xef4444)
        embed = discord.Embed(description=desc, color=color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"{member.guild.name} \u2022 Goodbye")
        try:
            await ch.send(embed=embed)
        except Exception as e:
            logger.warning(f"Goodbye send error: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        logger.info(f"on_member_join fired: {member.display_name} in {member.guild.name}")
        await self._send_welcome(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        logger.info(f"on_member_remove fired: {member.display_name} in {member.guild.name}")
        await self._send_goodbye(member)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        cfg = await self._get_cfg(after.guild.id)
        promo_ch_id = cfg.get("promo_channel")
        watched_raw = cfg.get("promo_roles", "")
        if not promo_ch_id or not watched_raw:
            return
        watched = {r.strip().lower() for r in watched_raw.split(",") if r.strip()}
        new_roles = [r for r in after.roles if r not in before.roles]
        for role in new_roles:
            if role.name.lower() in watched:
                ch = after.guild.get_channel(int(promo_ch_id))
                if not ch:
                    return
                promo_template = cfg.get("promo_message", "")
                if not promo_template:
                    ai_msg = await _gemini(
                        f"Write a short Discord promotion announcement.\n"
                        f"Member: {after.display_name}\nNew role: {role.name}\nServer: {after.guild.name}\n"
                        f"1-2 sentences, use emojis, be hype and congratulatory.",
                        max_tokens=80
                    )
                    msg = ai_msg or f"\U0001f389 Congratulations {after.mention}! You've been promoted to **{role.name}**! Well deserved! \U0001f38a"
                else:
                    msg = (promo_template
                        .replace("{user}", after.mention)
                        .replace("{username}", after.display_name)
                        .replace("{role}", role.name)
                        .replace("{server}", after.guild.name)
                    )
                embed = discord.Embed(description=msg, color=0xf59e0b)
                embed.set_thumbnail(url=after.display_avatar.url)
                embed.set_footer(text=f"{after.guild.name} \u2022 Promotion")
                try:
                    await ch.send(embed=embed)
                except Exception as e:
                    logger.warning(f"Promo send error: {e}")
                break

    @app_commands.command(name="welcome-set", description="📢 Set the welcome channel and message")
    @app_commands.describe(channel="Channel for welcome messages", message="Custom message (leave blank for AI)", color="Hex color e.g. 57f287")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_set(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str = "", color: str = "57f287"):
        cfg = await self._get_cfg(ctx.guild.id)
        cfg.update({"welcome_channel": str(channel.id), "welcome_message": message, "welcome_color": color})
        await self._save_cfg(interaction.guild.id, cfg)
        note = "AI-generated messages enabled." if not message else "Custom message saved."
        await interaction.response.send_message(
            f"\u2705 Welcome \u2192 {channel.mention}\n{note}\nVariables: `{{user}}` `{{username}}` `{{server}}` `{{count}}`",
            ephemeral=True)

    @app_commands.command(name="goodbye-set", description="👋 Set the goodbye channel and message")
    @app_commands.describe(channel="Channel for goodbye messages", message="Custom message (leave blank for AI)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def goodbye_set(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str = ""):
        cfg = await self._get_cfg(ctx.guild.id)
        cfg.update({"goodbye_channel": str(channel.id), "goodbye_message": message})
        await self._save_cfg(interaction.guild.id, cfg)
        await interaction.response.send_message(f"\u2705 Goodbye \u2192 {channel.mention}", ephemeral=True)

    @app_commands.command(name="welcome-dm", description="📩 Set a DM message for new members")
    @app_commands.describe(message="DM message to send on join")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_dm(self, interaction: discord.Interaction, message: str):
        cfg = await self._get_cfg(ctx.guild.id)
        cfg["dm_enabled"] = True
        cfg["dm_message"] = message
        await self._save_cfg(interaction.guild.id, cfg)
        await interaction.response.send_message(f"\u2705 Join DM enabled.\nMessage: {message[:100]}", ephemeral=True)

    @app_commands.command(name="promo-set", description="🎉 Set promotion announcements channel")
    @app_commands.describe(channel="Channel for promo messages", roles="Comma-separated role names to watch")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def promo_set(self, interaction: discord.Interaction, channel: discord.TextChannel, roles: str):
        cfg = await self._get_cfg(ctx.guild.id)
        cfg.update({"promo_channel": str(channel.id), "promo_roles": roles})
        await self._save_cfg(interaction.guild.id, cfg)
        await interaction.response.send_message(f"\u2705 Promo announcements \u2192 {channel.mention}\nWatched roles: `{roles}`", ephemeral=True)

    @app_commands.command(name="autorole", description="🎭 Set auto-role for new members")
    @app_commands.describe(role="Role to give new members (leave blank to disable)")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole(self, interaction: discord.Interaction, role: discord.Role = None):
        cfg = await self._get_cfg(ctx.guild.id)
        if role:
            cfg["autorole"] = str(role.id)
            await self._save_cfg(interaction.guild.id, cfg)
            await interaction.response.send_message(f"\u2705 New members will get **{role.name}** on join.", ephemeral=True)
        else:
            cfg.pop("autorole", None)
            await self._save_cfg(interaction.guild.id, cfg)
            await interaction.response.send_message("\u2705 Auto-role disabled.", ephemeral=True)

    @app_commands.command(name="welcome-test", description="🧪 Send a test welcome message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_test(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self._send_welcome(interaction.user)
        await interaction.followup.send("\u2705 Test welcome sent!", ephemeral=True)

    @app_commands.command(name="goodbye-test", description="🧪 Send a test goodbye message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def goodbye_test(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self._send_goodbye(interaction.user)
        await interaction.followup.send("\u2705 Test goodbye sent!", ephemeral=True)

    @app_commands.command(name="welcome-status", description="📊 Show welcome system status")
    async def welcome_status(self, interaction: discord.Interaction):
        cfg = await self._get_cfg(interaction.guild.id)
        embed = discord.Embed(title="Welcome System Status", color=0x57f287)
        wch = interaction.guild.get_channel(int(cfg["welcome_channel"])) if cfg.get("welcome_channel") else None
        gch = interaction.guild.get_channel(int(cfg["goodbye_channel"])) if cfg.get("goodbye_channel") else None
        pch = interaction.guild.get_channel(int(cfg["promo_channel"])) if cfg.get("promo_channel") else None
        embed.add_field(name="Welcome Channel", value=wch.mention if wch else "Auto-detect", inline=True)
        embed.add_field(name="Goodbye Channel", value=gch.mention if gch else "Same as welcome", inline=True)
        embed.add_field(name="Promo Channel", value=pch.mention if pch else "Not set", inline=True)
        embed.add_field(name="Welcome Message", value=cfg.get("welcome_message") or "AI-generated", inline=False)
        embed.add_field(name="Goodbye Message", value=cfg.get("goodbye_message") or "AI-generated", inline=False)
        embed.add_field(name="Join DM", value="\u2705 Enabled" if cfg.get("dm_enabled") else "\u274c Disabled", inline=True)
        embed.add_field(name="Auto-Role", value=f"<@&{cfg['autorole']}>" if cfg.get("autorole") else "None", inline=True)
        embed.add_field(name="AI Messages", value="\u2705 Gemini" if GEMINI_API_KEY else "\u274c No API key (using fallback)", inline=True)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
