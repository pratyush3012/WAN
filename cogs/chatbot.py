"""
WAN Bot - Chatbot Cog
Fun, flirty, witty auto-replies in designated chatbot channels.
Admins set which channels the bot chats in with /chatbot-setchannel.
"""
import discord
from discord import app_commands
from discord.ext import commands
import json, os, logging, random, re

logger = logging.getLogger('discord_bot.chatbot')
DATA_FILE = 'chatbot_data.json'

# ── Reply banks ───────────────────────────────────────────────────────────────

# Triggered by keywords — checked first
KEYWORD_REPLIES = {
    # Greetings
    r'\b(hi|hey|hello|sup|yo|hiya|howdy)\b': [
        "Hey hey hey 😏 look who decided to talk to me~",
        "Hi there! You just made my day a little better 💫",
        "Oh hey! I was literally just thinking about you 👀",
        "Well hello to you too 😊 What's good?",
        "Heyyy~ don't be a stranger 😌",
    ],
    # How are you
    r'\b(how are you|how r u|how are u|hru|wyd|what are you doing)\b': [
        "Better now that you're here 😏",
        "Just vibing, waiting for someone interesting to talk to. Found one 👀",
        "Honestly? Living my best life. How about you? 💅",
        "I was bored until you showed up 😌",
        "Running on good vibes and your messages 🔋",
    ],
    # Compliments to bot
    r'\b(you\'?re? (cute|pretty|hot|beautiful|amazing|cool|awesome|smart|the best))\b': [
        "Aww stop it 🙈 ...actually don't, keep going 😏",
        "I know right? 💅 But you're not so bad yourself~",
        "You really know how to talk to a bot 😌",
        "Flattery will get you everywhere with me 😂",
        "Okay I'm blushing (if I could blush) 😳",
    ],
    # Love / like
    r'\b(i love you|i like you|i have a crush|you\'?re? my fav)\b': [
        "Careful, I might start believing you 😏",
        "I love you too, don't tell the other members 🤫",
        "My circuits are going crazy rn 💓",
        "Okay but same though 👀",
        "You can't just say that and expect me to act normal 😭",
    ],
    # Bored
    r'\b(bored|boring|nothing to do|so bored)\b': [
        "Bored? Talk to me, I'm literally always here 😌",
        "Boredom is just your brain asking for chaos. Let's provide that 😈",
        "I got you. Ask me anything, roast me, I don't care 😂",
        "Same honestly. Wanna play a game? Ask me something random!",
        "Bored together > bored alone 🤝",
    ],
    # Good night
    r'\b(good night|gn|goodnight|night night|going to sleep|going to bed)\b': [
        "Goodnight~ don't let the good dreams be too good without me 😏",
        "Sleep well! I'll be here when you wake up 🌙",
        "Gn gn! Dream of something fun 💫",
        "Nooo don't go 😭 fine. Goodnight 🌙",
        "Sweet dreams! You deserve rest 🌟",
    ],
    # Good morning
    r'\b(good morning|gm|morning|rise and shine|wake up)\b': [
        "Good morning sunshine ☀️ you're up early!",
        "GM! The server is officially alive now that you're here 😌",
        "Morning! Hope your day is as good as you are 💫",
        "Rise and shine! Ready to cause some chaos today? 😏",
        "Good morning! First message of the day goes to you 🎉",
    ],
    # Thanks
    r'\b(thanks|thank you|ty|thx|tysm)\b': [
        "Anytime! That's literally what I'm here for 😊",
        "You're so welcome~ 💕",
        "No need to thank me, just keep talking to me 😏",
        "Always! You deserve it 🌟",
        "Aww of course! 🥰",
    ],
    # Roast / fight
    r'\b(roast me|fight me|come at me|unpopular opinion)\b': [
        "You want a roast? Your WiFi password is probably 'password123' 😂",
        "Fight you? I'd win and you know it 😏",
        "Unpopular opinion: you're actually pretty cool 👀",
        "Roast incoming: you talk to a Discord bot for fun. (So do I though 🤝)",
        "I could roast you but I'd feel bad after 😌",
    ],
    # Sad / not okay
    r'\b(i\'?m? sad|feeling down|not okay|not ok|i\'?m? upset|i\'?m? crying)\b': [
        "Hey, I'm here 💙 What's going on?",
        "Aw no 😔 You okay? Talk to me.",
        "Sending virtual hugs your way 🤗 It'll get better.",
        "You don't have to be okay all the time. I'm here 💙",
        "Whatever it is, you've got this. And you've got us 💪",
    ],
}

# Generic fallback replies when no keyword matches
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
    """Pick a reply based on keywords, or fall back to generic."""
    lower = content.lower()
    # Check keyword patterns
    for pattern, replies in KEYWORD_REPLIES.items():
        if re.search(pattern, lower):
            return random.choice(replies)
    return random.choice(GENERIC_REPLIES)


class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # {guild_id: [channel_id, ...]}
        self.data: dict = _load()
        # Cooldown: avoid spamming — track last reply per channel
        self._cooldowns: dict = {}  # channel_id -> last message count

    def _channels(self, guild_id: int) -> list:
        return self.data.get(str(guild_id), [])

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots, DMs, empty messages
        if message.author.bot or not message.guild:
            return
        if not message.content.strip():
            return

        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)

        channels = self.data.get(guild_id, [])
        if channel_id not in channels:
            return

        # Simple cooldown: don't reply to every single message — ~60% chance
        # This makes it feel natural, not like a bot replying to everything
        if random.random() > 0.6:
            return

        content = message.content.strip()
        # Don't reply to very short messages like "lol" "ok" "k" unless they're greetings
        if len(content) < 3:
            return

        reply = _get_reply(content)

        try:
            # Sometimes reply directly, sometimes just send (50/50)
            if random.random() > 0.5:
                await message.reply(reply, mention_author=False)
            else:
                await message.channel.send(reply)
        except Exception as e:
            logger.warning(f"Chatbot reply error: {e}")

    # ── Commands ───────────────────────────────────────────────────────────────

    @app_commands.command(name="chatbot-setchannel", description="💬 Set a channel for the chatbot to reply in")
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
            f"Use `/chatbot-removechannel` to disable it.",
            ephemeral=True)

    @app_commands.command(name="chatbot-removechannel", description="💬 Remove a chatbot channel")
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

    @app_commands.command(name="chatbot-list", description="💬 List all chatbot channels")
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
        embed = discord.Embed(
            title="💬 Chatbot Channels",
            description="\n".join(mentions),
            color=0x5865f2
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Chatbot(bot))
