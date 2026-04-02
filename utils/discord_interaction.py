"""Helpers to avoid HTTP 40060 when the interaction was already deferred or acknowledged."""
import discord


async def send_response(interaction: discord.Interaction, content=None, **kwargs):
    """Send via response or followup depending on whether the interaction was already answered."""
    if interaction.response.is_done():
        return await interaction.followup.send(content=content, **kwargs)
    return await interaction.response.send_message(content=content, **kwargs)
