import asyncio
import io
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image

from bot import bot as shadow_bot
from logger import LoggerManager

UPVOTE_EMOJI_NAME = os.getenv("IMAGE_UPVOTE_EMOJI_NAME", "arrow_upvote")
UPVOTE_THRESHOLD = int(os.getenv("IMAGE_UPVOTE_THRESHOLD", "4"))
UPLOAD_DIR = Path("cdn/Uploads")
THUMBNAIL_DIR = UPLOAD_DIR / "thumbnails"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
CDN_BASE_URL = "https://cdn.killua.de"
DATABASE_TABLE = "media_uploads"


logger = LoggerManager(name="ImageUpvote", level="INFO", log_file="logs/ImageUpvote.log").get_logger()


class ImageUpvote(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._uploaded_messages: set[int] = set()
        self._db_pool: Optional[asyncpg.Pool] = None

    async def cog_load(self) -> None:
        await self._initialise_database()

    async def cog_unload(self) -> None:
        if self._db_pool is not None:
            await self._db_pool.close()
            self._db_pool = None

    async def _initialise_database(self) -> None:
        db_host = os.getenv("POSTGRES_HOST", "postgres")
        db_port = int(os.getenv("POSTGRES_PORT", "5432"))
        db_name = os.getenv("POSTGRES_DB", "thebase")
        db_user = os.getenv("POSTGRES_USER", "postgres")
        db_password = os.getenv("POSTGRES_PASSWORD", "")

        try:
            self._db_pool = await asyncpg.create_pool(
                host=db_host,
                port=db_port,
                database=db_name,
                user=db_user,
                password=db_password,
                min_size=1,
                max_size=5,
                command_timeout=30,
            )
            async with self._db_pool.acquire() as connection:
                await connection.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {DATABASE_TABLE} (
                        file_id UUID PRIMARY KEY,
                        filename TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        thumbnail_path TEXT,
                        date_of_upload TIMESTAMPTZ NOT NULL,
                        file_format TEXT NOT NULL,
                        creator_name TEXT NOT NULL,
                        uploaded_by TEXT NOT NULL
                    )
                    """
                )
            logger.info("Postgres connection initialised and table ensured for image upvotes.")
        except Exception:
            logger.exception("Failed to initialise Postgres connection")
            self._db_pool = None

    @staticmethod
    def _is_supported_attachment(attachment: discord.Attachment) -> bool:
        content_type = (attachment.content_type or "").lower()
        if content_type.startswith("image") or content_type.startswith("video") or content_type.startswith("audio"):
            return True
        extension = Path(attachment.filename).suffix.lower()
        return extension in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".mkv", ".webm", ".avi", ".mp3", ".wav", ".ogg", ".flac", ".m4a"}

    async def _record_upload(
        self,
        filename: str,
        file_url: str,
        thumbnail_url: Optional[str],
        file_format: str,
        creator_name: str,
        uploaded_by: str,
    ) -> None:
        if not self._db_pool:
            logger.warning("Skipping database write for %s because pool is not initialised.", filename)
            return
        file_id = uuid.uuid4()
        date_of_upload = datetime.now(timezone.utc)
        try:
            async with self._db_pool.acquire() as connection:
                await connection.execute(
                    f"""
                    INSERT INTO {DATABASE_TABLE} (
                        file_id,
                        filename,
                        file_path,
                        thumbnail_path,
                        date_of_upload,
                        file_format,
                        creator_name,
                        uploaded_by
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    file_id,
                    filename,
                    file_url,
                    thumbnail_url,
                    date_of_upload,
                    file_format,
                    creator_name,
                    uploaded_by,
                )
        except Exception:
            logger.exception("Failed to record upload metadata for %s", filename)

    @staticmethod
    def _build_file_stem(message: discord.Message, index: int) -> str:
        return f"{message.author.id}-{message.id}_{index:02d}"

    async def _save_image(self, data: bytes, file_stem: str) -> tuple[Path, Optional[Path], str]:
        try:
            with Image.open(io.BytesIO(data)) as img:
                img_format = img.format or ""
                img_extension = f".{img_format.lower()}" if img_format else Path(img.filename or "").suffix
                if img_format == "GIF":
                    file_path = UPLOAD_DIR / f"{file_stem}.gif"
                    file_path.write_bytes(data)
                    img.seek(0)
                    frame = img.convert("RGBA")
                    frame.thumbnail((512, 512))
                    thumbnail_path = THUMBNAIL_DIR / f"{file_stem}.webp"
                    frame.save(thumbnail_path, "WEBP")
                    return file_path, thumbnail_path, ".gif"
                if img_format == "WEBP":
                    file_path = UPLOAD_DIR / f"{file_stem}.webp"
                    file_path.write_bytes(data)
                    thumbnail_path = THUMBNAIL_DIR / f"{file_stem}.webp"
                    preview = img.copy()
                    preview.thumbnail((512, 512))
                    preview.save(thumbnail_path, "WEBP")
                    return file_path, thumbnail_path, ".webp"
                file_path = UPLOAD_DIR / f"{file_stem}.webp"
                converted = img.convert("RGBA") if img.mode not in {"RGB", "RGBA"} else img
                converted.save(file_path, "WEBP")
                thumbnail_path = THUMBNAIL_DIR / f"{file_stem}.webp"
                thumb_image = converted.copy()
                thumb_image.thumbnail((512, 512))
                thumb_image.save(thumbnail_path, "WEBP")
                return file_path, thumbnail_path, ".webp"
        except Exception as exc:
            raise RuntimeError(f"Failed to process image: {exc}") from exc

    async def _save_video(self, data: bytes, file_stem: str, source_extension: str) -> tuple[Path, Optional[Path], str]:
        file_path = UPLOAD_DIR / f"{file_stem}.mp4"
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=source_extension or ".tmp") as temp_file:
                temp_file.write(data)
                temp_path = Path(temp_file.name)
            process = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-y",
                "-i",
                str(temp_path),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "22",
                "-c:a",
                "aac",
                str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()
            if process.returncode != 0:
                raise RuntimeError(stderr.decode())
            thumbnail_path = THUMBNAIL_DIR / f"{file_stem}.webp"
            thumb_process = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-y",
                "-i",
                str(file_path),
                "-vf",
                "thumbnail,scale=512:-1",
                "-frames:v",
                "1",
                str(thumbnail_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, thumb_stderr = await thumb_process.communicate()
            if thumb_process.returncode != 0:
                raise RuntimeError(thumb_stderr.decode())
            return file_path, thumbnail_path, ".mp4"
        except Exception as exc:
            raise RuntimeError(f"Failed to process video: {exc}") from exc
        finally:
            if temp_path:
                temp_path.unlink(missing_ok=True)

    async def _save_audio(self, data: bytes, file_stem: str, source_extension: str) -> tuple[Path, Optional[Path], str]:
        file_path = UPLOAD_DIR / f"{file_stem}.mp3"
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=source_extension or ".tmp") as temp_file:
                temp_file.write(data)
                temp_path = Path(temp_file.name)
            process = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-y",
                "-i",
                str(temp_path),
                "-vn",
                "-ar",
                "44100",
                "-ac",
                "2",
                "-b:a",
                "192k",
                str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()
            if process.returncode != 0:
                raise RuntimeError(stderr.decode())
            return file_path, None, ".mp3"
        except Exception as exc:
            raise RuntimeError(f"Failed to process audio: {exc}") from exc
        finally:
            if temp_path:
                temp_path.unlink(missing_ok=True)

    async def handle_upload(
            self,
            message: discord.Message,
            source: str,
            interaction: discord.Interaction | None = None,
    ) -> bool:
        media_attachments = [
            att
            for att in message.attachments
            if self._is_supported_attachment(att)
        ]
        admin_log_cog = (
            interaction.client.get_cog("AdminLog")
            if interaction
            else self.bot.get_cog("AdminLog")
        )
        any_success = False
        uploader_name = (
            interaction.user.display_name if source == "force" and interaction else "upvoted"
        )
        for idx, attachment in enumerate(media_attachments, start=1):
            data = await attachment.read()
            extension = Path(attachment.filename).suffix.lower()
            file_stem = self._build_file_stem(message, idx)
            try:
                content_type = (attachment.content_type or "").lower()
                if content_type.startswith("image") or extension in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
                    file_path, thumbnail_path, file_format = await self._save_image(data, file_stem)
                elif content_type.startswith("video") or extension in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
                    file_path, thumbnail_path, file_format = await self._save_video(data, file_stem, extension)
                elif content_type.startswith("audio") or extension in {".mp3", ".wav", ".ogg", ".flac", ".m4a"}:
                    file_path, thumbnail_path, file_format = await self._save_audio(data, file_stem, extension)
                else:
                    raise ValueError("Unsupported content type")
                size_mb = file_path.stat().st_size / (1024 * 1024)
                url = f"{CDN_BASE_URL}/{file_path.parent.name}/{file_path.name}"
                thumb_url = (
                    f"{CDN_BASE_URL}/{thumbnail_path.parent.name}/{thumbnail_path.name}"
                    if thumbnail_path
                    else None
                )
                await self._record_upload(
                    filename=file_path.name,
                    file_url=url,
                    thumbnail_url=thumb_url,
                    file_format=file_format,
                    creator_name=message.author.display_name,
                    uploaded_by=uploader_name,
                )
                logger.info(
                    f"Saved message {message.id} attachment as {file_path.name}."
                )
                any_success = True
                if admin_log_cog:
                    event = (
                        "Media force uploaded"
                        if source == "force"
                        else "Media uploaded via upvotes"
                    )
                    event_lines = [
                        f"{file_path.name} - {size_mb:.2f} MB",
                        url,
                    ]
                    if thumb_url:
                        event_lines.append(f"Thumbnail: {thumb_url}")
                    if source == "force" and interaction:
                        event_lines.append(
                            f"Force by {interaction.user.mention} in {message.channel.mention}"
                        )
                    event_lines.append(f"Uploaded by: {uploader_name}")
                    event_lines.append(message.jump_url)
                    event_status = "\n".join(event_lines)
                    await admin_log_cog.log_event(
                        message.guild.id,
                        priority="info",
                        event_name=event,
                        event_status=event_status,
                    )
            except Exception as exc:
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
            self._uploaded_messages.add(message.id)
            try:
                await message.add_reaction("✅")
            except discord.HTTPException:
                logger.warning("Failed to add success reaction for message %s", message.id)
        else:
            if not any(
                    str(reaction.emoji) == "❎" and reaction.me
                    for reaction in message.reactions
            ):
                try:
                    await message.add_reaction("❎")
                except discord.HTTPException:
                    pass
        return any_success

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
        if any(str(reaction.emoji) == "✅" for reaction in message.reactions):
            return
        if message.id in self._uploaded_messages:
            return
        if not any(
                self._is_supported_attachment(att)
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
    cog = interaction.client.get_cog("ImageUpvote")
    if not cog:
        await interaction.response.send_message("Image upvote system is not loaded.", ephemeral=True)
        return
    if not any(
        cog._is_supported_attachment(att)
        for att in message.attachments
    ):
        await interaction.response.send_message(
            "The selected message does not contain an image, video, or audio.",
            ephemeral=True,
        )
        return
    await interaction.response.defer(ephemeral=True)
    success = await cog.handle_upload(message, source="force", interaction=interaction)
    if success:
        await interaction.followup.send("Image saved to CDN.", ephemeral=True)
    else:
        await interaction.followup.send("Failed to save any attachments.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ImageUpvote(bot))
