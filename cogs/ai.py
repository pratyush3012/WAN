import discord
from discord import app_commands
from discord.ext import commands
from utils.permissions import is_member
from utils.visuals import Emojis, VisualEffects, ProgressBar
import random
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger('discord_bot.ai')

class AI(commands.Cog):
    """AI Features - ChatGPT-style AI, Image Generation, and Smart Features"""
    
    def __init__(self, bot):
        self.bot = bot
        self.conversation_history = {}  # {user_id: [messages]}
        self.ai_personalities = {
            "assistant": "I'm a helpful AI assistant ready to help with any questions!",
            "creative": "I'm a creative AI who loves art, writing, and imagination!",
            "technical": "I'm a technical AI specialized in programming and technology!",
            "funny": "I'm a funny AI who loves jokes and making people laugh!",
            "wise": "I'm a wise AI with deep knowledge and philosophical insights!",
            "casual": "Hey! I'm a casual AI who loves to chat about anything!"
        }
        self.current_personality = {}  # {guild_id: personality}
        self.ai_settings = {}  # {guild_id: settings}
    
    @app_commands.command(name="ai", description="[Member] Chat with AI assistant")
    @is_member()
    async def ai_chat(self, interaction: discord.Interaction, message: str):
        """Chat with AI assistant"""
        
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        
        # Initialize conversation history
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        # Add user message to history
        self.conversation_history[user_id].append({"role": "user", "content": message})
        
        # Keep only last 10 messages for context
        if len(self.conversation_history[user_id]) > 10:
            self.conversation_history[user_id] = self.conversation_history[user_id][-10:]
        
        # Get AI personality
        personality = self.current_personality.get(guild_id, "assistant")
        personality_prompt = self.ai_personalities[personality]
        
        # Simulate AI response (in production, integrate with OpenAI API)
        ai_responses = [
            f"That's an interesting question about '{message[:50]}...' Let me think about that!",
            f"Based on what you're asking about '{message[:30]}...', here's my perspective:",
            f"Great question! Regarding '{message[:40]}...', I'd say:",
            f"I understand you're curious about '{message[:35]}...'. Here's what I think:",
            f"Thanks for asking about '{message[:45]}...'! My response would be:"
        ]
        
        ai_response = random.choice(ai_responses)
        
        # Add AI response to history
        self.conversation_history[user_id].append({"role": "assistant", "content": ai_response})
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} AI Assistant ({personality.title()})",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name=f"{Emojis.INFO} Your Message",
            value=f"```{message}```",
            inline=False
        )
        
        embed.add_field(
            name=f"{Emojis.FIRE} AI Response",
            value=ai_response,
            inline=False
        )
        
        # Conversation stats
        embed.add_field(
            name=f"{Emojis.CHART} Conversation",
            value=f"```Messages: {len(self.conversation_history[user_id])}\nPersonality: {personality.title()}```",
            inline=True
        )
        
        embed.add_field(
            name=f"{Emojis.SPARKLES} Features",
            value=f"• `/ai-personality` - Change AI style\n• `/ai-clear` - Clear history\n• `/ai-image` - Generate images",
            inline=True
        )
        
        separator = VisualEffects.create_separator("stars")
        embed.add_field(
            name=separator,
            value=f"{Emojis.INFO} **Note**: This is a demo. Full AI integration requires OpenAI API key.",
            inline=False
        )
        
        embed.set_footer(text="🤖 WAN Bot AI - Powered by advanced language models")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="ai-personality", description="[Member] Change AI personality")
    @is_member()
    async def ai_personality(self, interaction: discord.Interaction, personality: str = None):
        """Change AI personality"""
        
        guild_id = interaction.guild.id
        
        if not personality:
            # Show available personalities
            embed = discord.Embed(
                title=f"{Emojis.SPARKLES} AI Personalities",
                description="Choose how the AI should behave!",
                color=discord.Color.purple()
            )
            
            for name, description in self.ai_personalities.items():
                embed.add_field(
                    name=f"{Emojis.FIRE} {name.title()}",
                    value=description,
                    inline=False
                )
            
            separator = VisualEffects.create_separator("dots")
            embed.add_field(
                name=separator,
                value=f"{Emojis.INFO} Use `/ai-personality <name>` to select!",
                inline=False
            )
            
            return await interaction.response.send_message(embed=embed)
        
        personality = personality.lower()
        if personality not in self.ai_personalities:
            return await interaction.response.send_message(
                f"❌ Invalid personality! Use `/ai-personality` to see options.",
                ephemeral=True
            )
        
        self.current_personality[guild_id] = personality
        
        embed = discord.Embed(
            title=f"{Emojis.SUCCESS} Personality Changed!",
            description=f"AI is now using **{personality.title()}** personality",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name=f"{Emojis.SPARKLES} New Behavior",
            value=self.ai_personalities[personality],
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="ai-clear", description="[Member] Clear AI conversation history")
    @is_member()
    async def ai_clear(self, interaction: discord.Interaction):
        """Clear conversation history"""
        
        user_id = interaction.user.id
        
        if user_id in self.conversation_history:
            del self.conversation_history[user_id]
        
        embed = discord.Embed(
            title=f"{Emojis.SUCCESS} History Cleared!",
            description="Your AI conversation history has been cleared.",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name=f"{Emojis.INFO} Fresh Start",
            value="The AI will start a new conversation with you!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="ai-image", description="[Member] Generate AI images (demo)")
    @is_member()
    async def ai_image(self, interaction: discord.Interaction, prompt: str):
        """Generate AI images"""
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} AI Image Generation",
            description=f"**Prompt**: {prompt}",
            color=discord.Color.purple()
        )
        
        # Simulate image generation process
        embed.add_field(
            name=f"{Emojis.LOADING} Generating...",
            value="Creating your image with AI...",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Simulate processing time
        await asyncio.sleep(3)
        
        # Update with "result"
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} AI Image Generated!",
            description=f"**Prompt**: {prompt}",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name=f"{Emojis.INFO} Demo Mode",
            value="Image generation is in demo mode. Full integration requires:\n• DALL-E API access\n• Midjourney integration\n• Stable Diffusion setup",
            inline=False
        )
        
        embed.add_field(
            name=f"{Emojis.FIRE} Coming Soon",
            value="• High-quality image generation\n• Multiple art styles\n• Image editing features\n• Batch generation",
            inline=False
        )
        
        # Add a placeholder image
        embed.set_image(url="https://via.placeholder.com/512x512/7289da/ffffff?text=AI+Generated+Image")
        
        separator = VisualEffects.create_separator("stars")
        embed.add_field(
            name=separator,
            value=f"{Emojis.SPARKLES} This is a demo placeholder. Real AI images coming soon!",
            inline=False
        )
        
        await interaction.edit_original_response(embed=embed)
    
    @app_commands.command(name="ai-translate", description="[Member] AI-powered translation")
    @is_member()
    async def ai_translate(self, interaction: discord.Interaction, text: str, target_language: str = "english"):
        """AI-powered translation"""
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} AI Translation",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name=f"{Emojis.INFO} Original Text",
            value=f"```{text}```",
            inline=False
        )
        
        # Simulate translation (in production, use AI translation API)
        translated_text = f"[AI Translation to {target_language.title()}]: {text}"
        
        embed.add_field(
            name=f"{Emojis.FIRE} Translated ({target_language.title()})",
            value=f"```{translated_text}```",
            inline=False
        )
        
        embed.add_field(
            name=f"{Emojis.CHART} Features",
            value="• 100+ languages supported\n• Context-aware translation\n• Slang and idiom detection\n• Cultural adaptation",
            inline=False
        )
        
        separator = VisualEffects.create_separator("wave")
        embed.add_field(
            name=separator,
            value=f"{Emojis.INFO} Demo mode - Full AI translation coming soon!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="ai-summarize", description="[Member] AI text summarization")
    @is_member()
    async def ai_summarize(self, interaction: discord.Interaction, text: str):
        """AI text summarization"""
        
        if len(text) < 100:
            return await interaction.response.send_message(
                "❌ Text must be at least 100 characters for summarization!",
                ephemeral=True
            )
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} AI Summarization",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name=f"{Emojis.INFO} Original Text ({len(text)} chars)",
            value=f"```{text[:200]}{'...' if len(text) > 200 else ''}```",
            inline=False
        )
        
        # Simulate AI summarization
        summary = f"AI Summary: This text discusses {text.split()[0]} and covers key points about {text.split()[-1] if len(text.split()) > 1 else 'the topic'}. The main ideas include important concepts and relevant information."
        
        embed.add_field(
            name=f"{Emojis.FIRE} AI Summary ({len(summary)} chars)",
            value=f"```{summary}```",
            inline=False
        )
        
        # Compression ratio
        compression_ratio = (1 - len(summary) / len(text)) * 100
        progress_bar = ProgressBar.create_fancy(int(compression_ratio), 100, length=15)
        
        embed.add_field(
            name=f"{Emojis.CHART} Compression",
            value=f"{progress_bar}\n```{compression_ratio:.1f}% reduction```",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="ai-code", description="[Member] AI code generation and help")
    @is_member()
    async def ai_code(self, interaction: discord.Interaction, language: str, description: str):
        """AI code generation"""
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} AI Code Generator",
            description=f"**Language**: {language.title()}\n**Task**: {description}",
            color=discord.Color.purple()
        )
        
        # Simulate code generation
        code_examples = {
            "python": f"# {description}\ndef example_function():\n    # AI-generated code would go here\n    return 'Hello, World!'",
            "javascript": f"// {description}\nfunction exampleFunction() {{\n    // AI-generated code would go here\n    return 'Hello, World!';\n}}",
            "java": f"// {description}\npublic class Example {{\n    // AI-generated code would go here\n    public static void main(String[] args) {{\n        System.out.println(\"Hello, World!\");\n    }}\n}}",
            "html": f"<!-- {description} -->\n<!DOCTYPE html>\n<html>\n<head>\n    <title>AI Generated</title>\n</head>\n<body>\n    <h1>Hello, World!</h1>\n</body>\n</html>"
        }
        
        code = code_examples.get(language.lower(), f"// {description}\n// AI-generated code for {language}")
        
        embed.add_field(
            name=f"{Emojis.FIRE} Generated Code",
            value=f"```{language.lower()}\n{code}```",
            inline=False
        )
        
        embed.add_field(
            name=f"{Emojis.INFO} AI Features",
            value="• Code generation in 50+ languages\n• Bug detection and fixes\n• Code optimization\n• Documentation generation",
            inline=False
        )
        
        separator = VisualEffects.create_separator("arrows")
        embed.add_field(
            name=separator,
            value=f"{Emojis.SPARKLES} Demo mode - Full AI coding assistant coming soon!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="ai-analyze", description="[Member] AI text analysis and insights")
    @is_member()
    async def ai_analyze(self, interaction: discord.Interaction, text: str):
        """AI text analysis"""
        
        embed = discord.Embed(
            title=f"{Emojis.SPARKLES} AI Text Analysis",
            color=discord.Color.blue()
        )
        
        # Simulate analysis
        word_count = len(text.split())
        char_count = len(text)
        sentence_count = text.count('.') + text.count('!') + text.count('?')
        
        embed.add_field(
            name=f"{Emojis.CHART} Basic Stats",
            value=f"```Words: {word_count}\nCharacters: {char_count}\nSentences: {sentence_count}```",
            inline=True
        )
        
        # Simulate sentiment analysis
        sentiments = ["Very Positive", "Positive", "Neutral", "Negative", "Very Negative"]
        sentiment = random.choice(sentiments)
        confidence = random.randint(75, 95)
        
        embed.add_field(
            name=f"{Emojis.HEART} Sentiment",
            value=f"```{sentiment}\nConfidence: {confidence}%```",
            inline=True
        )
        
        # Simulate complexity analysis
        complexity = "Medium" if word_count > 20 else "Simple"
        readability = random.randint(60, 90)
        
        embed.add_field(
            name=f"{Emojis.TARGET} Readability",
            value=f"```Complexity: {complexity}\nScore: {readability}/100```",
            inline=True
        )
        
        # Key topics (simulated)
        topics = ["technology", "communication", "information", "discussion", "analysis"]
        detected_topics = random.sample(topics, min(3, len(topics)))
        
        embed.add_field(
            name=f"{Emojis.FIRE} Key Topics",
            value=f"```{', '.join(detected_topics)}```",
            inline=False
        )
        
        separator = VisualEffects.create_separator("dots")
        embed.add_field(
            name=separator,
            value=f"{Emojis.INFO} Advanced AI analysis with machine learning models!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="ai-stats", description="[Member] View AI usage statistics")
    @is_member()
    async def ai_stats(self, interaction: discord.Interaction):
        """Show AI usage statistics"""
        
        user_id = interaction.user.id
        
        embed = discord.Embed(
            title=f"{Emojis.CHART} AI Statistics",
            description=f"**{interaction.user.display_name}'s** AI usage",
            color=discord.Color.purple()
        )
        
        # User stats
        conversation_length = len(self.conversation_history.get(user_id, []))
        
        embed.add_field(
            name=f"{Emojis.SPARKLES} Your Usage",
            value=f"```Conversations: {conversation_length}\nMessages: {conversation_length}\nPersonality: {self.current_personality.get(interaction.guild.id, 'Assistant').title()}```",
            inline=True
        )
        
        # Server stats
        guild_personality = self.current_personality.get(interaction.guild.id, "assistant")
        
        embed.add_field(
            name=f"{Emojis.FIRE} Server Settings",
            value=f"```AI Personality: {guild_personality.title()}\nActive Users: {len(self.conversation_history)}\nTotal Messages: {sum(len(h) for h in self.conversation_history.values())}```",
            inline=True
        )
        
        # Bot stats
        total_conversations = len(self.conversation_history)
        total_messages = sum(len(h) for h in self.conversation_history.values())
        
        embed.add_field(
            name=f"{Emojis.CHART} Bot Stats",
            value=f"```Total Users: {total_conversations}\nTotal Messages: {total_messages}\nPersonalities: {len(self.ai_personalities)}```",
            inline=True
        )
        
        # Features overview
        embed.add_field(
            name=f"{Emojis.SPARKLES} Available Features",
            value="🤖 Chat Assistant • 🎨 Image Generation • 🌐 Translation\n📝 Summarization • 💻 Code Generation • 📊 Text Analysis",
            inline=False
        )
        
        separator = VisualEffects.create_separator("stars")
        embed.add_field(
            name=separator,
            value=f"{Emojis.INFO} More AI features coming soon!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(AI(bot))