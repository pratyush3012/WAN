import discord
from discord.ext import commands, tasks
from utils.checks import is_admin
from utils.embeds import EmbedFactory
from utils.database import Database
import json

class Automation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
    
    @commands.command(name="setwelcome")
    @commands.has_permissions(administrator=True)
    async def setwelcome(self, ctx, channel: discord.TextChannel):
        await self.db.update_guild_config(ctx.guild.id, welcome_channel=channel.id)
        await ctx.send(f"✅ Welcome messages will be sent to {channel.mention}")

    @commands.command(name="setautorole")
    @commands.has_permissions(administrator=True)
    async def setautorole(self, ctx, role: discord.Role):
        await self.db.update_guild_config(ctx.guild.id, auto_role=role.id)
        await ctx.send(f"✅ New members will automatically receive {role.mention}")

    @commands.command(name="announce")
    @commands.has_permissions(administrator=True)
    async def announce(self, ctx, channel: discord.TextChannel, title: str, *, message: str):
        embed = discord.Embed(title=f"📢 {title}", description=message, color=discord.Color.blue())
        embed.set_footer(text=f"Announced by {ctx.author.display_name}")
        await channel.send(embed=embed)
        await ctx.send(f"✅ Announcement sent to {channel.mention}", delete_after=5)

    @commands.command(name="reactionrole")
    @commands.has_permissions(administrator=True)
    async def reactionrole(self, ctx, channel: discord.TextChannel, title: str, *, description: str):
        embed = discord.Embed(title=title, description=description + "\n\nReact below to get roles!", color=discord.Color.purple())
        message = await channel.send(embed=embed)
        await ctx.send(f"✅ Reaction role created. Message ID: {message.id}", delete_after=10)

async def setup(bot):
    await bot.add_cog(Automation(bot))
