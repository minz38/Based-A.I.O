import discord
from discord.ext import commands
from discord import app_commands
from bot import bot as shadow_bot
from logger import LoggerManager
import os
from pathlib import Path

CHANNEL_ID = int(os.getenv("IMAGE_UPVOTE_CHANNEL_ID", "1003337674008055919"))
UPVOTE_EMOJI_NAME = os.getenv("IMAGE_UPVOTE_EMOJI_NAME", "arrow_upvote")
UPVOTE_THRESHOLD = int(os.getenv("IMAGE_UPVOTE_THRESHOLD", "4"))
UPLOAD_DIR = Path("cdn/ImageUploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

logger = LoggerManager(name="ImageUpvote", level="INFO", log_file="logs/ImageUpvote.log").get_logger()


class ImageUpvote(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._uploaded_messages: set[int] = set()

    async def handle_upload(
            self,
            message: discord.Message,
            source: str,
            interaction: discord.Interaction | None = None,
    ) -> None:
        images = [
            att
            for att in message.attachments
            if att.content_type and att.content_type.startswith("image")
        ]
        admin_log_cog = (
            interaction.client.get_cog("AdminLog")
            if interaction
            else self.bot.get_cog("AdminLog")
        )
        for idx, attachment in enumerate(images, start=1):
            data = await attachment.read()
            size_mb = len(data) / (1024 * 1024)
            extension = Path(attachment.filename).suffix
            file_path = UPLOAD_DIR / (
                f"{message.author.id}-{message.id}_{idx:02d}{extension}"
            )
            with open(file_path, "wb") as f:
                f.write(data)
            logger.info(
                f"Saved message {message.id} attachment as {file_path.name}."
            )
            if admin_log_cog:
                event = (
                    "Image force uploaded"
                    if source == "force"
                    else "Image uploaded via upvotes"
                )
                await admin_log_cog.log_event(
                    message.guild.id,
                    priority="info",
                    event_name=event,
                    event_status=f"{file_path.name} - {size_mb:.2f} MB",
                )
        self._uploaded_messages.add(message.id)
        await message.add_reaction("✅")

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
        if any(str(reaction.emoji) == "✅" for reaction in message.reactions):
            return
        if message.id in self._uploaded_messages:
            return
        if not any(
                att.content_type and att.content_type.startswith("image")
                for att in message.attachments
        ):
            return
        arrow_count = 0
        for reaction in message.reactions:
            emoji_name = (
                reaction.emoji.name
                if hasattr(reaction.emoji, "name")
                else str(reaction.emoji)
            )
            if emoji_name == UPVOTE_EMOJI_NAME:
                arrow_count = reaction.count
                break
        if arrow_count >= UPVOTE_THRESHOLD:
            await self.handle_upload(message, source="upvote")


@shadow_bot.tree.context_menu(name="Force Upload")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.guild_only()
async def force_upload(interaction: discord.Interaction, message: discord.Message) -> None:
    logger.info(f"Force upload triggered by {interaction.user} for message {message.id}")
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("You do not have permission to use this.", ephemeral=True)
        return
    if message.channel.id != CHANNEL_ID:
        await interaction.response.send_message("This command can only be used in the configured channel.",
                                                ephemeral=True)
        return
    if not any(att.content_type and att.content_type.startswith("image") for att in message.attachments):
        await interaction.response.send_message("The selected message does not contain an image.", ephemeral=True)
        return
    cog = interaction.client.get_cog("ImageUpvote")
    if not cog:
        await interaction.response.send_message("Image upvote system is not loaded.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    await cog.handle_upload(message, source="force", interaction=interaction)
    await interaction.followup.send("Image saved to CDN.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ImageUpvote(bot))
