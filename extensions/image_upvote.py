import discord
from discord.ext import commands
from discord import app_commands
from bot import bot as shadow_bot
from logger import LoggerManager
import os
import io
import asyncio
import tempfile
from pathlib import Path
from PIL import Image
import json

UPVOTE_EMOJI_NAME = os.getenv("IMAGE_UPVOTE_EMOJI_NAME", "arrow_upvote")
UPVOTE_THRESHOLD = int(os.getenv("IMAGE_UPVOTE_THRESHOLD", "4"))
UPLOAD_DIR = Path("cdn/Uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CDN_BASE_URL = "https://cdn.killua.de"
LINKS_FILE = UPLOAD_DIR / "links.json"
if not LINKS_FILE.exists():
    LINKS_FILE.write_text("[]")


def rebuild_links_index() -> None:
    files = [
        f"{CDN_BASE_URL}/{UPLOAD_DIR.name}/{p.name}"
        for p in sorted(UPLOAD_DIR.iterdir())
        if p.is_file() and p.name != LINKS_FILE.name
    ]
    LINKS_FILE.write_text(json.dumps(files, indent=2))

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
        attachments = [
            att
            for att in message.attachments
            if att.content_type
            and (
                att.content_type.startswith("image")
                or att.content_type.startswith("video")
                or att.content_type.startswith("audio")
            )
        ]
        admin_log_cog = (
            interaction.client.get_cog("AdminLog")
            if interaction
            else self.bot.get_cog("AdminLog")
        )
        any_failure = False
        any_success = False
        for idx, attachment in enumerate(attachments, start=1):
            data = await attachment.read()
            extension = Path(attachment.filename).suffix
            file_stem = f"{message.author.id}-{message.id}_{idx:02d}"
            try:
                if attachment.content_type.startswith("image"):
                    with Image.open(io.BytesIO(data)) as img:
                        img_format = img.format
                        if img_format == "GIF":
                            file_path = UPLOAD_DIR / f"{file_stem}.gif"
                            file_path.write_bytes(data)
                        elif img_format == "WEBP":
                            file_path = UPLOAD_DIR / f"{file_stem}.webp"
                            file_path.write_bytes(data)
                        else:
                            file_path = UPLOAD_DIR / f"{file_stem}.webp"
                            img.save(file_path, "WEBP")
                elif attachment.content_type.startswith("video"):
                    file_path = UPLOAD_DIR / f"{file_stem}.mp4"
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=extension
                    ) as temp_file:
                        temp_file.write(data)
                        temp_path = Path(temp_file.name)
                    process = await asyncio.create_subprocess_exec(
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(temp_path),
                        str(file_path),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    _, stderr = await process.communicate()
                    temp_path.unlink(missing_ok=True)
                    if process.returncode != 0:
                        raise RuntimeError(stderr.decode())
                elif attachment.content_type.startswith("audio"):
                    file_path = UPLOAD_DIR / f"{file_stem}.mp3"
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=extension
                    ) as temp_file:
                        temp_file.write(data)
                        temp_path = Path(temp_file.name)
                    process = await asyncio.create_subprocess_exec(
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(temp_path),
                        str(file_path),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    _, stderr = await process.communicate()
                    temp_path.unlink(missing_ok=True)
                    if process.returncode != 0:
                        raise RuntimeError(stderr.decode())
                else:
                    raise ValueError("Unsupported content type")
                size_mb = file_path.stat().st_size / (1024 * 1024)
                url = f"{CDN_BASE_URL}/{file_path.parent.name}/{file_path.name}"
                logger.info(
                    f"Saved message {message.id} attachment as {file_path.name}."
                )
                if admin_log_cog:
                    event = (
                        "Media force uploaded"
                        if source == "force"
                        else "Media uploaded via upvotes"
                    )
                    if source == "force" and interaction:
                        event_status = (
                            f"{file_path.name} - {size_mb:.2f} MB\n"
                            f"{url}\n"
                            f"Force by {interaction.user.mention} in {message.channel.mention}\n"
                            f"{message.jump_url}"
                        )
                    else:
                        event_status = (
                            f"{file_path.name} - {size_mb:.2f} MB\n"
                            f"{url}\n"
                            f"{message.jump_url}"
                        )
                    await admin_log_cog.log_event(
                        message.guild.id,
                        priority="info",
                        event_name=event,
                        event_status=event_status,
                    )
                any_success = True
            except Exception as exc:
                any_failure = True
                logger.error(
                    f"Failed to save attachment {attachment.filename} from message {message.id}: {exc}"
                )
                if admin_log_cog:
                    await admin_log_cog.log_event(
                        message.guild.id,
                        priority="error",
                        event_name="Media upload failed",
                        event_status=(
                            f"{attachment.filename}\n"
                            f"{message.jump_url}\n"
                            f"Reason: {exc}"
                        ),
                    )
                continue
        if any_success:
            rebuild_links_index()
        self._uploaded_messages.add(message.id)
        if any_failure:
            await message.add_reaction("❎")
        else:
            await message.add_reaction("✅")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
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
        if any(str(reaction.emoji) in {"✅", "❎"} for reaction in message.reactions):
            return
        if message.id in self._uploaded_messages:
            return
        if not any(
                att.content_type
                and (
                    att.content_type.startswith("image")
                    or att.content_type.startswith("video")
                    or att.content_type.startswith("audio")
                )
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
    logger.info(
        f"Force upload triggered by {interaction.user} in {message.channel} ({message.jump_url})"
    )
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("You do not have permission to use this.", ephemeral=True)
        return
    if not any(
        att.content_type
        and (
            att.content_type.startswith("image")
            or att.content_type.startswith("video")
            or att.content_type.startswith("audio")
        )
        for att in message.attachments
    ):
        await interaction.response.send_message(
            "The selected message does not contain an image, video, or audio.",
            ephemeral=True,
        )
        return
    cog = interaction.client.get_cog("ImageUpvote")
    if not cog:
        await interaction.response.send_message("Image upvote system is not loaded.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    await cog.handle_upload(message, source="force", interaction=interaction)
    await interaction.followup.send("Media saved to CDN.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ImageUpvote(bot))
