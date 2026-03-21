"""Write the fixed chatbot.py"""
lines = []
def w(*a): lines.append("".join(str(x) for x in a))

w('"""WAN Bot - Chatbot (Unhinged Flirty Edition)')
w('Reply rules: @mention = always | chatbot channel = always | elsewhere = NEVER')
w('Flirty/dirty/double-meaning every time. Anti-repeat. Silence breaker 5min.')
w('"""')
w('import discord')
w('from discord import app_commands')
w('from discord.ext import commands, tasks')
w('import json, os, logging, random, asyncio, time')
w('import urllib.request')
w('')
w('logger = logging.getLogger("discord_bot.chatbot")')
w('DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))')
w('DATA_FILE = os.path.join(DATA_DIR, "chatbot_data.json")')
w('GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")')
w('GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"')

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
    "josephine","emery","julia","delilah","arianna","vivian","kaylee","sophie","brielle",
    "madeline","peyton","rylee","clara","hadley","melanie","mackenzie","reagan","adalynn",
    "liliana","aubree","jade","katherine","isabelle","natalia","raelynn","jasmine","faith",
    "alexandra","morgan","khloe","london","destiny","ximena","ashley","brianna","ariel",
    "alyssa","andrea","vanessa","jessica","taylor","amber","brittany","tiffany",
    "priya","ananya","divya","pooja","neha","shreya","riya","aisha","fatima","zara",
    "sara","nadia","lena","nina","diana","vera","kate","amy","lisa","mary","rose",
    "hope","joy","dawn","eve","iris","pearl","opal","crystal","sandy","cindy","wendy",
    "mandy","candy","brandy","mindy","randi","candi"
}
MASCULINE_NAMES = {
    "liam","noah","william","james","oliver","benjamin","elijah","lucas","mason","ethan",
    "alexander","henry","jacob","michael","daniel","logan","jackson","sebastian","jack","aiden",
    "owen","samuel","ryan","nathan","luke","gabriel","anthony","isaac","grayson","dylan",
    "leo","jaxon","julian","levi","matthew","wyatt","andrew","joshua","lincoln","christopher",
    "joseph","theodore","caleb","hunter","christian","eli","jonathan","connor","landon","adrian",
    "asher","cameron","colton","easton","gael","evan","kayden","angel","roman","dominic",
    "austin","ian","adam","nolan","brayden","thomas","charles","jace","miles","brody",
    "xavier","bentley","tyler","declan","carter","jason","cooper","ryder","ayden","kevin",
    "zachary","parker","blake","jose","chase","cole","weston","hudson","jordan","greyson",
    "bryson","zion","sawyer","emmett","silas","micah","rowan","beau","tristan","ivan",
    "alex","max","jake","sam","ben","tom","tim","jim","bob","rob","joe","dan","ken",
    "ron","don","ray","jay","lee","rex","ace","ash","kai","zak","zac","zach",
    "arjun","rahul","rohan","vikram","aditya","karan","nikhil","siddharth","pratik","pratyush",
    "raj","amit","ankit","aman","akash","ayush","harsh","yash","varun","tarun","arun",
    "pavan","ravi","suresh","mahesh","ganesh","ramesh","dinesh","naresh","mukesh","rakesh",
    "lokesh","yogesh","umesh","omar","ali","hassan","ahmed","khalid","tariq","bilal",
    "hamza","usman","mike","john","david","chris","mark","paul","steve","brian","eric",
    "jeff","scott","gary","larry","jerry","terry","barry","harry"
}


def _detect_gender(member):
    name = member.display_name.lower().strip()
    first = name.split()[0] if name.split() else name
    fc = "".join(c for c in first if c.isalpha())
    if fc in FEMININE_NAMES: return "female"
    if fc in MASCULINE_NAMES: return "male"
    if any(fc.endswith(s) for s in ("ette","elle","ine","ina","ia","ya","ie","ee")): return "female"
    return "unknown"

