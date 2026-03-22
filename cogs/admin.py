import discord
from discord import app_commands
from discord.ext import commands
from utils.checks import is_admin, is_owner
from utils.embeds import EmbedFactory
from utils.database import Database

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
    
    @commands.command(name="addrole")
    @is_admin()
    async def addrole(self, ctx, member: discord.Member, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            return await ctx.send(
                embed=EmbedFactory.error("Permission Error", "I cannot manage this role (it's higher than my highest role)")
            )
        
        await member.add_roles(role)
        await ctx.send(
            embed=EmbedFactory.success("Role Added", f"Added {role.mention} to {member.mention}")
        )
    
    @commands.command(name="removerole")
    @is_admin()
    async def removerole(self, ctx, member: discord.Member, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            return await ctx.send(
                embed=EmbedFactory.error("Permission Error", "I cannot manage this role")
            )
        
        await member.remove_roles(role)
        await ctx.send(
            embed=EmbedFactory.success("Role Removed", f"Removed {role.mention} from {member.mention}")
        )
    
    @commands.command(name="setlogchannel")
    @is_admin()
    async def setlogchannel(self, ctx, channel: discord.TextChannel):
        await self.db.update_guild_config(ctx.guild.id, log_channel=channel.id)
        await ctx.send(
            embed=EmbedFactory.success("Log Channel Set", f"Logs will be sent to {channel.mention}")
        )
    
    
    @commands.command(name="togglemodule")
    @is_admin()
    async def togglemodule(self, ctx, module: str):
        config = await self.db.get_guild_config(ctx.guild.id)
        disabled = config.disabled_modules or []
        
        if module in disabled:
            disabled.remove(module)
            status = "enabled"
        else:
            disabled.append(module)
            status = "disabled"
        
        await self.db.update_guild_config(ctx.guild.id, disabled_modules=disabled)
        await ctx.send(
            embed=EmbedFactory.success("Module Toggled", f"Module `{module}` has been {status}")
        )
    
    @commands.command(name="config")
    @is_admin()
    async def config(self, ctx):
        config = await self.db.get_guild_config(ctx.guild.id)
        
        embed = discord.Embed(
            title=f"⚙️ {ctx.guild.name} Configuration",
            color=discord.Color.blue()
        )
        
        welcome_ch = f"<#{config.welcome_channel}>" if config.welcome_channel else "Not set"
        log_ch = f"<#{config.log_channel}>" if config.log_channel else "Not set"
        dj_role = f"<@&{config.dj_role}>" if config.dj_role else "Not set"
        auto_role = f"<@&{config.auto_role}>" if config.auto_role else "Not set"
        
        embed.add_field(name="Welcome Channel", value=welcome_ch, inline=True)
        embed.add_field(name="Log Channel", value=log_ch, inline=True)
        embed.add_field(name="DJ Role", value=dj_role, inline=True)
        embed.add_field(name="Auto Role", value=auto_role, inline=True)
        embed.add_field(name="Translation", value="✅" if config.translation_enabled else "❌", inline=True)
        embed.add_field(name="XP System", value="✅" if config.xp_enabled else "❌", inline=True)
        embed.add_field(name="Anti-Spam", value="✅" if config.anti_spam else "❌", inline=True)
        embed.add_field(name="Anti-Raid", value="✅" if config.anti_raid else "❌", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="reload")
    @is_owner()
    async def reload(self, ctx, cog: str):
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await ctx.send(
                embed=EmbedFactory.success("Cog Reloaded", f"Successfully reloaded `{cog}`")
            )
        except Exception as e:
            await ctx.send(
                embed=EmbedFactory.error("Reload Failed", f"Error: {str(e)}")
            )
    
    # sync-commands removed — use /reload instead

async def setup(bot):
    await bot.add_cog(Admin(bot))
