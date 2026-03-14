import discord
from discord import app_commands
from discord.ext import commands
from utils.embeds import EmbedFactory
from utils.permissions import is_member
import random
import aiohttp
import logging

logger = logging.getLogger('discord_bot.fun')

class Fun(commands.Cog):
    """Fun and entertainment commands - Members only"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="8ball", description="[Member] Ask the magic 8ball a question")
    @is_member()
    async def eightball(self, interaction: discord.Interaction, question: str):
        """Magic 8ball responses"""
        responses = [
            "It is certain.", "It is decidedly so.", "Without a doubt.",
            "Yes definitely.", "You may rely on it.", "As I see it, yes.",
            "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
            "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
            "Cannot predict now.", "Concentrate and ask again.",
            "Don't count on it.", "My reply is no.", "My sources say no.",
            "Outlook not so good.", "Very doubtful."
        ]
        
        response = random.choice(responses)
        embed = EmbedFactory.info("🎱 Magic 8Ball", f"**Question:** {question}\n**Answer:** {response}")
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="meme", description="[Member] Get a random meme")
    @is_member()
    async def meme(self, interaction: discord.Interaction):
        """Fetch a random meme from Reddit"""
        await interaction.response.defer()
        
        try:
            subreddits = ["memes", "dankmemes", "wholesomememes", "me_irl"]
            subreddit = random.choice(subreddits)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://www.reddit.com/r/{subreddit}/random.json",
                                     headers={'User-Agent': 'Discord Bot'}) as resp:
                    if resp.status != 200:
                        return await interaction.followup.send(
                            embed=EmbedFactory.error("Error", "Could not fetch meme. Try again!")
                        )
                    
                    data = await resp.json()
                    post = data[0]['data']['children'][0]['data']
                    
                    # Skip videos and galleries
                    if post.get('is_video') or 'gallery' in post.get('url', ''):
                        return await interaction.followup.send(
                            embed=EmbedFactory.info("🎭 Meme", "Got a video/gallery, try again!")
                        )
                    
                    embed = discord.Embed(
                        title=post['title'][:256],
                        url=f"https://reddit.com{post['permalink']}",
                        color=discord.Color.orange()
                    )
                    embed.set_image(url=post['url'])
                    embed.set_footer(text=f"👍 {post['ups']} | r/{subreddit}")
                    
                    await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error fetching meme: {e}")
            await interaction.followup.send(
                embed=EmbedFactory.error("Error", "Could not fetch meme. Try again!")
            )
    
    @app_commands.command(name="joke", description="[Member] Get a random joke")
    @is_member()
    async def joke(self, interaction: discord.Interaction):
        """Fetch a random joke"""
        await interaction.response.defer()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://official-joke-api.appspot.com/random_joke") as resp:
                    if resp.status != 200:
                        return await interaction.followup.send(
                            embed=EmbedFactory.error("Error", "Could not fetch joke. Try again!")
                        )
                    
                    data = await resp.json()
                    
                    embed = EmbedFactory.info("😂 Random Joke", f"**{data['setup']}**\n\n||{data['punchline']}||")
                    embed.set_footer(text="Click to reveal punchline!")
                    
                    await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error fetching joke: {e}")
            await interaction.followup.send(
                embed=EmbedFactory.error("Error", "Could not fetch joke. Try again!")
            )
    
    @app_commands.command(name="choose", description="[Member] Let the bot choose for you")
    @is_member()
    async def choose(self, interaction: discord.Interaction, choices: str):
        """Choose between multiple options (separate with commas)"""
        options = [choice.strip() for choice in choices.split(',')]
        
        if len(options) < 2:
            return await interaction.response.send_message(
                embed=EmbedFactory.error("Not Enough Options", "Please provide at least 2 options separated by commas."),
                ephemeral=True
            )
        
        chosen = random.choice(options)
        embed = EmbedFactory.info("🎯 I Choose...", f"**{chosen}**")
        embed.add_field(name="Options", value=", ".join(options), inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="rate", description="[Member] Rate something from 1-10")
    @is_member()
    async def rate(self, interaction: discord.Interaction, thing: str):
        """Rate something"""
        rating = random.randint(1, 10)
        stars = "⭐" * rating
        
        embed = EmbedFactory.info("⭐ Rating", f"I'd rate **{thing}** a **{rating}/10**!\n{stars}")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Fun(bot))
