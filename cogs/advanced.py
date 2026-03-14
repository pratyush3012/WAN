import discord
from discord import app_commands
from discord.ext import commands
from utils.permissions import is_member
import aiohttp
import random
from datetime import datetime

class Advanced(commands.Cog):
    """Advanced features - Weather, Wiki, Crypto, News, Quotes"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="weather", description="[Member] Get weather information for a city")
    @is_member()
    async def weather(self, interaction: discord.Interaction, city: str):
        """Get weather information (using free API)"""
        await interaction.response.defer()
        
        try:
            async with aiohttp.ClientSession() as session:
                # Using wttr.in - free weather API
                url = f"https://wttr.in/{city}?format=j1"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        current = data['current_condition'][0]
                        
                        embed = discord.Embed(
                            title=f"🌤️ Weather in {city.title()}",
                            color=discord.Color.blue(),
                            timestamp=datetime.utcnow()
                        )
                        
                        weather_box = f"""
```ansi
[2;36m╔════════════════════════════════════╗[0m
[2;36m║[0m  [1;33m🌡️ CURRENT CONDITIONS[0m          [2;36m║[0m
[2;36m╠════════════════════════════════════╣[0m
[2;36m║[0m                                    [2;36m║[0m
[2;36m║[0m  Temperature: [1;32m{current['temp_C']}°C[0m / [1;32m{current['temp_F']}°F[0m  [2;36m║[0m
[2;36m║[0m  Feels Like:  [1;32m{current['FeelsLikeC']}°C[0m / [1;32m{current['FeelsLikeF']}°F[0m  [2;36m║[0m
[2;36m║[0m  Condition:   [1;36m{current['weatherDesc'][0]['value']}[0m  [2;36m║[0m
[2;36m║[0m  Humidity:    [1;34m{current['humidity']}%[0m              [2;36m║[0m
[2;36m║[0m  Wind:        [1;35m{current['windspeedKmph']} km/h[0m      [2;36m║[0m
[2;36m║[0m  Pressure:    [1;33m{current['pressure']} mb[0m         [2;36m║[0m
[2;36m║[0m                                    [2;36m║[0m
[2;36m╚════════════════════════════════════╝[0m
```
"""
                        embed.add_field(name="", value=weather_box, inline=False)
                        
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("❌ City not found!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error fetching weather: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="wiki", description="[Member] Search Wikipedia")
    @is_member()
    async def wiki(self, interaction: discord.Interaction, query: str):
        """Search Wikipedia"""
        await interaction.response.defer()
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        embed = discord.Embed(
                            title=f"📚 {data['title']}",
                            description=data['extract'][:500] + "..." if len(data['extract']) > 500 else data['extract'],
                            url=data['content_urls']['desktop']['page'],
                            color=discord.Color.from_rgb(255, 255, 255)
                        )
                        
                        if 'thumbnail' in data:
                            embed.set_thumbnail(url=data['thumbnail']['source'])
                        
                        embed.set_footer(text="Source: Wikipedia")
                        
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("❌ Article not found!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="crypto", description="[Member] Get cryptocurrency prices")
    @is_member()
    async def crypto(self, interaction: discord.Interaction, coin: str = "bitcoin"):
        """Get crypto prices"""
        await interaction.response.defer()
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd&include_24hr_change=true"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if coin in data:
                            price = data[coin]['usd']
                            change = data[coin].get('usd_24h_change', 0)
                            
                            trend = "📈" if change > 0 else "📉"
                            color = discord.Color.green() if change > 0 else discord.Color.red()
                            
                            embed = discord.Embed(
                                title=f"💰 {coin.title()} Price",
                                color=color
                            )
                            
                            crypto_box = f"""
```ansi
[2;33m╔════════════════════════════════════╗[0m
[2;33m║[0m  [1;36m💎 CRYPTOCURRENCY INFO[0m          [2;33m║[0m
[2;33m╠════════════════════════════════════╣[0m
[2;33m║[0m                                    [2;33m║[0m
[2;33m║[0m  Coin:        [1;32m{coin.title()}[0m              [2;33m║[0m
[2;33m║[0m  Price:       [1;33m${price:,.2f}[0m USD      [2;33m║[0m
[2;33m║[0m  24h Change:  {trend} [1;{'32' if change > 0 else '31'}m{change:.2f}%[0m       [2;33m║[0m
[2;33m║[0m                                    [2;33m║[0m
[2;33m╚════════════════════════════════════╝[0m
```
"""
                            embed.add_field(name="", value=crypto_box, inline=False)
                            
                            await interaction.followup.send(embed=embed)
                        else:
                            await interaction.followup.send("❌ Cryptocurrency not found!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="quote", description="[Member] Get an inspirational quote")
    @is_member()
    async def quote(self, interaction: discord.Interaction):
        """Get random quote"""
        await interaction.response.defer()
        
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.quotable.io/random"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        embed = discord.Embed(
                            color=discord.Color.purple()
                        )
                        
                        quote_box = f"""
```
╔═══════════════════════════════════════════════╗
║                                               ║
║  💭 INSPIRATIONAL QUOTE                       ║
║                                               ║
╠═══════════════════════════════════════════════╣
║                                               ║
║  "{data['content']}"
║                                               ║
║  — {data['author']}                           ║
║                                               ║
╚═══════════════════════════════════════════════╝
```
"""
                        embed.add_field(name="", value=quote_box, inline=False)
                        
                        await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="fact", description="[Member] Get a random fun fact")
    @is_member()
    async def fact(self, interaction: discord.Interaction):
        """Get random fact"""
        await interaction.response.defer()
        
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://uselessfacts.jsph.pl/random.json?language=en"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        embed = discord.Embed(
                            title="🧠 Random Fun Fact",
                            description=f"```\n{data['text']}\n```",
                            color=discord.Color.blue()
                        )
                        
                        await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Advanced(bot))
