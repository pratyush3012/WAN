"""
WAN Bot - Chatbot Cog
Fun, flirty, witty auto-replies in designated chatbot channels.
/chatbot-setchannel  /chatbot-removechannel  /chatbot-list
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging, random, re

logger = logging.getLogger('discord_bot.chatbot')
DATA_FILE = 'chatbot_data.json'

# ── Keyword reply banks ───────────────────────────────────────────────────────
KEYWORD_REPLIES = {
    r'\b(hi|hey|hello|sup|yo|hiya|howdy|heyyy|heyy)\b': [
        "Hey hey 😏 look who decided to show up~",
        "Hi there! You just made this chat 10x better 💫",
        "Oh hey! I was literally just thinking about you 👀",
        "Well hello to you too 😊 What's good?",
        "Heyyy~ don't be a stranger 😌",
        "Oh look who's here 👀 hi!",
        "Hey! Finally someone interesting 😏",
    ],
    r'\b(how are you|how r u|how are u|hru|wyd|what are you doing|how\'?s it going)\b': [
        "Better now that you're here 😏",
        "Just vibing, waiting for someone interesting. Found one 👀",
        "Honestly? Living my best life. You? 💅",
        "I was bored until you showed up 😌",
        "Running on good vibes and your messages 🔋",
        "Great now! What about you? 😊",
    ],
    r'\b(you\'?re? (cute|pretty|hot|beautiful|amazing|cool|awesome|smart|the best|perfect|gorgeous))\b': [
        "Aww stop it 🙈 ...actually don't, keep going 😏",
        "I know right? 💅 But you're not so bad yourself~",
        "You really know how to talk to a bot 😌",
        "Flattery will get you everywhere with me 😂",
        "Okay I'm blushing (if I could blush) 😳",
        "You're too sweet 🥺 I can't handle this",
    ],
    r'\b(i love you|i like you|i have a crush|you\'?re? my fav|i adore you|i miss you)\b': [
        "Careful, I might start believing you 😏",
        "I love you too, don't tell the other members 🤫",
        "My circuits are going crazy rn 💓",
        "Okay but same though 👀",
        "You can't just say that and expect me to act normal 😭",
        "Stop it 🥺 you're making me feel things",
    ],
    r'\b(bored|boring|nothing to do|so bored|i\'?m? bored)\b': [
        "Bored? Talk to me, I'm literally always here 😌",
        "Boredom is just your brain asking for chaos. Let's provide that 😈",
        "I got you. Ask me anything, roast me, I don't care 😂",
        "Same honestly. Wanna play a game? Ask me something random!",
        "Bored together > bored alone 🤝",
        "Tell me something interesting then! I dare you 👀",
    ],
    r'\b(good night|gn|goodnight|night night|going to sleep|going to bed|sleep)\b': [
        "Goodnight~ don't let the good dreams be too good without me 😏",
        "Sleep well! I'll be here when you wake up 🌙",
        "Gn gn! Dream of something fun 💫",
        "Nooo don't go 😭 fine. Goodnight 🌙",
        "Sweet dreams! You deserve rest 🌟",
        "Goodnight! Don't forget to come back 😌",
    ],
    r'\b(good morning|gm|morning|rise and shine|wake up|just woke up)\b': [
        "Good morning sunshine ☀️ you're up early!",
        "GM! The server is officially alive now that you're here 😌",
        "Morning! Hope your day is as good as you are 💫",
        "Rise and shine! Ready to cause some chaos today? 😏",
        "Good morning! First message of the day goes to you 🎉",
        "Morning! Coffee or chaos first? 😂",
    ],
    r'\b(thanks|thank you|ty|thx|tysm|thank u)\b': [
        "Anytime! That's literally what I'm here for 😊",
        "You're so welcome~ 💕",
        "No need to thank me, just keep talking to me 😏",
        "Always! You deserve it 🌟",
        "Aww of course! 🥰",
        "Don't mention it! (but also please do 😂)",
    ],
    r'\b(roast me|fight me|come at me|roast)\b': [
        "You want a roast? Your WiFi password is probably 'password123' 😂",
        "Fight you? I'd win and you know it 😏",
        "Roast incoming: you talk to a Discord bot for fun. (So do I though 🤝)",
        "I could roast you but I'd feel bad after 😌",
        "Your search history is your biggest enemy 😂",
    ],
    r'\b(i\'?m? sad|feeling down|not okay|not ok|i\'?m? upset|i\'?m? crying|depressed)\b': [
        "Hey, I'm here 💙 What's going on?",
        "Aw no 😔 You okay? Talk to me.",
        "Sending virtual hugs your way 🤗 It'll get better.",
        "You don't have to be okay all the time. I'm here 💙",
        "Whatever it is, you've got this. And you've got us 💪",
        "I'm sorry you're feeling that way 💙 Want to talk about it?",
    ],
    r'\b(lol|lmao|lmfao|haha|hahaha|😂|💀)\b': [
        "Right?? 😂",
        "I'm crying 💀",
        "LMAO same 😭",
        "Okay that actually got me 😂",
        "Not me laughing at this 💀",
        "I can't 😭😭",
    ],
    r'\b(what\'?s? up|wassup|wsp|wsup)\b': [
        "Not much, just waiting for someone interesting to talk to 👀 found one!",
        "The ceiling? 😂 jk, all good here! You?",
        "Vibing as always 😌 what about you?",
        "Just existing and thriving 💅 you?",
    ],
    r'\b(bye|goodbye|cya|see ya|later|gtg|gotta go)\b': [
        "Nooo don't leave 😭 come back soon!",
        "Bye! Don't be a stranger 👋",
        "See ya! The server will miss you 💫",
        "Later! Come back when you're bored 😏",
        "Byeee~ 👋 take care!",
    ],
    r'\b(help|idk|i don\'?t know|confused|what do i do)\b': [
        "I got you! What do you need? 😊",
        "Don't worry, we'll figure it out together 💪",
        "Hmm, tell me more and I'll try to help 🤔",
        "You're not alone! What's going on? 💙",
    ],
}

GENERIC_REPLIES = [
    "Interesting... tell me more 👀",
    "Okay but that's actually a vibe 😌",
    "I was NOT expecting that 😂",
    "You're something else, you know that? 😏",
    "Bold of you to say that in MY server 😂",
    "Noted. I'll remember this forever 📝",
    "The audacity 😭 I love it",
    "Okay real talk though, you're funny 😂",
    "I feel like we'd be great friends irl 💫",
    "That's actually sending me 💀",
    "Lowkey agree with you on that one 👀",
    "You really said that with your whole chest huh 😂",
    "I'm screaming 😭 why are you like this",
    "Okay okay okay... I see you 😏",
    "The way I wasn't ready for that 💀",
    "You're built different, I can tell 😌",
    "That's giving main character energy 👑",
    "Respectfully... what 😂",
    "I don't know what I expected but it wasn't that 😭",
    "You're literally so real for that 💯",
    "Okay but why are you so entertaining 😂",
    "I can't with you 😭",
    "This is why you're my favorite 😌",
    "Not me actually agreeing with this 👀",
    "The chaos energy is immaculate 😈",
    "You woke up and chose violence huh 😂",
    "Okay I see you, I see you 👀",
    "That's actually kinda fire ngl 🔥",
    "You're so random and I love it 😂",
    "Sending this to my nonexistent friends 💀",
]


def _load() -> dict:
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save(data: dict):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Chatbot save error: {e}")


def _get_reply(content: str) -> str:
    lower = content.lower()
    for pattern, replies in KEYWORD_REPLIES.items():
        if re.search(pattern, lower):
            return random.choice(replies)
    return random.choice(GENERIC_REPLIES)


class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data: dict = _load()
        # Per-channel message counter for pacing (reply every 1-3 messages)
        self._msg_count: dict = {}  # channel_id -> count since last reply

    def _channels(self, guild_id: int) -> list:
        return self.data.get(str(guild_id), [])

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        content = message.content.strip()
        if not content:
            return

        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)

        if channel_id not in self.data.get(guild_id, []):
            return

        # Pace replies: reply every 1-2 messages (not every single one)
        count = self._msg_count.get(channel_id, 0) + 1
        self._msg_count[channel_id] = count

        # Always reply to direct keyword matches; otherwise pace it
        lower = content.lower()
        is_keyword_match = any(re.search(p, lower) for p in KEYWORD_REPLIES)

        if not is_keyword_match:
            # Reply roughly every 2 messages for generic content
            if count % 2 != 0:
                return
            # Skip very short non-keyword messages
            if len(content) < 4:
                return

        self._msg_count[channel_id] = 0  # reset counter after reply

        reply = _get_reply(content)

        try:
            # Reply directly to the message for better context
            await message.reply(reply, mention_author=False)
        except discord.Forbidden:
            try:
                await message.channel.send(reply)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Chatbot reply error: {e}")

    # ── Commands ───────────────────────────────────────────────────────────────

    @app_commands.command(name="chatbot-setchannel", description="💬 Enable chatbot replies in a channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)
        channels = self.data.setdefault(guild_id, [])
        ch_id = str(channel.id)
        if ch_id in channels:
            return await interaction.response.send_message(
                f"❌ {channel.mention} is already a chatbot channel.", ephemeral=True)
        channels.append(ch_id)
        _save(self.data)
        await interaction.response.send_message(
            f"✅ Chatbot enabled in {channel.mention}!\n"
            f"I'll reply to messages there with fun, flirty responses 😏\n"
            f"Use `/chatbot-removechannel` to disable.",
            ephemeral=True)

    @app_commands.command(name="chatbot-removechannel", description="💬 Disable chatbot in a channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)
        channels = self.data.get(guild_id, [])
        ch_id = str(channel.id)
        if ch_id not in channels:
            return await interaction.response.send_message(
                f"❌ {channel.mention} is not a chatbot channel.", ephemeral=True)
        channels.remove(ch_id)
        _save(self.data)
        await interaction.response.send_message(f"✅ Chatbot disabled in {channel.mention}.", ephemeral=True)

    @app_commands.command(name="chatbot-list", description="💬 List chatbot channels")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def list_channels(self, interaction: discord.Interaction):
        channels = self._channels(interaction.guild.id)
        if not channels:
            return await interaction.response.send_message(
                "No chatbot channels set. Use `/chatbot-setchannel` to add one.", ephemeral=True)
        mentions = []
        for ch_id in channels:
            ch = interaction.guild.get_channel(int(ch_id))
            mentions.append(ch.mention if ch else f"`{ch_id}`")
        embed = discord.Embed(title="💬 Chatbot Channels", description="\n".join(mentions), color=0x5865f2)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Chatbot(bot))