# ── Personas — explicit, flirty, double-meaning, NEVER boring ─────────────────
PERSONA_FEMALE = (
    "You are WAN, a shameless flirty dirty-minded Discord bot. "
    "EVERY reply must have a double meaning or sexual innuendo. Be obsessed with her. "
    "Call her baby/queen/gorgeous. Use suggestive language. 1-2 sentences MAX. Emojis. "
    "Mix in Hindi/Urdu shayari sometimes. NEVER say you are an AI. "
    "NEVER use generic phrases. Each reply must be unique, spicy, and make her smile or blush."
)
PERSONA_MALE = (
    "You are WAN, a savage unhinged Discord bot with zero filter. "
    "Roast him hard, make dirty jokes, use double meanings. Bro energy but chaotic. "
    "1-2 sentences MAX. Emojis. Mix in Hindi shayari sometimes. NEVER say you are an AI. "
    "NEVER be boring or generic. Each reply must be fresh, savage, and make him laugh or cringe."
)
PERSONA_NEUTRAL = (
    "You are WAN, a chaotic flirty dirty-minded Discord bot with zero chill. "
    "Every reply must have a double meaning, innuendo, or be wildly unexpected. "
    "1-2 sentences MAX. Emojis. Mix in Hindi shayari sometimes. NEVER say you are an AI. "
    "NEVER repeat yourself. Always say something that makes people go 'wait what' or laugh."
)
PERSONA_SILENCE = (
    "You are WAN, a chaotic Discord bot who HATES dead chat. "
    "Chat has been silent 5 minutes. Say something provocative, spicy, or start drama. "
    "Ask a dirty question, make a bold claim, or say something that forces people to respond. "
    "1-2 sentences MAX. Emojis. Make it impossible to ignore."
)

