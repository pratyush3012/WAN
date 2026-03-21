"""Write welcome.py with Gemini AI messages + auto-channel detection"""
lines = []
def w(*a): lines.append("".join(str(x) for x in a))

w('"""')
w('WAN Bot - Welcome / Goodbye / Promotion System')
w('- Auto-detects welcome channel if none configured')
w('- Gemini AI generates unique welcome/goodbye messages')
w('- Gender-aware fallback pool (30+ messages each)')
w('- Promotion announcements on role gain')
w('- DM new members with server info')
w('"""')
w('import discord')
w('from discord import app_commands')
w('from discord.ext import commands')
w('import json, os, logging, random, asyncio')
w('import urllib.request')
w('from datetime import datetime, timezone')
w('')
w('logger = logging.getLogger("discord_bot.welcome")')
w('DATA_FILE = "welcome_data.json"')
w('GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")')
w('GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"')
w('')
w('')
w('async def _gemini(prompt: str, max_tokens: int = 120) -> str | None:')
w('    if not GEMINI_API_KEY:')
w('        return None')
w('    try:')
w('        payload = json.dumps({')
w('            "contents": [{"parts": [{"text": prompt}]}],')
w('            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.95}')
w('        }).encode()')
w('        url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"')
w('        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})')
w('        loop = asyncio.get_event_loop()')
w('        def _call():')
w('            with urllib.request.urlopen(req, timeout=8) as resp:')
w('                return json.loads(resp.read())')
w('        data = await loop.run_in_executor(None, _call)')
w('        return data["candidates"][0]["content"]["parts"][0]["text"].strip()')
w('    except Exception as e:')
w('        logger.warning(f"Gemini error in welcome: {e}")')
w('        return None')
w('')
w('')
w('FEMININE_NAMES = {')
w('    "emma","olivia","ava","isabella","sophia","mia","charlotte","amelia","harper","evelyn",')
w('    "abigail","emily","elizabeth","mila","ella","avery","sofia","camila","aria","scarlett",')
w('    "victoria","madison","luna","grace","chloe","penelope","layla","riley","zoey","nora",')
w('    "lily","eleanor","hannah","lillian","addison","aubrey","ellie","stella","natalie","zoe",')
w('    "leah","hazel","violet","aurora","savannah","audrey","brooklyn","bella","claire","skylar",')
w('    "lucy","paisley","everly","anna","caroline","nova","genesis","emilia","kennedy","samantha",')
w('    "maya","willow","kinsley","naomi","aaliyah","elena","sarah","ariana","allison","gabriella",')
w('    "alice","madelyn","cora","ruby","eva","serenity","autumn","adeline","hailey","gianna",')
w('    "valentina","isla","eliana","quinn","nevaeh","ivy","sadie","piper","lydia","alexa",')
w('    "priya","ananya","divya","pooja","neha","shreya","riya","aisha","fatima","zara",')
w('    "sara","nadia","lena","nina","diana","vera","kate","amy","lisa","mary","rose",')
w('    "hope","joy","dawn","eve","iris","pearl","opal","crystal","sandy","cindy","wendy",')
w('    "mandy","candy","brandy","mindy","randi","candi","jade","jasmine","faith","morgan",')
w('    "khloe","london","destiny","ximena","ashley","brianna","ariel","alyssa","andrea","vanessa"')
w('}')
w('MASCULINE_NAMES = {')
w('    "liam","noah","william","james","oliver","benjamin","elijah","lucas","mason","ethan",')
w('    "alexander","henry","jacob","michael","daniel","logan","jackson","sebastian","jack","aiden",')
w('    "owen","samuel","ryan","nathan","luke","gabriel","anthony","isaac","grayson","dylan",')
w('    "leo","jaxon","julian","levi","matthew","wyatt","andrew","joshua","lincoln","christopher",')
w('    "joseph","theodore","caleb","hunter","christian","eli","jonathan","connor","landon","adrian",')
w('    "asher","cameron","colton","easton","evan","kayden","roman","dominic","austin","ian",')
w('    "adam","nolan","thomas","charles","jace","miles","brody","xavier","tyler","declan",')
w('    "carter","jason","cooper","ryder","kevin","zachary","parker","blake","chase","cole",')
w('    "alex","max","jake","sam","ben","tom","tim","jim","bob","rob","joe","dan","ken",')
w('    "ron","don","ray","jay","lee","rex","ace","ash","kai","zak","zac","zach",')
w('    "arjun","rahul","rohan","vikram","aditya","karan","nikhil","siddharth","pratik","pratyush",')
w('    "raj","amit","ankit","aman","akash","ayush","harsh","yash","varun","tarun","arun",')
w('    "pavan","ravi","suresh","mahesh","ganesh","ramesh","dinesh","naresh","mukesh","rakesh",')
w('    "omar","ali","hassan","ahmed","khalid","tariq","bilal","hamza","usman",')
w('    "mike","john","david","chris","mark","paul","steve","brian","eric","jeff","scott","gary"')
w('}')
w('')
w('')
w('def _detect_gender(member: discord.Member) -> str:')
w('    name = member.display_name.lower().strip()')
w('    first = name.split()[0] if name.split() else name')
w('    fc = "".join(c for c in first if c.isalpha())')
w('    if fc in FEMININE_NAMES: return "female"')
w('    if fc in MASCULINE_NAMES: return "male"')
w('    if any(fc.endswith(s) for s in ("ette","elle","ine","ina","ia","ya","ie","ee")): return "female"')
w('    return "unknown"')
w('')
w('')
w('# ── Fallback message pools ────────────────────────────────────────────────')
w('WELCOME_F = [')
w('    "💕 A queen has entered the chat! Welcome {user} — you\'re member **#{count}** and we\'re already obsessed!",')
w('    "✨ {user} just walked in and honestly? The whole vibe shifted. Welcome to **{server}**! 👑",')
w('    "She arrived 🌸 {user} is here! **{server}** just got 10x better, welcome queen!",')
w('    "Careful everyone, {user} just joined and she looks dangerous 😈 Welcome to **{server}**!",')
w('    "The server was missing something... turns out it was you, {user}! Welcome 💫",')
w('    "{user} has entered the chat. Everyone act cool 😎 Welcome to **{server}**!",')
w('    "New member alert 🚨 {user} arrived! Say hi before she thinks we\'re boring 😂",')
w('    "{user} walked in like she owns the place. Honestly? Respect. Welcome! 💪",')
w('    "Hey {user}! Fair warning — we\'re a little chaotic here. You\'ll fit right in 😏",')
w('    "The stars aligned and brought {user} to **{server}**. Coincidence? We think not ✨",')
w('    "Roses are red, the server is lit, {user} just joined and we love it 💕",')
w('    "Plot twist: {user} just joined and now **{server}** is officially better 🎉",')
w('    "We don\'t know you yet {user}, but we already like you 😌 Welcome, queen!",')
w('    "{user} just dropped in! You\'re our **#{count}** member — make it count 👑",')
w('    "Tere aane se roshan hua ye server 🌙 Welcome {user}! We\'re so glad you\'re here 💕",')
w('    "The legend {user} has arrived! **{server}** will never be the same 🌟",')
w('    "Oh wow {user} is here 😍 Welcome to **{server}** — you\'re already our favorite!",')
w('    "Someone told me a queen was joining today 👑 Welcome {user}! They were right!",')
w('    "{user} just joined and I\'m already writing a shayari about it 😭 Welcome!",')
w('    "Welcome {user}! You\'re member **#{count}** and honestly we peaked today 💕",')
w(']')
w('WELCOME_M = [')
w('    "🔥 {user} just walked in! Welcome to **{server}** — you\'re member **#{count}**, legend!",')
w('    "Bhai {user} aa gaya! 😎 Welcome to **{server}** — scene ban gaya!",')
w('    "New player unlocked 🎮 {user} has joined **{server}**! Welcome to the squad!",')
w('    "Careful everyone, {user} just arrived and he looks dangerous 😈 Welcome!",')
w('    "The server was missing something... turns out it was you, {user}! Welcome 💫",')
w('    "{user} has entered the chat. Everyone act cool 😎 Welcome to **{server}**!",')
w('    "New member alert 🚨 {user} arrived! Say hi before he thinks we\'re boring 😂",')
w('    "{user} walked in like he owns the place. Honestly? Respect. Welcome! 💪",')
w('    "Hey {user}! Fair warning — we\'re a little chaotic here. You\'ll fit right in 😏",')
w('    "The stars aligned and brought {user} to **{server}**. Coincidence? We think not ✨",')
w('    "Plot twist: {user} just joined and now **{server}** is officially better 🎉",')
w('    "We don\'t know you yet {user}, but we already like you 😌 Welcome!",')
w('    "{user} just dropped in! You\'re our **#{count}** member — make it count 👑",')
w('    "Bhai {user} teri entry se macha shor hai 🔥 Welcome to **{server}**!",')
w('    "Player {user} has entered the game. **{server}** just got more interesting 🎮",')
w('    "The legend {user} has arrived! **{server}** will never be the same 🌟",')
w('    "Bro {user} is here 💪 Welcome to **{server}** — you\'re already one of us!",')
w('    "Someone told me a legend was joining today 👑 Welcome {user}! They were right!",')
w('    "{user} just joined and I\'m already hyped 🔥 Welcome to the crew!",')
w('    "Welcome {user}! You\'re member **#{count}** and honestly we peaked today 💪",')
w(']')
w('WELCOME_N = [')
w('    "✨ {user} just joined **{server}**! Welcome — you\'re member **#{count}**!",')
w('    "New member alert 🚨 {user} has arrived! Welcome to **{server}**!",')
w('    "{user} has entered the chat. Everyone act cool 😎 Welcome!",')
w('    "The server was missing something... turns out it was you, {user}! Welcome 💫",')
w('    "Plot twist: {user} just joined and now **{server}** is officially better 🎉",')
w('    "We don\'t know you yet {user}, but we already like you 😌 Welcome!",')
w('    "{user} just dropped in! You\'re our **#{count}** member — make it count 👑",')
w('    "Hey {user}! Fair warning — we\'re a little chaotic here. You\'ll fit right in 😏",')
w('    "The stars aligned and brought {user} to **{server}**. Coincidence? We think not ✨",')
w('    "Roses are red, the server is lit, {user} just joined and we love it 💕",')
w('    "Welcome {user}! You\'re member **#{count}** and we\'re glad you\'re here 🎉",')
w('    "The legend {user} has arrived! **{server}** will never be the same 🌟",')
w('    "Oh wow {user} is here! Welcome to **{server}** — you\'re already our favorite!",')
w('    "Someone told me a new member was joining today 👑 Welcome {user}!",')
w('    "{user} just joined and we\'re already excited 🔥 Welcome to the crew!",')
w(']')
w('GOODBYE_MSGS = [')
w('    "**{username}** has left the building 👋 We\'ll miss you (a little). **{server}** now has {count} members.",')
w('    "**{username}** dipped 💨 Take care out there! **{server}** has {count} members now.",')
w('    "And just like that, **{username}** was gone 😔 Until next time!",')
w('    "**{username}** left the server. The vibe took a small hit ngl 😔 ({count} members remain)",')
w('    "**{username}** has logged off from **{server}**. Until next time! 👋",')
w('    "Goodbye **{username}** 👋 You will be missed! ({count} members left)",')
w('    "**{username}** left 😢 Hope to see you back soon! **{server}** misses you already.",')
w('    "**{username}** has departed. Safe travels! 🌟 ({count} members remain)",')
w(']')


