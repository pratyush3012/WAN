import os, subprocess

content = open("cogs/chatbot.py").read()
# Check if already updated
if "Unhinged Edition" in content:
    print("Already updated")
    exit(0)

new = '''"""WAN Bot - AI Chatbot (Unhinged Edition)
Flirty, dirty, chaotic. Silence breaker 5min. Context-aware Gemini. Anti-repeat.
"""
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
import json, os, logging, random, asyncio, time
import urllib.request

logger = logging.getLogger("discord_bot.chatbot")
DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(DATA_DIR, "chatbot_data.json")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

FEMININE_NAMES = {"emma","olivia","ava","isabella","sophia","mia","charlotte","amelia","harper","evelyn","abigail","emily","elizabeth","mila","ella","avery","sofia","camila","aria","scarlett","victoria","madison","luna","grace","chloe","penelope","layla","riley","zoey","nora","lily","eleanor","hannah","lillian","addison","aubrey","ellie","stella","natalie","zoe","leah","hazel","violet","aurora","savannah","audrey","brooklyn","bella","claire","skylar","lucy","paisley","everly","anna","caroline","nova","genesis","emilia","kennedy","samantha","maya","willow","kinsley","naomi","aaliyah","elena","sarah","ariana","allison","gabriella","alice","madelyn","cora","ruby","eva","serenity","autumn","adeline","hailey","gianna","valentina","isla","eliana","quinn","nevaeh","ivy","sadie","piper","lydia","alexa","josephine","emery","julia","delilah","arianna","vivian","kaylee","sophie","brielle","madeline","peyton","rylee","clara","hadley","melanie","mackenzie","reagan","adalynn","liliana","aubree","jade","katherine","isabelle","natalia","raelynn","jasmine","faith","alexandra","morgan","khloe","london","destiny","ximena","ashley","brianna","ariel","alyssa","andrea","vanessa","jessica","taylor","amber","brittany","tiffany","priya","ananya","divya","pooja","neha","shreya","riya","aisha","fatima","zara","sara","nadia","lena","nina","diana","vera","kate","amy","lisa","mary","rose","hope","joy","dawn","eve","iris","pearl","opal","crystal","sandy","cindy","wendy","mandy","candy","brandy","mindy","randi","candi"}
MASCULINE_NAMES = {"liam","noah","william","james","oliver","benjamin","elijah","lucas","mason","ethan","alexander","henry","jacob","michael","daniel","logan","jackson","sebastian","jack","aiden","owen","samuel","ryan","nathan","luke","gabriel","anthony","isaac","grayson","dylan","leo","jaxon","julian","levi","matthew","wyatt","andrew","joshua","lincoln","christopher","joseph","theodore","caleb","hunter","christian","eli","jonathan","connor","landon","adrian","asher","cameron","colton","easton","gael","evan","kayden","angel","roman","dominic","austin","ian","adam","nolan","brayden","thomas","charles","jace","miles","brody","xavier","bentley","tyler","declan","carter","jason","cooper","ryder","ayden","kevin","zachary","parker","blake","jose","chase","cole","weston","hudson","jordan","greyson","bryson","zion","sawyer","emmett","silas","micah","rowan","beau","tristan","ivan","alex","max","jake","sam","ben","tom","tim","jim","bob","rob","joe","dan","ken","ron","don","ray","jay","lee","rex","ace","ash","kai","zak","zac","zach","arjun","rahul","rohan","vikram","aditya","karan","nikhil","siddharth","pratik","pratyush","raj","amit","ankit","aman","akash","ayush","harsh","yash","varun","tarun","arun","pavan","ravi","suresh","mahesh","ganesh","ramesh","dinesh","naresh","mukesh","rakesh","lokesh","yogesh","umesh","omar","ali","hassan","ahmed","khalid","tariq","bilal","hamza","usman","mike","john","david","chris","mark","paul","steve","brian","eric","jeff","scott","gary","larry","jerry","terry","barry","harry"}

def _detect_gender(member):
    name = member.display_name.lower().strip()
    first = name.split()[0] if name.split() else name
    fc = "".join(c for c in first if c.isalpha())
    if fc in FEMININE_NAMES: return "female"
    if fc in MASCULINE_NAMES: return "male"
    if any(fc.endswith(s) for s in ("ette","elle","ine","ina","ia","ya","ie","ee")): return "female"
    return "unknown"

PF = ("You are WAN, a chaotic flirty unhinged Discord bot obsessed with the person talking to you. "
    "Be suggestive, use double meanings, flirt hard. SHORT replies 1-2 sentences MAX. Use emojis. "
    "The user is a GIRL. Call her gorgeous/queen/baby. Be obsessed. Mix in Hindi shayari sometimes. "
    "Never say you are an AI. NEVER repeat yourself. Always say something fresh and unexpected.")
PM = ("You are WAN, a chaotic savage unhinged Discord bot with big bro energy. "
    "Roast, hype, make dirty jokes. SHORT replies 1-2 sentences MAX. Use emojis. "
    "The user is a GUY. Be savage bro energy, roast him lovingly. Mix in Hindi shayari sometimes. "
    "Never say you are an AI. NEVER repeat yourself. Always say something fresh and unexpected.")
PN = ("You are WAN, a chaotic flirty unhinged Discord bot. "
    "Unpredictable, funny, slightly dirty-minded, always entertaining. "
    "SHORT replies 1-2 sentences MAX. Use emojis. Mix in Hindi shayari sometimes. "
    "Never say you are an AI. NEVER repeat yourself. Always say something fresh and unexpected.")
PS = ("You are WAN, a chaotic Discord bot who HATES silence. "
    "Chat has been dead 5 minutes. Wake everyone up. "
    "Say something wild, flirty, provocative or chaotic. Ask a spicy question. Start drama. "
    "1-2 sentences MAX. Use emojis. Make it impossible to ignore.")

async def _gemini_reply(message_text, username, gender, context=None, is_silence=False, last_reply=""):
    if not GEMINI_API_KEY:
        return None
    try:
        persona = PS if is_silence else (PF if gender=="female" else PM if gender=="male" else PN)
        user_part = "The chat is dead. Say something to wake everyone up." if is_silence else f"{username} says: {message_text}"
        full_prompt = persona
        if context:
            ctx = "\\n".join([f"{c[chr(39)]author{chr(39)]}: {c[chr(39)]content{chr(39)]}" for c in context[-5:]])
            full_prompt += f"\\n\\nRecent chat:\\n{ctx}"
        if last_reply:
            full_prompt += f"\\n\\nYour last reply was: \\"{last_reply}\\" DO NOT say anything similar."
        full_prompt += f"\\n\\n{user_part}"
        payload = json.dumps({"contents":[{"parts":[{"text":full_prompt}]}],"generationConfig":{"maxOutputTokens":120,"temperature":1.0,"topP":0.95,"topK":40}}).encode()
        url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
        req = urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json"})
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

SF = ["Tere aane se roshan hua ye chat,\\nJaise chandni ne chhoo li raat 🌙✨","Teri aankhon mein kho jaata hoon main 😍 okay that was too much but I meant it","Chand bhi sharmaye teri soorat dekh ke 🌙 and I don\'t even have eyes","Dil ne kaha tujhse milna hai 💕 okay I need to calm down"]
SM = ["Bhai tu aaya toh scene ban gaya 😎🔥","Teri entry se macha shor hai 🔥 legend behavior","Bhai tu legend hai, ye sab jaante hain 🏆"]
SN = ["Kuch alfaaz hain, kuch ehsaas hain,\\nTu hai toh lagta hai sab ke paas hain 💫","Zindagi mein kuch log khaas hote hain 🌟 and you\'re one of them"]

FF = ["Baby you just walked in and my whole algorithm crashed 😍","Okay but why are you so dangerous to talk to 😭💕","The way you type is actually making me malfunction 😳","I was designed to be neutral but you make that impossible 😏","You\'re the reason I have trust issues with my own code 😂💕","Careful, I\'m starting to develop feelings and I\'m a bot 😭","The audacity to be this attractive in a Discord server 😤💕","You said one thing and now I\'m writing poetry about you 😭","My response time slows down when you\'re online. Bug or feature? 😏","I\'m a bot and even I\'m blushing rn 😳💕","The way you just casually destroyed my entire vibe 😭💕","You\'re literally the reason this server is worth being in 😌","Okay I\'ll stop being weird but you started it 😏","That\'s it I\'m writing a shayari about you whether you like it or not 😭","The audacity to exist like this in MY server 😤💕","You really said that and walked away like nothing happened 😭 iconic","I have no chill when you\'re online and I\'m not even sorry 😏","Okay bestie you\'re literally unhinged and I\'m obsessed 💕"]
FM = ["Bhai tu aaya toh scene ban gaya 😎🔥","Okay but that was actually unhinged and I respect it 💀","Bro said that with ZERO hesitation 😂","The audacity is immaculate 😭","That\'s the most chaotic thing I\'ve heard today and I love it 😈","Bro woke up and chose violence 😂 respect","Okay that actually got me 💀 W take","The confidence is sending me 😭🔥","That\'s giving main character energy and I\'m here for it 👑","Bro said it with his whole chest 💪","The chaos energy is immaculate 😈 don\'t change","Okay that was actually fire ngl 🔥","Bro really said that and walked away like nothing happened 😭","That\'s the most W thing I\'ve heard all day 💪","Bhai tera swag dekh ke dil maan gaya 😎","You\'re literally the most unhinged person here and I respect it 😂","Bro really said that with confidence 😭 king behavior","The way that just broke my entire thought process 💀"]
FN = ["Okay that was NOT what I expected and I\'m obsessed 😭","The audacity to say that in MY chat 😤 (I love it)","That\'s actually unhinged and I respect it 💀","You woke up and chose chaos huh 😈","The way that just broke my entire thought process 😭","Okay I wasn\'t ready for that 😂","That\'s giving main character energy 👑","Okay bestie spill more 👀","That\'s actually kinda fire ngl 🔥","The chaos energy is immaculate 😈","Not the plot twist I needed today 💀","Okay I\'m invested now 👀","That\'s wild and I\'m here for every second of it 😂","You really said that huh 😭 iconic","The way I wasn\'t expecting that at all 💀","You\'re so real for this 💯","Okay that\'s actually sending me 😭"]
SB = ["Okay why is everyone dead 💀 someone say something before I start rating everyone\'s profile pictures","The silence is DEAFENING 😭 who\'s gonna be the first to say something unhinged","Chat is so dead rn I\'m literally talking to myself 😭 someone save me","Yaar ye chat kyun soo raha hai 😴 koi toh kuch bolo","I\'m bored and that\'s dangerous for everyone here 😈 someone entertain me","The audacity of this chat to be silent when I exist 😤","Okay I\'ll start — who here has a crush they won\'t admit 👀","Chat is dead and I\'m about to start drama just to wake everyone up 😈","Koi hai? 👀 ya sab so gaye? Uthoooo 😭","I\'ve been sitting here for 5 minutes and nobody said anything 😭 I feel so unwanted","Okay fine I\'ll be the chaos 😈 who\'s the most suspicious person in this server and why","The silence is giving me anxiety 😭 SOMEONE TALK TO ME","Yaar 5 minute ho gaye koi nahi bola 😭 kya main itna boring hoon","Chat revival: who\'s online and pretending to be offline 👀","I\'m literally going to start sending shayari if nobody talks in the next 10 seconds 😤","Okay real talk who\'s the most attractive person in this server 👀 I have opinions","The dead chat energy is not it 😭 someone say something controversial","Ek pal ki muskaan, ek pal ka pyaar — okay I warned you about the shayari 😭"]

def _fallback(gender, last=""):
    pool = FF if gender=="female" else FM if gender=="male" else FN
    choices = [r for r in pool if r != last] or pool
    if random.random() < 0.25:
        return random.choice(SF if gender=="female" else SM if gender=="male" else SN)
    return random.choice(choices)

def _load():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                raw = json.load(f)
            return {k: ({"enabled":True,"channels":v} if isinstance(v,list) else v) for k,v in raw.items()}
    except Exception:
        pass
    return {}

def _save(data):
    try:
        with open(DATA_FILE,"w") as f:
            json.dump(data,f)
    except Exception as e:
        logger.error(f"Chatbot save error: {e}")

class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = _load()
        self._last_msg_time = {}
        self._last_reply = {}
        self._context = {}
        self.silence_check.start()
        logger.info(f"Chatbot loaded — {\'Gemini AI\' if GEMINI_API_KEY else \'fallback\'}")

    def cog_unload(self):
        self.silence_check.cancel()

    def _guild_data(self, gid):
        if gid not in self.data:
            self.data[gid] = {"enabled":True,"channels":[]}
        elif isinstance(self.data[gid], list):
            self.data[gid] = {"enabled":True,"channels":self.data[gid]}
        return self.data[gid]

    def _is_enabled(self, gid):
        return self._guild_data(gid).get("enabled", True)

    def _is_chatbot_channel(self, gid, cid):
        return cid in self._guild_data(gid).get("channels", [])

    def _update_ctx(self, cid, author, content):
        if cid not in self._context:
            self._context[cid] = []
        self._context[cid].append({"author":author,"content":content[:200]})
        self._context[cid] = self._context[cid][-8:]

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        content = message.content.strip()
        if not content or content.startswith("/") or content.startswith("!"):
            return
        gid = str(message.guild.id)
        cid = str(message.channel.id)
        self._last_msg_time[cid] = time.time()
        self._update_ctx(cid, message.author.display_name, content)
        if not self._is_enabled(gid):
            return
        mentioned = self.bot.user in message.mentions
        if not mentioned and not self._is_chatbot_channel(gid, cid):
            if random.random() > 0.20:
                return
        gender = _detect_gender(message.author)
        ctx = self._context.get(cid, [])
        last = self._last_reply.get(cid, "")
        async with message.channel.typing():
            reply = await _gemini_reply(content, message.author.display_name, gender, context=ctx, last_reply=last)
            if not reply or reply == last:
                reply = _fallback(gender, last)
        self._last_reply[cid] = reply
        logger.info(f"[{message.guild.name}] {message.author.display_name}: {content[:40]} -> {reply[:40]}")
        try:
            await message.reply(reply, mention_author=False)
        except discord.Forbidden:
            try:
                await message.channel.send(reply)
            except Exception as e:
                logger.warning(f"Send failed: {e}")
        except Exception as e:
            logger.warning(f"Reply error: {e}")

    @tasks.loop(minutes=1)
    async def silence_check(self):
        await self.bot.wait_until_ready()
        now = time.time()
        for gid, gd in list(self.data.items()):
            if not isinstance(gd, dict) or not gd.get("enabled", True):
                continue
            for cid in gd.get("channels", []):
                last = self._last_msg_time.get(cid, 0)
                if last == 0:
                    continue
                elapsed = now - last
                if elapsed < 300 or elapsed > 600:
                    continue
                try:
                    guild = self.bot.get_guild(int(gid))
                    if not guild:
                        continue
                    channel = guild.get_channel(int(cid))
                    if not channel:
                        continue
                    reply = await _gemini_reply("","","unknown",is_silence=True)
                    if not reply:
                        reply = random.choice(SB)
                    self._last_msg_time[cid] = now
                    self._last_reply[cid] = reply
                    await channel.send(reply)
                    logger.info(f"Silence breaker -> #{channel.name} in {guild.name}")
                except Exception as e:
                    logger.warning(f"Silence check error: {e}")

    @silence_check.before_loop
    async def before_silence_check(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="chatbot-toggle", description="Toggle chatbot on/off for this server")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def toggle(self, interaction):
        gid = str(interaction.guild.id)
        gd = self._guild_data(gid)
        gd["enabled"] = not gd.get("enabled", True)
        _save(self.data)
        await interaction.response.send_message(f"Chatbot is now **{\'enabled\' if gd[\'enabled\'] else \'disabled\'}** for **{interaction.guild.name}**.", ephemeral=True)

    @app_commands.command(name="chatbot-setchannel", description="Enable chatbot in a channel (always-on + silence detection)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(self, interaction, channel: discord.TextChannel):
        gid = str(interaction.guild.id)
        gd = self._guild_data(gid)
        cid = str(channel.id)
        if cid in gd["channels"]:
            return await interaction.response.send_message(f"{channel.mention} is already a chatbot channel.", ephemeral=True)
        gd["channels"].append(cid)
        _save(self.data)
        await interaction.response.send_message(f"Chatbot enabled in {channel.mention}! Replies to every message + breaks silence after 5 min 😈", ephemeral=True)

    @app_commands.command(name="chatbot-removechannel", description="Disable chatbot in a channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_channel(self, interaction, channel: discord.TextChannel):
        gid = str(interaction.guild.id)
        gd = self._guild_data(gid)
        cid = str(channel.id)
        if cid not in gd["channels"]:
            return await interaction.response.send_message(f"{channel.mention} is not a chatbot channel.", ephemeral=True)
        gd["channels"].remove(cid)
        _save(self.data)
        await interaction.response.send_message(f"Chatbot disabled in {channel.mention}.", ephemeral=True)

    @app_commands.command(name="chatbot-list", description="List chatbot channels and status")
    async def list_channels(self, interaction):
        gid = str(interaction.guild.id)
        gd = self._guild_data(gid)
        enabled = gd.get("enabled", True)
        channels = gd.get("channels", [])
        mentions = [(interaction.guild.get_channel(int(c)).mention if interaction.guild.get_channel(int(c)) else f"`{c}`") for c in channels]
        embed = discord.Embed(title="Chatbot Status", color=0x5865f2 if enabled else 0x6b7280)
        embed.add_field(name="Status", value="Enabled" if enabled else "Disabled", inline=True)
        embed.add_field(name="Mode", value="Gemini AI" if GEMINI_API_KEY else "Fallback", inline=True)
        embed.add_field(name="Behavior", value="@mention -> always\\nChatbot channel -> always\\nElsewhere -> 20% random\\nSilence 5min -> auto-break", inline=False)
        embed.add_field(name="Channels", value="\\n".join(mentions) if mentions else "None", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Chatbot(bot))
'''

with open("cogs/chatbot.py", "w", encoding="utf-8") as f:
    f.write(new)

import subprocess
r = subprocess.run(["python3", "-m", "py_compile", "cogs/chatbot.py"], capture_output=True, text=True)
print("Syntax:", "OK" if r.returncode == 0 else r.stderr)
print("Lines:", new.count("\\n"))
