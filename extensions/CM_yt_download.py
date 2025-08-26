import re
import discord
from discord import app_commands
from discord.ext import commands
from logger import LoggerManager
from dependencies.youtube_handler import download_music, delete_temp_files

logger = LoggerManager(name="YT-Downloader", level="INFO", log_file="logs/bot.log").get_logger()


# YouTube downloader in Context Menu
# Dependencies folder: ffmpeg.exe, ffprobe.exe, youtube_handler.py
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.context_menu(name="Youtube Music Download")
async def music_download(interaction: discord.Interaction, message: discord.Message):
    logger.info(f"Command: {interaction.command.name} used by {interaction.user.name}")
    message_content: str = str(message.clean_content)
    youtube_regex: str = (r'(https?://(?:www\.)?(?:youtube|youtu|youtube-nocookie)\.'
                          r'(?:com|be)/(?:watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11}))')

    # Find all matches
    matches: list[str] = re.findall(youtube_regex, message_content)

    if matches:
        found_links: list[str] = [match[0] for match in matches]
        await interaction.response.send_message("Found YouTube video links... downloading", ephemeral=True)  # noqa

        for link in found_links:
            file_path: str | bool = await download_music(link)

            if file_path:
                message_content: str = f"{interaction.user.mention}, your requested download was successful!"
                file_to_send: discord.File = discord.File(file_path)  # Wrap the file in discord.File
                await interaction.followup.send(content=message_content, file=file_to_send, ephemeral=True)
            else:
                await interaction.followup.send(content=f"Failed to download video from {link}", ephemeral=True)

        # cleanup the temp files folder
        await delete_temp_files()

    else:
        await interaction.response.send_message("No YouTube video link found.", ephemeral=True)  # noqa


async def setup(bot: commands.Bot) -> None:
    """Register the context menu with the provided bot."""
    bot.tree.add_command(music_download)
