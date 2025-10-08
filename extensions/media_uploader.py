import asyncio
import io
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import asyncpg
import boto3
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageSequence

from bot import bot as shadow_bot
from logger import LoggerManager

UPVOTE_EMOJI_NAME = os.getenv("IMAGE_UPVOTE_EMOJI_NAME", "arrow_upvote")
UPVOTE_THRESHOLD = int(os.getenv("IMAGE_UPVOTE_THRESHOLD", "4"))
S3_ENDPOINT = os.getenv("IMAGE_UPVOTE_S3_ENDPOINT")
S3_BUCKET = os.getenv("IMAGE_UPVOTE_S3_BUCKET")
S3_ACCESS_KEY = os.getenv("IMAGE_UPVOTE_S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("IMAGE_UPVOTE_S3_SECRET_KEY")
S3_REGION = os.getenv("IMAGE_UPVOTE_S3_REGION")
DATABASE_TABLE = "media_uploads"

logger = LoggerManager(name="ImageUpvote", level="INFO", log_file="logs/ImageUpvote.log").get_logger()


class ImageUpvote(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._uploaded_messages: set[int] = set()
        self._db_pool: Optional[asyncpg.Pool] = None
        self._s3_client = None
        self._s3_bucket: Optional[str] = None
        self._s3_url_prefix: Optional[str] = None

    async def cog_load(self) -> None:
        await self._initialise_database()
        self._initialise_s3()

    async def cog_unload(self) -> None:
        if self._db_pool is not None:
            await self._db_pool.close()
            self._db_pool = None

    async def _initialise_database(self) -> None:
        db_host = os.getenv("POSTGRES_HOST", "postgres")
        db_port = int(os.getenv("POSTGRES_PORT", "5432"))
        db_name = os.getenv("POSTGRES_DB", "thebase")
        db_user = os.getenv("POSTGRES_USER", "based")
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

    def _initialise_s3(self) -> None:
        if not all([S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY]):
            logger.error("S3 configuration is incomplete; uploads will be skipped.")
            return
        try:
            session = boto3.session.Session()
            self._s3_client = session.client(
                "s3",
                endpoint_url=S3_ENDPOINT,
                aws_access_key_id=S3_ACCESS_KEY,
                aws_secret_access_key=S3_SECRET_KEY,
                region_name=S3_REGION,
            )
            self._s3_bucket = S3_BUCKET
            endpoint = S3_ENDPOINT.rstrip("/")
            bucket = S3_BUCKET.strip("/")
            self._s3_url_prefix = f"{endpoint}/{bucket}"
            logger.info("S3 client initialised for image upvotes.")
        except Exception:
            logger.exception("Failed to initialise S3 client")
            self._s3_client = None
            self._s3_bucket = None
            self._s3_url_prefix = None

    @staticmethod
    def _is_supported_attachment(attachment: discord.Attachment) -> bool:
        content_type = (attachment.content_type or "").lower()
        if content_type.startswith("image") or content_type.startswith("video") or content_type.startswith("audio"):
            return True
        extension = Path(attachment.filename).suffix.lower()
        return extension in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".mkv", ".webm", ".avi", ".mp3",
                             ".wav", ".ogg", ".flac", ".m4a"}

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

    async def _upload_to_s3(self, local_path: Path, object_key: str, content_type: str) -> str:
        if not self._s3_client or not self._s3_bucket or not self._s3_url_prefix:
            raise RuntimeError("S3 client not configured")

        def _upload() -> None:
            extra_args = {"ContentType": content_type} if content_type else None
            if extra_args:
                self._s3_client.upload_file(
                    str(local_path),
                    self._s3_bucket,
                    object_key,
                    ExtraArgs=extra_args,
                )
            else:
                self._s3_client.upload_file(
                    str(local_path),
                    self._s3_bucket,
                    object_key,
                )

        await asyncio.to_thread(_upload)
        return f"{self._s3_url_prefix}/{object_key}"

    @staticmethod
    def _content_type_for_extension(extension: str) -> str:
        mapping = {
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".mp4": "video/mp4",
            ".mp3": "audio/mpeg",
        }
        return mapping.get(extension.lower(), "application/octet-stream")

    def _extract_key_from_url(self, url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        if self._s3_url_prefix:
            prefix = self._s3_url_prefix.rstrip("/") + "/"
            if url.startswith(prefix):
                return url[len(prefix):]
        parsed = urlparse(url)
        path = parsed.path.lstrip("/")
        if not path:
            return None
        if self._s3_bucket:
            bucket = self._s3_bucket.strip("/")
            if path.startswith(f"{bucket}/"):
                path = path[len(bucket) + 1:]
        return path or None

    async def _delete_s3_object(self, object_key: str) -> None:
        if not self._s3_client or not self._s3_bucket:
            raise RuntimeError("S3 client not configured")

        def _delete() -> None:
            self._s3_client.delete_object(Bucket=self._s3_bucket, Key=object_key)

        await asyncio.to_thread(_delete)

    async def _save_image(self, data: bytes, file_stem: str) -> tuple[Path, Optional[Path], str]:
        try:
            with Image.open(io.BytesIO(data)) as img:
                fd, webp_path = tempfile.mkstemp(suffix=".webp")
                os.close(fd)
                file_path = Path(webp_path)

                if getattr(img, "is_animated", False):
                    frames = []
                    durations: list[int] = []
                    for frame in ImageSequence.Iterator(img):
                        frames.append(frame.convert("RGBA"))
                        durations.append(int(frame.info.get("duration", img.info.get("duration", 0)) or 0))
                    base_frame = frames[0]
                    save_kwargs: dict[str, Any] = {
                        "format": "WEBP",
                        "save_all": True,
                        "append_images": frames[1:],
                        "loop": img.info.get("loop", 0),
                        "duration": durations,
                        "lossless": True,
                    }
                    base_frame.save(file_path, **save_kwargs)
                else:
                    converted = img.convert("RGBA") if img.mode not in {"RGB", "RGBA"} else img.copy()
                    converted.save(file_path, "WEBP", lossless=True)
                    base_frame = converted

                fd_thumb, thumb_path = tempfile.mkstemp(suffix=".webp")
                os.close(fd_thumb)
                thumbnail_path = Path(thumb_path)
                thumb_image = base_frame.copy()
                thumb_image.thumbnail((512, 512))
                thumb_image.save(thumbnail_path, "WEBP", lossless=True)
                return file_path, thumbnail_path, ".webp"
        except Exception as exc:
            raise RuntimeError(f"Failed to process image: {exc}") from exc

    async def _save_video(
            self,
            data: bytes,
            file_stem: str,
            source_extension: str,
            content_type: str,
    ) -> tuple[Path, Optional[Path], str]:
        extension = (source_extension or "").lower()
        ctype = (content_type or "").lower()
        is_mp4 = extension == ".mp4" or ctype == "video/mp4"
        file_path: Optional[Path] = None
        input_temp: Optional[Path] = None
        try:
            if is_mp4:
                fd_dest, dest_path = tempfile.mkstemp(suffix=".mp4")
                os.close(fd_dest)
                file_path = Path(dest_path)
                file_path.write_bytes(data)
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix=extension or ".tmp") as temp_file:
                    temp_file.write(data)
                    input_temp = Path(temp_file.name)
                fd_dest, dest_path = tempfile.mkstemp(suffix=".mp4")
                os.close(fd_dest)
                file_path = Path(dest_path)
                process = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(input_temp),
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

            fd_thumb, thumb_path = tempfile.mkstemp(suffix=".webp")
            os.close(fd_thumb)
            thumbnail_path = Path(thumb_path)
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
            if input_temp:
                input_temp.unlink(missing_ok=True)

    async def _save_audio(self, data: bytes, file_stem: str, source_extension: str) -> tuple[Path, Optional[Path], str]:
        fd_dest, dest_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd_dest)
        file_path = Path(dest_path)
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

    async def delete_media_entry(self, file_id_str: str) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
        if not self._db_pool:
            return False, "Database connection is not initialised.", None
        if not self._s3_client or not self._s3_bucket:
            return False, "S3 client is not configured.", None
        try:
            file_uuid = uuid.UUID(file_id_str)
        except ValueError:
            return False, "The provided file_id is not a valid UUID.", None

        try:
            async with self._db_pool.acquire() as connection:
                record = await connection.fetchrow(
                    f"""
                        SELECT file_id,
                               filename,
                               file_path,
                               thumbnail_path,
                               file_format,
                               creator_name,
                               uploaded_by,
                               date_of_upload
                        FROM {DATABASE_TABLE}
                        WHERE file_id=$1
                    """,
                    file_uuid,
                )
        except Exception:
            logger.exception("Failed to fetch media metadata for %s", file_id_str)
            return False, "Failed to query media metadata.", None

        if record is None:
            return False, "No media entry found for that file_id.", None

        main_key = self._extract_key_from_url(record["file_path"])
        thumb_key = self._extract_key_from_url(record["thumbnail_path"])
        if not main_key:
            return False, "Could not determine the S3 object key for the media file.", None

        metadata: dict[str, Any] = {
            "file_id": str(record["file_id"]),
            "filename": record["filename"],
            "file_url": record["file_path"],
            "thumbnail_url": record["thumbnail_path"],
            "file_format": record["file_format"],
            "creator_name": record["creator_name"],
            "uploaded_by": record["uploaded_by"],
            "date_of_upload": record["date_of_upload"],
        }

        try:
            await self._delete_s3_object(main_key)
            if thumb_key:
                await self._delete_s3_object(thumb_key)
        except Exception as exc:
            logger.exception("Failed to delete S3 objects for %s", file_uuid)
            return False, f"Failed to delete from S3: {exc}", metadata

        try:
            async with self._db_pool.acquire() as connection:
                await connection.execute(
                    f"DELETE FROM {DATABASE_TABLE} WHERE file_id=$1",
                    file_uuid,
                )
        except Exception as exc:
            logger.exception("Deleted S3 objects but failed to remove DB record for %s", file_uuid)
            return False, f"S3 objects removed, but database deletion failed: {exc}", metadata

        logger.info("Deleted media entry %s from S3 and database.", file_uuid)
        return True, None, metadata

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
        if not media_attachments:
            return False
        if not self._s3_client or not self._s3_bucket:
            logger.error("S3 client is not configured; unable to handle uploads.")
            return False
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
            file_path: Optional[Path] = None
            thumbnail_path: Optional[Path] = None
            try:
                content_type = (attachment.content_type or "").lower()
                if content_type.startswith("image") or extension in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
                    file_path, thumbnail_path, file_format = await self._save_image(data, file_stem)
                elif content_type.startswith("video") or extension in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
                    file_path, thumbnail_path, file_format = await self._save_video(
                        data,
                        file_stem,
                        extension,
                        content_type,
                    )
                elif content_type.startswith("audio") or extension in {".mp3", ".wav", ".ogg", ".flac", ".m4a"}:
                    file_path, thumbnail_path, file_format = await self._save_audio(data, file_stem, extension)
                else:
                    raise ValueError("Unsupported content type")
                size_mb = file_path.stat().st_size / (1024 * 1024)
                s3_filename = f"{file_stem}{file_format}"
                file_key = s3_filename
                file_url = await self._upload_to_s3(
                    local_path=file_path,
                    object_key=file_key,
                    content_type=self._content_type_for_extension(file_format),
                )
                thumb_url = None
                if thumbnail_path:
                    thumb_key = f"thumbnails/{file_stem}.webp"
                    thumb_url = await self._upload_to_s3(
                        local_path=thumbnail_path,
                        object_key=thumb_key,
                        content_type="image/webp",
                    )
                await self._record_upload(
                    filename=s3_filename,
                    file_url=file_url,
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
                        f"{s3_filename} - {size_mb:.2f} MB",
                        file_url,
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
            finally:
                if file_path:
                    file_path.unlink(missing_ok=True)
                if thumbnail_path:
                    thumbnail_path.unlink(missing_ok=True)
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


@shadow_bot.tree.context_menu(name="Upload to S3")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.guild_only()
async def force_upload(interaction: discord.Interaction, message: discord.Message) -> None:
    logger.info(
        f"Upload to S3 triggered by {interaction.user} in {message.channel} ({message.jump_url})"
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
        await interaction.followup.send("Media uploaded to S3.", ephemeral=True)
    else:
        await interaction.followup.send("Failed to save any attachments.", ephemeral=True)


@shadow_bot.tree.command(name="delete-upload", description="Delete an uploaded media item from S3 by file id.")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.guild_only()
@app_commands.describe(file_id="UUID for the uploaded media entry")
async def delete_upload(interaction: discord.Interaction, file_id: str) -> None:
    logger.info(
        f"Delete upload triggered by {interaction.user} in {interaction.channel} for file_id {file_id}"
    )
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("You do not have permission to use this.", ephemeral=True)
        return
    cog = interaction.client.get_cog("ImageUpvote")
    if not cog:
        await interaction.response.send_message("Image upvote system is not loaded.", ephemeral=True)
        return
    admin_log_cog = interaction.client.get_cog("AdminLog")
    await interaction.response.defer(ephemeral=True)
    success, error_message, metadata = await cog.delete_media_entry(file_id)
    if success:
        await interaction.followup.send("Media entry deleted from S3 and database.", ephemeral=True)
        if admin_log_cog and interaction.guild:
            info = metadata or {}
            event_lines = [
                f"File ID: {info.get('file_id', file_id)}",
                f"Filename: {info.get('filename', 'Unknown')} ({info.get('file_format', 'n/a')})",
                f"Creator: {info.get('creator_name', 'Unknown')}",
                f"Uploaded by: {info.get('uploaded_by', 'Unknown')}",
            ]
            if info.get("file_url"):
                event_lines.append(f"File URL: {info['file_url']}")
            if info.get("thumbnail_url"):
                event_lines.append(f"Thumbnail URL: {info['thumbnail_url']}")
            if info.get("date_of_upload"):
                event_lines.append(f"Uploaded at: {info['date_of_upload']}")
            event_lines.append(f"Deleted by: {interaction.user.mention}")
            await admin_log_cog.log_event(
                interaction.guild.id,
                priority="warning",
                event_name="Media upload deleted",
                event_status="\n".join(event_lines),
            )
    else:
        failure_message = error_message or "Failed to delete media entry."
        await interaction.followup.send(failure_message, ephemeral=True)
        if admin_log_cog and interaction.guild:
            event_lines = [
                f"File ID: {file_id}",
                f"Requested by: {interaction.user.mention}",
                f"Reason: {failure_message}",
            ]
            if metadata and metadata.get("file_url"):
                event_lines.append(f"File URL: {metadata['file_url']}")
            await admin_log_cog.log_event(
                interaction.guild.id,
                priority="error",
                event_name="Media deletion failed",
                event_status="\n".join(event_lines),
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ImageUpvote(bot))
