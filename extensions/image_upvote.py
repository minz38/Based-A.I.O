import discord
from discord.ext import commands
from discord import app_commands
from bot import bot as shadow_bot
from logger import LoggerManager
import os
from pathlib import Path

CHANNEL_ID = int(os.getenv("IMAGE_UPVOTE_CHANNEL_ID", "1003337674008055919"))
UPVOTE_EMOJI_NAME = os.getenv("IMAGE_UPVOTE_EMOJI_NAME", "arrow_upvote")
UPVOTE_THRESHOLD = int(os.getenv("IMAGE_UPVOTE_THRESHOLD", "5"))
UPLOAD_DIR = Path("cdn/ImageUploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

logger = LoggerManager(name="ImageUpvote", level="INFO", log_file="logs/ImageUpvote.log").get_logger()


class ImageUpvote(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._uploaded_messages: set[int] = set()

    async def handle_upload(self, message: discord.Message) -> None:
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith("image"):
                data = await attachment.read()
                file_path = UPLOAD_DIR / f"{message.id}_{attachment.filename}"
                with open(file_path, "wb") as f:
                    f.write(data)
        logger.info(f"Saved message {message.id} attachments to {UPLOAD_DIR}.")
        self._uploaded_messages.add(message.id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.channel_id != CHANNEL_ID:
            return
        if payload.emoji.name != UPVOTE_EMOJI_NAME:
            return
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return
        if message.id in self._uploaded_messages:
            return
        if not any(att.content_type and att.content_type.startswith("image") for att in message.attachments):
            return
        for reaction in message.reactions:
            emoji_name = reaction.emoji.name if hasattr(reaction.emoji, "name") else str(reaction.emoji)
            if emoji_name == UPVOTE_EMOJI_NAME and reaction.count >= UPVOTE_THRESHOLD:
                await self.handle_upload(message)
                break


@shadow_bot.tree.context_menu(name="Force Upload")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.guild_only()
async def force_upload(interaction: discord.Interaction, message: discord.Message) -> None:
    logger.info(f"Force upload triggered by {interaction.user} for message {message.id}")
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("You do not have permission to use this.", ephemeral=True)
        return
    if message.channel.id != CHANNEL_ID:
        await interaction.response.send_message("This command can only be used in the configured channel.", ephemeral=True)
        return
    if not any(att.content_type and att.content_type.startswith("image") for att in message.attachments):
        await interaction.response.send_message("The selected message does not contain an image.", ephemeral=True)
        return
    cog = interaction.client.get_cog("ImageUpvote")
    if not cog:
        await interaction.response.send_message("Image upvote system is not loaded.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    await cog.handle_upload(message)
    await interaction.followup.send("Image saved to CDN.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ImageUpvote(bot))