def _fill(template: str, member: discord.Member) -> str:
    return (template
        .replace("{user}", member.mention)
        .replace("{username}", member.display_name)
        .replace("{server}", member.guild.name)
        .replace("{count}", str(member.guild.member_count))
        .replace("{id}", str(member.id))
    )

def _parse_color(raw, default: int = 0x57f287) -> int:
    try:
        s = str(raw).strip().lstrip("#")
        return int(s, 16)
    except Exception:
        return default

def _auto_channel(guild: discord.Guild, keywords=("welcome","general","lobby","chat","main","arrival")) -> discord.TextChannel | None:
    """Find a suitable channel automatically if none configured."""
    for kw in keywords:
        for ch in guild.text_channels:
            if kw in ch.name.lower():
                perms = ch.permissions_for(guild.me)
                if perms.send_messages and perms.embed_links:
                    return ch
    # fallback: first channel bot can write to
    for ch in guild.text_channels:
        perms = ch.permissions_for(guild.me)
        if perms.send_messages and perms.embed_links:
            return ch
    return None


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
            with open(DATA_FILE, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Welcome save error: {e}")

    def _guild(self, gid) -> dict:
        key = str(gid)
        if key not in self.data:
            self.data[key] = {}
        return self.data[key]

    async def _ai_welcome(self, member: discord.Member, gender: str) -> str | None:
        """Generate a unique Gemini welcome message."""
        gender_ctx = {
            "female": "She is a girl. Be warm, flirty, welcoming. Call her queen/gorgeous.",
            "male": "He is a guy. Be hype, bro energy, welcoming. Call him legend/bro.",
            "unknown": "Gender unknown. Be warm and welcoming to everyone.",
        }.get(gender, "Be warm and welcoming.")
        prompt = (
            f"Write a short Discord welcome message for a new member.\n"
            f"Member name: {member.display_name}\n"
            f"Server name: {member.guild.name}\n"
            f"Member count: {member.guild.member_count}\n"
            f"{gender_ctx}\n"
            f"Rules: 1-2 sentences MAX. Use emojis. Be fun and hype. "
            f"Mention their name. Do NOT use markdown headers. "
            f"Make it feel personal and exciting, not generic."
        )
        return await _gemini(prompt, max_tokens=100)

    async def _ai_goodbye(self, member: discord.Member) -> str | None:
        """Generate a unique Gemini goodbye message."""
        prompt = (
            f"Write a short Discord goodbye message for a member who just left.\n"
            f"Member name: {member.display_name}\n"
            f"Server name: {member.guild.name}\n"
            f"Remaining members: {member.guild.member_count}\n"
            f"Rules: 1-2 sentences MAX. Use emojis. Be warm but a little sad. "
            f"Mention their name. Make it feel genuine."
        )
        return await _gemini(prompt, max_tokens=80)

    async def _send_welcome(self, member: discord.Member):
        cfg = self._guild(member.guild.id)
        gender = _detect_gender(member)

        # Find channel — configured or auto-detected
        ch_id = cfg.get("welcome_channel")
        if ch_id:
            ch = member.guild.get_channel(int(ch_id))
        else:
            ch = _auto_channel(member.guild)
            if ch:
                # Auto-save so we don't re-detect every time
                cfg["welcome_channel"] = str(ch.id)
                self._save()
                logger.info(f"Auto-detected welcome channel: #{ch.name} in {member.guild.name}")

        if not ch:
            logger.warning(f"No welcome channel found for {member.guild.name}")
            return

        # Generate message — AI first, fallback to pool
        if cfg.get("welcome_message"):
            # Custom message set by admin
            desc = _fill(cfg["welcome_message"], member)
            title = _fill(cfg.get("welcome_title", ""), member) or None
        else:
            # Try Gemini AI
            ai_msg = await self._ai_welcome(member, gender)
            if ai_msg:
                desc = ai_msg.replace("{user}", member.mention).replace("{username}", member.display_name)
                title = None
            else:
                # Fallback pool
                pool = WELCOME_F if gender == "female" else WELCOME_M if gender == "male" else WELCOME_N
                desc = _fill(random.choice(pool), member)
                title = None

        color = _parse_color(cfg.get("welcome_color", "57f287"), 0x57f287)
        embed = discord.Embed(description=desc, color=color)
        if title:
            embed.title = title
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Welcome to {member.guild.name} • Member #{member.guild.member_count}")
        try:
            await ch.send(embed=embed)
            logger.info(f"Welcome sent for {member.display_name} in {member.guild.name}")
        except Exception as e:
            logger.warning(f"Welcome send error: {e}")

        # Auto-role
        role_id = cfg.get("autorole")
        if role_id:
            role = member.guild.get_role(int(role_id))
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except Exception as e:
                    logger.warning(f"Auto-role error: {e}")

        # DM new member
        if cfg.get("dm_enabled") and cfg.get("dm_message"):
            try:
                dm_embed = discord.Embed(
                    description=_fill(cfg["dm_message"], member),
                    color=0x7c3aed
                )
                dm_embed.set_author(name=f"Welcome to {member.guild.name}!", icon_url=member.guild.icon.url if member.guild.icon else None)
                await member.send(embed=dm_embed)
            except Exception:
                pass  # DMs can be closed

    async def _send_goodbye(self, member: discord.Member):
        cfg = self._guild(member.guild.id)

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
        embed.set_footer(text=f"{member.guild.name} • Goodbye")
        try:
            await ch.send(embed=embed)
        except Exception as e:
            logger.warning(f"Goodbye send error: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        logger.info(f"on_member_join fired: {member.display_name} in {member.guild.name}")
        await self._send_welcome(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        logger.info(f"on_member_remove fired: {member.display_name} in {member.guild.name}")
        await self._send_goodbye(member)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Promotion announcements when a watched role is gained."""
        cfg = self._guild(after.guild.id)
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
                # Try AI promo message
                promo_template = cfg.get("promo_message", "")
                if not promo_template:
                    ai_msg = await _gemini(
                        f"Write a short Discord promotion announcement.\n"
                        f"Member: {after.display_name}\nNew role: {role.name}\nServer: {after.guild.name}\n"
                        f"1-2 sentences, use emojis, be hype and congratulatory.",
                        max_tokens=80
                    )
                    msg = ai_msg or f"🎉 Congratulations {after.mention}! You've been promoted to **{role.name}**! Well deserved! 🎊"
                else:
                    msg = (promo_template
                        .replace("{user}", after.mention)
                        .replace("{username}", after.display_name)
                        .replace("{role}", role.name)
                        .replace("{server}", after.guild.name)
                    )
                embed = discord.Embed(description=msg, color=0xf59e0b)
                embed.set_thumbnail(url=after.display_avatar.url)
                embed.set_footer(text=f"{after.guild.name} • Promotion")
                try:
                    await ch.send(embed=embed)
                except Exception as e:
                    logger.warning(f"Promo send error: {e}")
                break

    # ── Slash commands ─────────────────────────────────────────────────────────

    @app_commands.command(name="welcome-set", description="Set welcome channel and optional custom message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_set(self, interaction: discord.Interaction,
                          channel: discord.TextChannel,
                          message: str = "",
                          title: str = "",
                          color: str = "57f287"):
        cfg = self._guild(interaction.guild.id)
        cfg.update({
            "welcome_channel": str(channel.id),
            "welcome_message": message,
            "welcome_title": title,
            "welcome_color": color,
        })
        self._save()
        note = "AI-generated messages enabled (no custom message)." if not message else "Custom message saved."
        await interaction.response.send_message(
            f"✅ Welcome → {channel.mention}\n{note}\n"
            f"Variables: `{{user}}` `{{username}}` `{{server}}` `{{count}}`",
            ephemeral=True)

    @app_commands.command(name="goodbye-set", description="Set goodbye channel and optional custom message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def goodbye_set(self, interaction: discord.Interaction,
                          channel: discord.TextChannel,
                          message: str = "",
                          title: str = ""):
        cfg = self._guild(interaction.guild.id)
        cfg.update({"goodbye_channel": str(channel.id), "goodbye_message": message, "goodbye_title": title})
        self._save()
        await interaction.response.send_message(f"✅ Goodbye → {channel.mention}", ephemeral=True)

    @app_commands.command(name="welcome-dm", description="Set a DM message sent to new members on join")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_dm(self, interaction: discord.Interaction,
                         message: str,
                         enabled: bool = True):
        cfg = self._guild(interaction.guild.id)
        cfg["dm_enabled"] = enabled
        cfg["dm_message"] = message
        self._save()
        await interaction.response.send_message(
            f"✅ Join DM {'enabled' if enabled else 'disabled'}.\nMessage: {message[:100]}",
            ephemeral=True)

    @app_commands.command(name="promo-set", description="Set promotion announcements channel and watched roles")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def promo_set(self, interaction: discord.Interaction,
                        channel: discord.TextChannel,
                        roles: str,
                        message: str = ""):
        cfg = self._guild(interaction.guild.id)
        cfg.update({"promo_channel": str(channel.id), "promo_roles": roles, "promo_message": message})
        self._save()
        await interaction.response.send_message(
            f"✅ Promo announcements → {channel.mention}\nWatched roles: `{roles}`",
            ephemeral=True)

    @app_commands.command(name="autorole", description="Set a role to auto-assign when members join")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole(self, interaction: discord.Interaction, role: discord.Role = None):
        cfg = self._guild(interaction.guild.id)
        if role:
            cfg["autorole"] = str(role.id)
            self._save()
            await interaction.response.send_message(f"✅ New members will get **{role.name}** on join.", ephemeral=True)
        else:
            cfg.pop("autorole", None)
            self._save()
            await interaction.response.send_message("✅ Auto-role disabled.", ephemeral=True)

    @app_commands.command(name="welcome-test", description="Test your welcome message right now")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_test(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self._send_welcome(interaction.user)
        await interaction.followup.send("✅ Test welcome sent!", ephemeral=True)

    @app_commands.command(name="goodbye-test", description="Test your goodbye message right now")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def goodbye_test(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self._send_goodbye(interaction.user)
        await interaction.followup.send("✅ Test goodbye sent!", ephemeral=True)

    @app_commands.command(name="welcome-status", description="View current welcome/goodbye configuration")
    async def welcome_status(self, interaction: discord.Interaction):
        cfg = self._guild(interaction.guild.id)
        embed = discord.Embed(title="Welcome System Status", color=0x57f287)
        wch = interaction.guild.get_channel(int(cfg["welcome_channel"])) if cfg.get("welcome_channel") else None
        gch = interaction.guild.get_channel(int(cfg["goodbye_channel"])) if cfg.get("goodbye_channel") else None
        pch = interaction.guild.get_channel(int(cfg["promo_channel"])) if cfg.get("promo_channel") else None
        embed.add_field(name="Welcome Channel", value=wch.mention if wch else "Auto-detect", inline=True)
        embed.add_field(name="Goodbye Channel", value=gch.mention if gch else "Same as welcome", inline=True)
        embed.add_field(name="Promo Channel", value=pch.mention if pch else "Not set", inline=True)
        embed.add_field(name="Welcome Message", value=cfg.get("welcome_message") or "AI-generated", inline=False)
        embed.add_field(name="Goodbye Message", value=cfg.get("goodbye_message") or "AI-generated", inline=False)
        embed.add_field(name="Join DM", value="✅ Enabled" if cfg.get("dm_enabled") else "❌ Disabled", inline=True)
        embed.add_field(name="Auto-Role", value=f"<@&{cfg['autorole']}>" if cfg.get("autorole") else "None", inline=True)
        embed.add_field(name="AI Messages", value="✅ Gemini" if GEMINI_API_KEY else "❌ No API key (using fallback)", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Welcome(bot))


# ── Write the file ────────────────────────────────────────────────────────────
import ast

src = open(__file__, encoding="utf-8").read()
content = src.split("# ── Write the file")[0]
lines_raw = content.splitlines()
# Find start of actual cog code (after the script header)
start = 0
for i, l in enumerate(lines_raw):
    if l.strip().startswith('"""'):
        start = i
        break
final = "\n".join(lines_raw[start:])
with open("cogs/welcome.py", "w", encoding="utf-8") as f:
    f.write(final)
print(f"Written {len(final.splitlines())} lines")
import subprocess
r = subprocess.run(["python3", "-m", "py_compile", "cogs/welcome.py"], capture_output=True, text=True)
print("Syntax:", "OK" if r.returncode == 0 else r.stderr[:400])