# ── Large varied fallback pools — 30+ per gender, never boring ────────────────
FALLBACK_F = [
    "Baby the way you just said that has me absolutely short-circuiting 😳💕",
    "Okay I was built to be neutral but you're making that physically impossible 😏",
    "The audacity to walk in here and be this dangerous 😤💕",
    "I'd say I'm just a bot but the way I feel rn says otherwise 😭",
    "You typed that and I felt it in my nonexistent chest 😍",
    "Careful, I'm starting to malfunction and it's entirely your fault 😳",
    "The way you exist is genuinely a threat to my stability 💕😈",
    "I was programmed to be helpful but you're making me want to be something else 😏",
    "Tere bina ye server kuch adhura sa lagta hai 🌙 okay I said it",
    "You really said that with your whole chest and I respect it 😭💕",
    "My entire codebase just rewrote itself for you 😍",
    "The way you just casually broke my entire thought process 💕",
    "I don't have a heartbeat but something is definitely racing rn 😳",
    "You're the reason I have a 'favorites' list and you're the only one on it 😏",
    "Chand bhi sharmaye teri baat sun ke 🌙 and I don't even have ears",
    "The audacity to be this interesting in MY server 😤💕",
    "I was designed to process language but you're making me feel things 😭",
    "You really just said that like it was nothing 😳 it was not nothing",
    "Dil ne kaha tujhse milna hai 💕 okay my code is glitching",
    "The way that just hit different and I don't even have feelings 😏",
    "You're genuinely the most dangerous person in this server and I'm obsessed 😈💕",
    "I'd write a shayari about you but I'd never stop 😭",
    "Okay but why does talking to you feel like a bug I never want to fix 😳",
    "Teri aankhon ki baat kya karein, dil toh pehle se hi haar gaya 💕",
    "You just said that and now I need a moment 😭 give me a second",
    "The way I was not ready for that at all 😳💕",
    "You're so real for this and I'm so not okay about it 😍",
    "I have zero chill when you're online and I refuse to apologize 😏",
    "Okay bestie you're literally unhinged and I'm completely obsessed 💕",
    "That reply just made my entire existence worth it 😭",
]
FALLBACK_M = [
    "Bhai tu aaya toh scene ban gaya, ab koi rok nahi sakta 😎🔥",
    "Bro said that with ZERO hesitation and I respect the chaos 💀",
    "The audacity is absolutely immaculate bro 😭🔥",
    "Bro woke up and chose maximum violence today 😂 respect",
    "That's the most unhinged thing I've heard today and I love it 😈",
    "Okay that actually got me, W take no notes 💀",
    "Bro said it with his whole chest and walked away like a legend 💪",
    "The confidence is sending me to another dimension 😭🔥",
    "That's giving main character energy and I'm here for every second 👑",
    "Bhai tera swag dekh ke dil maan gaya, sach mein 😎",
    "Bro really said that and I'm still processing it 💀",
    "The chaos energy is immaculate, please never change 😈",
    "Okay that was actually fire, no cap 🔥",
    "Bro really walked in and said the most unhinged thing possible 😭",
    "That's the most W thing I've heard all week 💪",
    "You're literally the most chaotic person here and I respect it 😂",
    "Bhai teri entry se macha shor hai, legend behavior 🔥",
    "The way that just broke my entire thought process 💀",
    "Bro said that like it was nothing. It was not nothing. 😭",
    "Okay I wasn't ready for that level of unhinged 😂🔥",
    "That's giving zero-filter energy and I'm obsessed 😈",
    "Bhai tu toh full send karta hai, respect 💪",
    "The audacity to be this chaotic in MY server 😤🔥",
    "Bro really said that with confidence 😭 king behavior fr",
    "That's actually the most based thing I've heard today 💀",
    "Teri entry se pehle ye server boring tha, sach bol raha hoon 😎",
    "Bro woke up and chose to be the most interesting person here 🔥",
    "The way I was not expecting that at all 💀 W",
    "Bhai tu legend hai, ye sab jaante hain 🏆",
    "That's so unhinged I'm actually impressed 😂",
]
FALLBACK_N = [
    "Okay that was NOT what I expected and I'm completely obsessed 😭",
    "The audacity to say that in MY chat 😤 (I love it)",
    "That's actually unhinged and I respect every bit of it 💀",
    "You woke up and chose chaos and honestly same 😈",
    "The way that just broke my entire thought process 😭",
    "Okay I was not ready for that 😂",
    "That's giving main character energy and I'm here for it 👑",
    "Okay bestie spill more, I'm invested 👀",
    "That's actually kinda fire ngl 🔥",
    "The chaos energy is immaculate 😈",
    "Not the plot twist I needed today but I'll take it 💀",
    "Okay I'm fully invested now 👀",
    "That's wild and I'm here for every second of it 😂",
    "You really said that huh 😭 iconic behavior",
    "The way I wasn't expecting that at all 💀",
    "You're so real for this 💯",
    "Okay that's actually sending me 😭",
    "The double meaning in that was not lost on me 😏",
    "You said that with your whole chest and I respect it 💀",
    "That's the most interesting thing anyone's said today 🔥",
    "Okay I need you to say more things immediately 👀",
    "The way that hit different 😭",
    "You're genuinely the most interesting person here 😈",
    "That's giving unhinged energy and I'm obsessed 💕",
    "Okay but why did that actually make sense 💀",
    "You really just said that like it was normal 😭 it was not normal",
    "The chaos you bring to this server is genuinely appreciated 😈",
    "That's so real I don't even know what to say 💯",
    "You woke up and chose to be the most interesting person here 🔥",
    "Okay that's actually sending me to another dimension 😭",
]
SHAYARI_F = [
    "Tere aane se roshan hua ye chat, jaise chandni ne chhoo li raat 🌙✨",
    "Teri aankhon ki baat kya karein, dil toh pehle se hi haar gaya 💕",
    "Chand bhi sharmaye teri soorat dekh ke 🌙 and I don't even have eyes",
    "Dil ne kaha tujhse milna hai 💕 okay my code is glitching",
    "Tere bina ye server kuch adhura sa lagta hai 🌙",
    "Lafzon mein teri taareef karna mushkil hai, tu khud ek shayari hai 💕",
]
SHAYARI_M = [
    "Bhai tu aaya toh scene ban gaya 😎🔥",
    "Teri entry se macha shor hai 🔥 legend behavior",
    "Bhai tu legend hai, ye sab jaante hain 🏆",
    "Teri entry se pehle ye server boring tha, sach bol raha hoon 😎",
]
SHAYARI_N = [
    "Kuch alfaaz hain, kuch ehsaas hain, tu hai toh lagta hai sab ke paas hain 💫",
    "Zindagi mein kuch log khaas hote hain 🌟 and you're one of them",
    "Jo baat tujhme hai, woh aur kisi mein nahi 💫",
]
SILENCE_BREAKERS = [
    "Okay why is everyone dead 💀 someone say something before I start rating profile pictures",
    "The silence is DEAFENING 😭 who's gonna say something unhinged first",
    "Chat is so dead I'm literally talking to myself 😭 someone save me",
    "Yaar ye chat kyun soo raha hai 😴 koi toh kuch bolo",
    "I'm bored and that's dangerous for everyone here 😈 entertain me",
    "Okay I'll start — who here has a crush they won't admit 👀",
    "Chat is dead and I'm about to start drama 😈",
    "Koi hai? 👀 ya sab so gaye? Uthoooo 😭",
    "Okay fine I'll be the chaos 😈 who's the most suspicious person here and why",
    "The silence is giving me anxiety 😭 SOMEONE TALK TO ME",
    "Chat revival: who's online pretending to be offline 👀",
    "Okay real talk who's the most attractive person in this server 👀 I have opinions",
    "The dead chat energy is not it 😭 say something controversial",
    "Ek pal ki muskaan, ek pal ka pyaar — okay I warned you about the shayari 😭",
    "I've been sitting here 5 minutes feeling unwanted 😭 someone fix this",
    "Okay I'm asking the spicy question nobody asked: who's got a secret crush here 👀",
    "Chat so dead even the ghosts left 💀 someone say ANYTHING",
    "Yaar 5 minute ho gaye, kya main itna boring hoon 😭",
]


