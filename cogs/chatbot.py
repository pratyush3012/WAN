"""
WAN Bot - AI Chatbot Cog
Uses Google Gemini (free tier) for smart replies.
Falls back to keyword/gender-aware replies if no API key set.
Set GEMINI_API_KEY in .env to enable AI mode.
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging, random, re, asyncio
import urllib.request

logger = logging.getLogger('discord_bot.chatbot')

DATA_DIR = os.getenv('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(DATA_DIR, 'chatbot_data.json')

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'

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
    'mary','rose','hope','joy','dawn','eve','iris','pearl','opal','crystal',
    'sandy','cindy','wendy','mandy','candy','brandy','mindy','randi','candi',
}

MASCULINE_NAMES = {
    'liam','noah','william','james','oliver','benjamin','elijah','lucas','mason',
    'ethan','alexander','henry','jacob','michael','daniel','logan','jackson',
    'sebastian','jack','aiden','owen','samuel','ryan','nathan','luke','gabriel',
    'anthony','isaac','grayson','dylan','leo','jaxon','julian','levi','matthew',
    'wyatt','andrew','joshua','lincoln','christopher','joseph','theodore','caleb',
    'hunter','christian','eli','jonathan','connor','landon','adrian','asher',
    'cameron','colton','easton','gael','evan','kayden','angel','roman',
    'dominic','austin','ian','adam','nolan','brayden','thomas','charles','jace',
    'miles','brody','xavier','bentley','tyler','declan','carter','jason','cooper',
    'ryder','ayden','kevin','zachary','parker','blake','jose','chase','cole',
    'weston','hudson','jordan','greyson','bryson','zion','sawyer','emmett',
    'silas','micah','rowan','beau','tristan','ivan','alex','max','jake','sam',
    'ben','tom','tim','jim','bob','rob','joe','dan','ken','ron','don','ray',
    'jay','lee','rex','ace','ash','kai','zak','zac','zach',
    'arjun','rahul','rohan','vikram','aditya','karan','nikhil','siddharth',
    'pratik','pratyush','raj','amit','ankit','aman','akash','ayush','harsh',
    'yash','varun','tarun','arun','pavan','ravi','suresh','mahesh','ganesh',
    'ramesh','dinesh','naresh','mukesh','rakesh','lokesh','yogesh','umesh',
    'omar','ali','hassan','ahmed','khalid','tariq','bilal','hamza','usman',
    'mike','john','david','chris','mark','paul','steve','brian','eric',
    'jeff','scott','gary','larry','jerry','terry','barry','harry',
}

def _detect_gender(member):
    name = member.display_name.lower().strip()
    first = name.split()[0] if name.split() else name
    first_clean = ''.join(c for c in first if c.isalpha())
    if first_clean in FEMININE_NAMES:
        return 'female'
    if first_clean in MASCULINE_NAMES:
        return 'male'
    if any(first_clean.endswith(s) for s in ('ette','elle','ine','ina','ia','ya','ie','ee')):
        return 'female'
    return 'unknown'

BOT_PERSONA = """You are WAN, a fun, witty, flirty Discord bot with a big personality.
Reply to messages in a Discord server chat. Keep replies SHORT (1-2 sentences max).
Be casual, use emojis, be entertaining. Never be rude or offensive.
Never say you are an AI or mention Google. Just vibe like a fun friend."""

async def _gemini_reply(message_text, username, gender):
    if not GEMINI_API_KEY:
        return None
    try:
        if gender == 'female':
            hint = f'(User {username} is female — be flirty, sweet, call them queen/gorgeous)'
        elif gender == 'male':
            hint = f'(User {username} is male — be cool, hype them up, bro energy)'
        else:
            hint = f'(User {username} — be fun and neutral)'
        prompt = f"{BOT_PERSONA}\n{hint}\n\n{username} says: {message_text}"
        payload = json.dumps({
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'maxOutputTokens': 80, 'temperature': 0.95}
        }).encode()
        url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        loop = asyncio.get_event_loop()
        def _call():
            with urllib.request.urlopen(req, timeout=8) as resp:
                return json.loads(resp.read())
        data = await loop.run_in_executor(None, _call)
        text = data['candidates'][0]['content']['parts'][0]['text'].strip()
        return text if text else None
    except Exception as e:
        logger.warning(f"Gemini API error: {e}")
        return None

KEYWORD_REPLIES = {
    r'\b(hi|hey|hello|sup|yo|hiya|howdy|heyyy|heyy|hai)\b': {
        'female': ["Hey gorgeous 😏 look who showed up~","Hiii bestie 💕 you just made this chat better!","Oh hey! I was literally just thinking about you 👀","Heyyy~ don't be a stranger 😌 we missed you!"],
        'male':   ["Yo what's good 😎 look who showed up!","Hey bro! You just made this chat way more interesting 🔥","What's up man 😊 good to see you!","Oh look who's here 👀 what's the move?"],
        'unknown':["Hey hey 😏 look who decided to show up~","Hi there! You just made this chat 10x better 💫","Oh hey! I was literally just thinking about you 👀"],
    },
    r'\b(how are you|how r u|hru|wyd|how\'?s it going)\b': {
        'female': ["Better now that you're here 😏 how are YOU though?","I was bored until you showed up 😌 now I'm great~","Great now! What about you, gorgeous? 😊"],
        'male':   ["Better now that you're here bro 😏 you?","Honestly? Chilling. You? 😎","Great! What about you man? 😊"],
        'unknown':["Better now that you're here 😏","Just vibing, waiting for someone interesting. Found one 👀"],
    },
    r'\b(good night|gn|goodnight|going to sleep|going to bed)\b': {
        'female': ["Goodnight gorgeous~ sweet dreams 😏💕","Sleep well queen! I'll be here when you wake up 🌙"],
        'male':   ["Goodnight bro~ sleep well 🌙","GN man! Rest up ��"],
        'unknown':["Goodnight~ don't let the good dreams be too good without me 😏","Sleep well! I'll be here when you wake up 🌙"],
    },
    r'\b(good morning|gm|morning|rise and shine|just woke up)\b': {
        'female': ["Good morning sunshine ☀️ Looking gorgeous already I bet~","GM queen! The server is alive now that you're here 😌💕"],
        'male':   ["Good morning bro ☀️ you're up early!","GM! Ready to grind today? 💪"],
        'unknown':["Good morning sunshine ☀️ you're up early!","GM! The server is officially alive now that you're here 😌"],
    },
    r'\b(bye|goodbye|cya|see ya|later|gtg|gotta go)\b': {
        'female': ["Nooo don't leave 😭 come back soon gorgeous!","Bye queen! Don't be a stranger 👋💕"],
        'male':   ["Nooo don't leave 😭 come back soon bro!","Bye man! Don't be a stranger 👋"],
        'unknown':["Nooo don't leave 😭 come back soon!","Bye! Don't be a stranger 👋"],
    },
    r'\b(i love you|i like you|i miss you|i\'?m? in love)\b': {
        'female': ["Careful, I might start believing you 😏 but I love you more~","I love you too, don't tell the other members 🤫💕"],
        'male':   ["Bro 😂 okay okay I love you too man","I love you too bro, no cap 🤝"],
        'unknown':["Careful, I might start believing you 😏","I love you too, don't tell the other members 🤫"],
    },
    r'\b(bored|boring|so bored|i\'?m? bored|ugh)\b': [
        "Bored? Talk to me, I'm literally always here 😌",
        "Boredom is just your brain asking for chaos. Let's provide that 😈",
        "Tell me something random! I dare you 👀",
    ],
    r'\b(thanks|thank you|ty|thx|tysm)\b': [
        "Anytime! That's literally what I'm here for 😊","You're so welcome~ 💕",
        "No need to thank me, just keep talking to me 😏",
    ],
    r'\b(lol|lmao|lmfao|haha|hahaha|hehe|💀|😂)\b': [
        "Right?? 😂","I'm crying 💀","LMAO same 😭","Okay that actually got me 😂","I can't 😭😭",
    ],
    r'\b(i\'?m? sad|feeling down|not okay|not ok|i\'?m? upset|i\'?m? crying|depressed)\b': [
        "Hey, I'm here 💙 What's going on?","Aw no 😔 You okay? Talk to me.",
        "Sending virtual hugs your way 🤗 It'll get better.",
    ],
    r'\b(roast me|fight me|come at me|dare me)\b': [
        "You want a roast? Your WiFi password is probably 'password123' 😂",
        "Roast incoming: you talk to a Discord bot for fun. (So do I though 🤝)",
    ],
    r'\b(food|hungry|eating|pizza|burger|snack|lunch|dinner|breakfast)\b': [
        "Okay now I'm jealous 😭 enjoy!","You're eating without me?? 😤","Okay but what are you having? 👀",
    ],
    r'\b(game|gaming|playing|minecraft|roblox|valorant|fortnite|gta|cod)\b': [
        "Ooh what are you playing? 👀","Gaming hours? Let's go 🎮","Okay but are you winning? 😏",
    ],
    r'\b(wow|omg|oh my god|no way|wtf|bruh)\b': [
        "RIGHT?? 😭","I know I know 😂","Exactly my reaction 💀","The audacity 😭","Bruh 💀",
    ],
}

GENERIC_FEMALE = ["Interesting... tell me more gorgeous 👀","Okay but that's actually a vibe 😌","I was NOT expecting that 😂 you're so random~","You're something else, you know that? 😏","The audacity 😭 I love it queen","Okay real talk though, you're hilarious 😂","That's giving main character energy 👑","Slay honestly 💅","You're literally unhinged and I respect it 😂","Okay queen we see you 👑","The chaos energy is immaculate 😈","You woke up and chose violence huh 😂","That's actually kinda fire ngl 🔥","You're iconic and you know it 👑","I can't with you 😭","This is why you're my favorite 😌"]
GENERIC_MALE   = ["Interesting... tell me more bro 👀","Okay but that's actually a vibe 😌","I was NOT expecting that 😂","You're something else, you know that? 😏","The audacity 😭 I love it","Okay real talk though, you're funny 😂","That's giving main character energy 👑","W take honestly 💪","You're literally unhinged and I respect it 😂","Okay we see you bro 👀","The chaos energy is immaculate 😈","You woke up and chose violence huh 😂","That's actually kinda fire ngl 🔥","Bro said that with confidence 😂","I can't with you 😭","This is why you're my favorite 😌"]
GENERIC_NEUTRAL= ["Interesting... tell me more 👀","Okay but that's actually a vibe 😌","I was NOT expecting that 😂","You're something else, you know that? 😏","The audacity 😭 I love it","Okay real talk though, you're funny 😂","That's giving main character energy 👑","You're literally unhinged and I respect it 😂","The chaos energy is immaculate 😈","You woke up and chose violence huh 😂","That's actually kinda fire ngl 🔥","I can't with you 😭","This is why you're my favorite 😌","Not the plot twist I needed today 💀","Okay bestie spill 👀","You're so real for this 💯"]

def _keyword_reply(content, gender):
    lower = content.lower()
    matched = []
    for pattern, replies in KEYWORD_REPLIES.items():
        if re.search(pattern, lower):
            if isinstance(replies, dict):
                pool = replies.get(gender) or replies.get('unknown') or []
                matched.extend(pool)
            else:
                matched.extend(replies)
    if matched:
        return random.choice(matched)
    if gender == 'female':
        return random.choice(GENERIC_FEMALE)
    elif gender == 'male':
        return random.choice(GENERIC_MALE)
    return random.choice(GENERIC_NEUTRAL)

def _load():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Chatbot save error: {e}")

class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = _load()
        mode = "AI (Gemini)" if GEMINI_API_KEY else "keyword fallback"
        logger.info(f"Chatbot loaded — mode: {mode} — file: {DATA_FILE}")

    def _is_chatbot_channel(self, guild_id, channel_id):
        return channel_id in self.data.get(guild_id, [])

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        content = message.content.strip()
        if not content or content.startswith('/') or content.startswith('!'):
            return
        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)
        if not self._is_chatbot_channel(guild_id, channel_id):
            return
        logger.info(f"Chatbot: {message.guild.name} #{message.channel.name} | {message.author}: {content[:60]}")
        gender = _detect_gender(message.author)
        reply = await _gemini_reply(content, message.author.display_name, gender)
        if not reply:
            reply = _keyword_reply(content, gender)
        try:
            await message.reply(reply, mention_author=False)
        except discord.Forbidden:
            try:
                await message.channel.send(reply)
            except Exception as e:
                logger.warning(f"Chatbot send failed: {e}")
        except Exception as e:
            logger.warning(f"Chatbot reply error: {e}")

    @app_commands.command(name="chatbot-setchannel", description="💬 Enable chatbot replies in a channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(self, interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)
        channels = self.data.setdefault(guild_id, [])
        ch_id = str(channel.id)
        if ch_id in channels:
            return await interaction.response.send_message(f"❌ {channel.mention} is already a chatbot channel.", ephemeral=True)
        channels.append(ch_id)
        _save(self.data)
        mode = "AI-powered 🤖" if GEMINI_API_KEY else "keyword-based 💬"
        await interaction.response.send_message(f"✅ Chatbot ({mode}) enabled in {channel.mention}!\nI'll reply to every message there 😏\nUse `/chatbot-removechannel` to disable.", ephemeral=True)

    @app_commands.command(name="chatbot-removechannel", description="💬 Disable chatbot in a channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_channel(self, interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)
        channels = self.data.get(guild_id, [])
        ch_id = str(channel.id)
        if ch_id not in channels:
            return await interaction.response.send_message(f"❌ {channel.mention} is not a chatbot channel.", ephemeral=True)
        channels.remove(ch_id)
        _save(self.data)
        await interaction.response.send_message(f"✅ Chatbot disabled in {channel.mention}.", ephemeral=True)

    @app_commands.command(name="chatbot-list", description="💬 List chatbot channels")
    async def list_channels(self, interaction):
        channels = self.data.get(str(interaction.guild.id), [])
        if not channels:
            return await interaction.response.send_message("No chatbot channels set. Use `/chatbot-setchannel #channel` to add one.", ephemeral=True)
        mentions = []
        for ch_id in channels:
            ch = interaction.guild.get_channel(int(ch_id))
            mentions.append(ch.mention if ch else f"`{ch_id}`")
        embed = discord.Embed(title="💬 Chatbot Channels", description="\n".join(mentions), color=0x5865f2)
        mode = "AI (Gemini) 🤖" if GEMINI_API_KEY else "Keyword-based 💬 (set GEMINI_API_KEY for AI)"
        embed.set_footer(text=f"Mode: {mode}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Chatbot(bot))
