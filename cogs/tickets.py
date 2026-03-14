import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils.permissions import is_admin, is_moderator
from datetime import datetime
import asyncio

logger = logging.getLogger('discord_bot.tickets')

class TicketView(discord.ui.View):
    """View with ticket control buttons"""
    
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the ticket"""
        # Check if user is staff or ticket owner
        if not (interaction.user.guild_permissions.manage_channels or 
                interaction.channel.name.endswith(str(interaction.user.id))):
            return await interaction.response.send_message(
                "❌ Only staff or the ticket owner can close this ticket!",
                ephemeral=True
            )
        
        # Create transcript
        transcript = []
        async for message in interaction.channel.history(limit=100, oldest_first=True):
            transcript.append(f"[{message.created_at}] {message.author}: {message.content}")
        
        # Send transcript to logs if configured
        # For now, just close the channel
        
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete(reason="Ticket closed")

class Tickets(commands.Cog):
    """Ticket System - Support tickets with private channels"""
    
    def __init__(self, bot):
        self.bot = bot
        self.ticket_category = {}  # {guild_id: category_id}
        self.support_role = {}  # {guild_id: role_id}
        self.ticket_counter = {}  # {guild_id: counter}
    
    @app_commands.command(name="ticket-setup", description="[Admin] Set up the ticket system")
    @is_admin()
    async def setup_tickets(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel = None,
        support_role: discord.Role = None
    ):
        """Set up ticket system"""
        
        # Create category if not provided
        if not category:
            category = await interaction.guild.create_category("Tickets")
        
        self.ticket_category[interaction.guild.id] = category.id
        
        if support_role:
            self.support_role[interaction.guild.id] = support_role.id
        
        self.ticket_counter[interaction.guild.id] = 0
        
        # Create ticket creation channel
        channel = await category.create_text_channel("create-ticket")
        
        embed = discord.Embed(
            title="🎫 Support Tickets",
            description="Need help? Create a support ticket!\n\nClick the button below to open a private ticket channel.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="What are tickets?",
            value="Tickets create a private channel where you can talk to staff privately.",
            inline=False
        )
        embed.add_field(
            name="When to use tickets",
            value="• Report issues\n• Ask for help\n• Appeal bans\n• Suggest features\n• Any private matter",
            inline=False
        )
        
        view = discord.ui.View(timeout=None)
        button = discord.ui.Button(
            label="Create Ticket",
            style=discord.ButtonStyle.green,
            custom_id="create_ticket",
            emoji="🎫"
        )
        
        async def create_ticket_callback(interaction: discord.Interaction):
            await self.create_ticket(interaction)
        
        button.callback = create_ticket_callback
        view.add_item(button)
        
        await channel.send(embed=embed, view=view)
        
        setup_embed = discord.Embed(
            title="✅ Ticket System Enabled",
            description=f"Tickets will be created in {category.mention}",
            color=discord.Color.green()
        )
        setup_embed.add_field(
            name="Ticket Channel",
            value=channel.mention,
            inline=True
        )
        if support_role:
            setup_embed.add_field(
                name="Support Role",
                value=support_role.mention,
                inline=True
            )
        
        await interaction.response.send_message(embed=setup_embed)
    
    async def create_ticket(self, interaction: discord.Interaction):
        """Create a new ticket"""
        
        guild_id = interaction.guild.id
        
        if guild_id not in self.ticket_category:
            return await interaction.response.send_message(
                "❌ Ticket system not set up! Ask an admin to run `/ticket-setup`",
                ephemeral=True
            )
        
        # Check if user already has an open ticket
        category = self.bot.get_channel(self.ticket_category[guild_id])
        if category:
            for channel in category.text_channels:
                if channel.name.endswith(str(interaction.user.id)):
                    return await interaction.response.send_message(
                        f"❌ You already have an open ticket: {channel.mention}",
                        ephemeral=True
                    )
        
        # Increment counter
        self.ticket_counter[guild_id] = self.ticket_counter.get(guild_id, 0) + 1
        ticket_num = self.ticket_counter[guild_id]
        
        # Create ticket channel
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                attach_files=True,
                embed_links=True
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_channels=True
            )
        }
        
        # Add support role if configured
        if guild_id in self.support_role:
            role = interaction.guild.get_role(self.support_role[guild_id])
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True
                )
        
        channel = await category.create_text_channel(
            name=f"ticket-{ticket_num}-{interaction.user.id}",
            overwrites=overwrites,
            reason=f"Ticket created by {interaction.user}"
        )
        
        # Send welcome message
        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_num}",
            description=f"Welcome {interaction.user.mention}!\n\nSupport staff will be with you shortly.\nPlease describe your issue in detail.",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Ticket created by {interaction.user}")
        
        view = TicketView(self.bot)
        await channel.send(f"{interaction.user.mention}", embed=embed, view=view)
        
        # Notify support role
        if guild_id in self.support_role:
            role = interaction.guild.get_role(self.support_role[guild_id])
            if role:
                await channel.send(f"{role.mention} New ticket opened!")
        
        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True
        )
    
    @app_commands.command(name="ticket-close", description="Close the current ticket")
    async def close_ticket_command(self, interaction: discord.Interaction):
        """Close a ticket via command"""
        
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(
                "❌ This is not a ticket channel!",
                ephemeral=True
            )
        
        # Check permissions
        if not (interaction.user.guild_permissions.manage_channels or 
                interaction.channel.name.endswith(str(interaction.user.id))):
            return await interaction.response.send_message(
                "❌ Only staff or the ticket owner can close this ticket!",
                ephemeral=True
            )
        
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
    
    @app_commands.command(name="ticket-add", description="[Moderator] Add a user to the ticket")
    @is_moderator()
    async def add_to_ticket(self, interaction: discord.Interaction, user: discord.Member):
        """Add a user to the current ticket"""
        
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(
                "❌ This is not a ticket channel!",
                ephemeral=True
            )
        
        await interaction.channel.set_permissions(
            user,
            read_messages=True,
            send_messages=True
        )
        
        await interaction.response.send_message(
            f"✅ Added {user.mention} to this ticket"
        )
    
    @app_commands.command(name="ticket-remove", description="[Moderator] Remove a user from the ticket")
    @is_moderator()
    async def remove_from_ticket(self, interaction: discord.Interaction, user: discord.Member):
        """Remove a user from the current ticket"""
        
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(
                "❌ This is not a ticket channel!",
                ephemeral=True
            )
        
        await interaction.channel.set_permissions(
            user,
            overwrite=None
        )
        
        await interaction.response.send_message(
            f"✅ Removed {user.mention} from this ticket"
        )

async def setup(bot):
    await bot.add_cog(Tickets(bot))