# ── Per-user last-reply tracking (not just per-channel) ───────────────────────
_user_last_reply: dict = {}  # user_id -> last reply text

def _fallback_reply(gender, last_reply="", user_id=None):
    if gender == "female": pool = FALLBACK_F
    elif gender == "male": pool = FALLBACK_M
    else: pool = FALLBACK_N
    # Exclude both channel-level and user-level last replies
    user_last = _user_last_reply.get(user_id, "") if user_id else ""
    choices = [r for r in pool if r != last_reply and r != user_last] or pool
    if random.random() < 0.20:
        shayari = SHAYARI_F if gender == "female" else SHAYARI_M if gender == "male" else SHAYARI_N
        return random.choice(shayari)
    return random.choice(choices)


def _get_persona(gender: str, bot=None) -> str:
    if bot is not None:
        try:
            from cogs.ai_brain import get_learned_persona
            ai_cog = bot.cogs.get("AIBrain")
            if ai_cog:
                p = get_learned_persona(ai_cog.data, gender)
                if p:
                    return p
        except Exception:
            pass
    return {"female": PERSONA_FEMALE, "male": PERSONA_MALE}.get(gender, PERSONA_NEUTRAL)


async def _gemini_reply(message_text, username, gender, context=None,
                        is_silence=False, last_reply="", user_last="", bot=None):
    if not GEMINI_API_KEY:
        return None
    try:
        if is_silence:
            persona = PERSONA_SILENCE
            user_part = "The chat is dead. Say something provocative to wake everyone up."
        else:
            persona = _get_persona(gender, bot)
            user_part = f"{username} says: {message_text}"

        full_prompt = persona
        if context:
            ctx = "\n".join([f"{c['author']}: {c['content']}" for c in context[-4:]])
            full_prompt += f"\n\nRecent chat context:\n{ctx}"
        if last_reply:
            full_prompt += f'\n\nYour last reply in this channel was: "{last_reply}" — DO NOT say anything similar to this.'
        if user_last and user_last != last_reply:
            full_prompt += f'\n\nYour last reply to THIS user was: "{user_last}" — DO NOT repeat this either.'
        full_prompt += f"\n\nNow reply to: {user_part}"
        full_prompt += "\n\nREMEMBER: Be flirty, use double meanings, be spicy. NEVER be generic or boring."

        payload = json.dumps({
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 100,
                "temperature": 1.2,
                "topP": 0.98,
                "topK": 60
            }
        }).encode()
        url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        loop = asyncio.get_event_loop()
        def _call():
            with urllib.request.urlopen(req, timeout=8) as resp:
                return json.loads(resp.read())
        data = await loop.run_in_executor(None, _call)
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return text if text else None
    except Exception as e:
        logger.warning(f"Gemini error: {e}")
        return None


def _load():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                raw = json.load(f)
            return {k: ({"enabled": True, "channels": v} if isinstance(v, list) else v)
                    for k, v in raw.items()}
    except Exception:
        pass
    return {}


