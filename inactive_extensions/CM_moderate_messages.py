import discord
from bot import bot as shadow_bot
from logger import LoggerManager
from dependencies.audit_logger import log_interaction

logger = LoggerManager(name="Moderation", level="INFO", log_file="logs/mod.log").get_logger()


class ReasonForModerationModal(discord.ui.Modal):
    def __init__(self, message: discord.Message, shadow_interaction: discord.Interaction):
        super().__init__(title="Reason for Moderation", custom_id="reason_for_moderation")
        self.message = message
        self.shadow_interaction = shadow_interaction
        self.reason = discord.ui.TextInput(
            label="Reason:", placeholder="Enter reason for deleting this message...", required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.value
        try:
            logger.info(
                f"Message from {self.message.author.name} deleted by {interaction.user.name} for reason: {reason}")
            await log_interaction(self.shadow_interaction, "audit", reason)
            await self.message.delete()
            await interaction.response.send_message("Message deleted successfully.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to delete messages.", ephemeral=True)
            logger.error("Bot lacks permissions to delete messages.")


@shadow_bot.tree.context_menu(name="Delete Message")
async def delete_message(interaction: discord.Interaction, message: discord.Message):
    """ Prompts for a reason before deleting the given message. """
    await interaction.response.send_modal(ReasonForModerationModal(message=message, shadow_interaction=interaction))


@shadow_bot.tree.context_menu(name="Pin Message")
async def pin_message(interaction: discord.Interaction, message: discord.Message):
    """Pins the given message to the top of the channel's message list."""
    if not message.pinned:
        try:
            await message.pin()
            await interaction.response.send_message("Message pinned successfully.", ephemeral=True)
            logger.info(f"Message: {message.id} pinned by {interaction.user.name} in channel: {message.channel.name}")
            await log_interaction(
                interaction,
                "audit",
                f""
            )

        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to pin messages.", ephemeral=True)
            logger.error("Bot lacks permissions to pin messages.")

    else:
        await interaction.response.send_message("Message is already pinned.", ephemeral=True)


@shadow_bot.tree.context_menu(name="Unpin Message")
async def unpin_message(interaction: discord.Interaction, message: discord.Message):
    """Unpins the given message from the channel's message list."""
    if message.pinned:
        try:
            await message.unpin()
            await interaction.response.send_message("Message unpinned successfully.", ephemeral=True)
            logger.info(f"Message: {message.id} unpinned by {interaction.user.name} in channel: {message.channel.name}")
            await log_interaction(
                interaction,
                "audit",
                f""
            )

        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to unpin messages.", ephemeral=True)
            logger.error("Bot lacks permissions to unpin messages.")

    else:
        await interaction.response.send_message("Message is not pinned.", ephemeral=True)
