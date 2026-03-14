import discord
from discord.ext import commands
from utils.database import Database
from utils.embeds import EmbedFactory

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
    
    async def send_log(self, guild_id, embed):
        config = await self.db.get_guild_config(guild_id)
        if config.log_channel:
            channel = self.bot.get_channel(config.log_channel)
            if channel:
                try:
                    await channel.send(embed=embed)
                except:
                    pass
    
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild:
            return
        
        embed = discord.Embed(
            title="🗑️ Message Deleted",
            description=f"**Author:** {message.author.mention}\n**Channel:** {message.channel.mention}",
            color=discord.Color.red()
        )
        
        if message.content:
            embed.add_field(name="Content", value=message.content[:1024], inline=False)
        
        embed.set_footer(text=f"User ID: {message.author.id}")
        await self.send_log(message.guild.id, embed)
    
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or not before.guild or before.content == after.content:
            return
        
        embed = discord.Embed(
            title="✏️ Message Edited",
            description=f"**Author:** {before.author.mention}\n**Channel:** {before.channel.mention}",
            color=discord.Color.orange()
        )
        
        embed.add_field(name="Before", value=before.content[:1024] if before.content else "No content", inline=False)
        embed.add_field(name="After", value=after.content[:1024] if after.content else "No content", inline=False)
        embed.add_field(name="Jump to Message", value=f"[Click here]({after.jump_url})", inline=False)
        
        await self.send_log(before.guild.id, embed)
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        embed = discord.Embed(
            title="🔨 Member Banned",
            description=f"**User:** {user.mention}\n**ID:** {user.id}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await self.send_log(guild.id, embed)
    
    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        embed = discord.Embed(
            title="✅ Member Unbanned",
            description=f"**User:** {user.mention}\n**ID:** {user.id}",
            color=discord.Color.green()
        )
        await self.send_log(guild.id, embed)
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.roles != after.roles:
            added = [role for role in after.roles if role not in before.roles]
            removed = [role for role in before.roles if role not in after.roles]
            
            if added or removed:
                embed = discord.Embed(
                    title="👤 Member Roles Updated",
                    description=f"**Member:** {after.mention}",
                    color=discord.Color.blue()
                )
                
                if added:
                    embed.add_field(name="Roles Added", value=", ".join([r.mention for r in added]), inline=False)
                if removed:
                    embed.add_field(name="Roles Removed", value=", ".join([r.mention for r in removed]), inline=False)
                
                await self.send_log(after.guild.id, embed)
    
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = discord.Embed(
            title="📝 Channel Created",
            description=f"**Channel:** {channel.mention}\n**Type:** {channel.type}",
            color=discord.Color.green()
        )
        await self.send_log(channel.guild.id, embed)
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = discord.Embed(
            title="🗑️ Channel Deleted",
            description=f"**Channel:** {channel.name}\n**Type:** {channel.type}",
            color=discord.Color.red()
        )
        await self.send_log(channel.guild.id, embed)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel != after.channel:
            if after.channel:
                embed = discord.Embed(
                    title="🔊 Voice Channel Join",
                    description=f"**Member:** {member.mention}\n**Channel:** {after.channel.mention}",
                    color=discord.Color.green()
                )
                await self.send_log(member.guild.id, embed)
            elif before.channel:
                embed = discord.Embed(
                    title="🔇 Voice Channel Leave",
                    description=f"**Member:** {member.mention}\n**Channel:** {before.channel.mention}",
                    color=discord.Color.red()
                )
                await self.send_log(member.guild.id, embed)

async def setup(bot):
    await bot.add_cog(Logging(bot))