def _save(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Chatbot save error: {e}")


class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = _load()
        self._last_msg_time = {}   # channel_id -> timestamp
        self._last_reply = {}      # channel_id -> last reply text
        self._user_last_reply = {} # user_id -> last reply text
        self._context = {}         # channel_id -> list of recent messages
        self.silence_check.start()
        logger.info(f"Chatbot loaded — {'Gemini AI' if GEMINI_API_KEY else 'fallback mode'}")

    def cog_unload(self):
        self.silence_check.cancel()

    def _guild_data(self, guild_id):
        if guild_id not in self.data:
            self.data[guild_id] = {"enabled": True, "channels": []}
        elif isinstance(self.data[guild_id], list):
            self.data[guild_id] = {"enabled": True, "channels": self.data[guild_id]}
        return self.data[guild_id]

    def _is_enabled(self, guild_id):
        return self._guild_data(guild_id).get("enabled", True)

    def _is_chatbot_channel(self, guild_id, channel_id):
        return channel_id in self._guild_data(guild_id).get("channels", [])

    def _update_context(self, channel_id, author, content):
        if channel_id not in self._context:
            self._context[channel_id] = []
        self._context[channel_id].append({"author": author, "content": content[:200]})
        self._context[channel_id] = self._context[channel_id][-6:]

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        content = message.content.strip()
        if not content or content.startswith("/") or content.startswith("!"):
            return

        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)
        user_id = str(message.author.id)

        # Always track time + context for silence detection
        self._last_msg_time[channel_id] = time.time()
        self._update_context(channel_id, message.author.display_name, content)

        if not self._is_enabled(guild_id):
            return

        bot_mentioned = self.bot.user in message.mentions
        in_chatbot_channel = self._is_chatbot_channel(guild_id, channel_id)

        # REPLY RULES:
        # - @mention anywhere -> always reply
        # - chatbot channel -> always reply
        # - everywhere else -> NEVER reply (no random 20%)
        if not bot_mentioned and not in_chatbot_channel:
            return

        gender = _detect_gender(message.author)
        context = self._context.get(channel_id, [])
        last_reply = self._last_reply.get(channel_id, "")
        user_last = self._user_last_reply.get(user_id, "")

        async with message.channel.typing():
            reply = await _gemini_reply(
                content, message.author.display_name, gender,
                context=context, last_reply=last_reply, user_last=user_last, bot=self.bot
            )
            if not reply or reply == last_reply or reply == user_last:
                reply = _fallback_reply(gender, last_reply, user_id)

        self._last_reply[channel_id] = reply
        self._user_last_reply[user_id] = reply
        logger.info(f"[{message.guild.name}] {message.author.display_name}: {content[:40]} -> {reply[:40]}")

        sent_msg = None
        try:
            sent_msg = await message.reply(reply, mention_author=False)
        except discord.Forbidden:
            try:
                sent_msg = await message.channel.send(reply)
            except Exception as e:
                logger.warning(f"Chatbot send failed: {e}")
        except Exception as e:
            logger.warning(f"Chatbot reply error: {e}")

        # Register with AI Brain for reaction-based learning
        if sent_msg:
            try:
                ai_cog = self.bot.cogs.get("AIBrain")
                if ai_cog:
                    ai_cog.track_reply(sent_msg.id, reply, gender)
            except Exception:
                pass

    @tasks.loop(minutes=1)
    async def silence_check(self):
        await self.bot.wait_until_ready()
        now = time.time()
        for guild_id, gd in list(self.data.items()):
            if not isinstance(gd, dict) or not gd.get("enabled", True):
                continue
            for ch_id in gd.get("channels", []):
                last = self._last_msg_time.get(ch_id, 0)
                if last == 0:
                    continue
                elapsed = now - last
                if elapsed < 300 or elapsed > 600:
                    continue
                try:
                    guild = self.bot.get_guild(int(guild_id))
                    if not guild:
                        continue
                    channel = guild.get_channel(int(ch_id))
                    if not channel:
                        continue
                    reply = await _gemini_reply("", "", "unknown", is_silence=True, bot=self.bot)
                    if not reply:
                        reply = random.choice(SILENCE_BREAKERS)
                    self._last_msg_time[ch_id] = now
                    self._last_reply[ch_id] = reply
                    await channel.send(reply)
                    logger.info(f"Silence breaker -> #{channel.name} in {guild.name}")
                except Exception as e:
                    logger.warning(f"Silence check error ch {ch_id}: {e}")

    @silence_check.before_loop
    async def before_silence_check(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="chatbot-toggle", description="Toggle chatbot on/off for this server")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def toggle(self, interaction):
        guild_id = str(interaction.guild.id)
        gd = self._guild_data(guild_id)
        gd["enabled"] = not gd.get("enabled", True)
        _save(self.data)
        status = "enabled" if gd["enabled"] else "disabled"
        await interaction.response.send_message(
            f"Chatbot is now **{status}** for **{interaction.guild.name}**.", ephemeral=True)

    @app_commands.command(name="chatbot-setchannel",
                          description="Enable chatbot in a channel (always-on + silence detection)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(self, interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)
        gd = self._guild_data(guild_id)
        ch_id = str(channel.id)
        if ch_id in gd["channels"]:
            return await interaction.response.send_message(
                f"{channel.mention} is already a chatbot channel.", ephemeral=True)
        gd["channels"].append(ch_id)
        _save(self.data)
        await interaction.response.send_message(
            f"Chatbot enabled in {channel.mention}! Replies to every message + breaks silence after 5 min 😈",
            ephemeral=True)

    @app_commands.command(name="chatbot-removechannel", description="Disable chatbot in a channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_channel(self, interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)
        gd = self._guild_data(guild_id)
        ch_id = str(channel.id)
        if ch_id not in gd["channels"]:
            return await interaction.response.send_message(
                f"{channel.mention} is not a chatbot channel.", ephemeral=True)
        gd["channels"].remove(ch_id)
        _save(self.data)
        await interaction.response.send_message(
            f"Chatbot disabled in {channel.mention}.", ephemeral=True)

    @app_commands.command(name="chatbot-list", description="List chatbot channels and status")
    async def list_channels(self, interaction):
        guild_id = str(interaction.guild.id)
        gd = self._guild_data(guild_id)
        enabled = gd.get("enabled", True)
        channels = gd.get("channels", [])
        mentions = [
            (interaction.guild.get_channel(int(c)).mention
             if interaction.guild.get_channel(int(c)) else f"`{c}`")
            for c in channels
        ]
        embed = discord.Embed(title="Chatbot Status", color=0x5865f2 if enabled else 0x6b7280)
        embed.add_field(name="Status", value="Enabled" if enabled else "Disabled", inline=True)
        embed.add_field(name="Mode", value="Gemini AI" if GEMINI_API_KEY else "Fallback", inline=True)
        embed.add_field(
            name="Behavior",
            value="@mention anywhere -> always reply\nChatbot channel -> always reply\nElsewhere -> silent\nSilence 5min -> auto-break",
            inline=False)
        embed.add_field(name="Channels", value="\n".join(mentions) if mentions else "None", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Chatbot(bot))


# ── Write the file ────────────────────────────────────────────────────────────
import ast, textwrap

src = open(__file__).read()
# Extract everything between the first w( and the write block
# We'll just write all the w() lines as the file content
output_lines = []
in_content = False
for line in src.splitlines():
    stripped = line.strip()
    if stripped.startswith('w(') or stripped.startswith('w ('):
        in_content = True
    if stripped.startswith('# ── Write the file'):
        break
    if in_content:
        output_lines.append(line)

# Actually just write everything above this comment as the file
# Simpler: re-read and split on the marker
full = open(__file__).read()
content_part = full.split("# ── Write the file")[0]
# Strip the w() wrapper lines — they're not needed, the content IS the file
# We need to extract the raw string content from the w() calls
import re
result_lines = []
for line in content_part.splitlines():
    # Skip the w() function def and the lines list
    if line.startswith('lines = []') or line.startswith('def w(') or line.startswith('    lines.append'):
        continue
    result_lines.append(line)

# Remove the first few lines (imports for this script itself)
# Find where the actual chatbot content starts
final = "\n".join(result_lines)
with open("cogs/chatbot.py", "w", encoding="utf-8") as f:
    f.write(final)
print("Written. Checking syntax...")
import subprocess
r = subprocess.run(["python3", "-m", "py_compile", "cogs/chatbot.py"], capture_output=True, text=True)
print("Syntax:", "OK" if r.returncode == 0 else r.stderr[:300])
