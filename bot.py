import re
import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from logger import LoggerManager
from datetime import datetime
from typing import Dict, Any
from dependencies.youtube_handler import download_music, delete_temp_files

# initialize logger
logger = LoggerManager(name="Bot", level="INFO", log_file="logs/bot.log").get_logger()

# load the bot configuration
with open("configs/bot_config.json", "r") as file:
    bot_config: Dict[str, Any] = json.load(file)
    logger.debug(f"Loaded bot configuration: {bot_config}")

# Load the bot Configuration
intents: discord.Intents = discord.Intents.all()
bot: commands.Bot = commands.Bot(command_prefix=bot_config["prefix"],
                                 intents=intents,
                                 help_command=None)


@bot.event
async def on_ready() -> None:
    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    logger.info(f"Bot is connected to {len(bot.guilds)} guilds")
    for guild in bot.guilds:
        logger.debug(f'Bot Logged in as: {bot.user.name} in {guild.name} (id: {guild.id})')

    await create_guild_config()
    await load_extensions()
    try:
        await bot.tree.sync()
        logger.info("Synced bot.tree for all guilds.")
    except Exception as err:
        logger.error(f"Error syncing bot.tree: {err}")


# Create a Config file for each guild the bot is in
async def create_guild_config() -> None:
    # Create the guilds directory if it doesn't exist already
    if not os.path.exists(f"configs/guilds"):
        logger.warning("Guilds directory not found. Creating a new folder...")
        os.makedirs(f"configs/guilds")
        logger.debug(f"Created guilds directory.")

    for guild in bot.guilds:
        # If the guild config exists, load it
        if os.path.exists(f"configs/guilds/{guild.id}.json"):
            logger.info(f"Loading existing config for guild: {guild.name} ({guild.id})")
            with open(f"configs/guilds/{guild.id}.json", "r") as config_file:
                guild_config = json.load(config_file)
        else:
            # Create new config if it doesn't exist
            logger.info(f"Creating new config for guild: {guild.name} ({guild.id})")
            guild_config = {
                "day_added": datetime.now().strftime("%d-%m-%Y"),
                "active_extensions": []
            }

        # Save the guild configuration (whether new or loaded)
        with open(f"configs/guilds/{guild.id}.json", "w") as config_file:
            json.dump(guild_config, config_file, indent=4)
            logger.debug(f"Config for guild: {guild.name} ({guild.id}) saved.")


async def load_extensions() -> None:
    logger.info("Loading extensions...")
    # load extension if it is set to True inf the bot config.json
    # for extension in bot_config["active_extensions"] where value is True load extension
    for extension in bot_config["active_extensions"]:
        if bot_config["active_extensions"][extension]:
            try:
                await bot.load_extension(f'extensions.{extension}')
                logger.info(f"Loaded {extension}")
            except Exception as e:
                logger.error(f"Could not load {extension}: {e}")
    logger.info("Finished loading extensions.")


# YouTube downloader in Context Menu
# Dependencies folder: ffmpeg.exe, ffprobe.exe, youtube_handler.py
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.context_menu(name="Youtube Music Download")
async def music_download(interaction: discord.Interaction, message: discord.Message):
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


@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.context_menu(name="Unarchive Channel")
async def unarchive_channel(interaction: discord.Interaction, message: discord.Message):
    # Defer the response
    await interaction.response.defer(ephemeral=True)  # noqa

    # Ensure the message is from the bot and contains the archive data
    if message.author != bot.user:
        await interaction.followup.send("This message was not sent by the bot.", ephemeral=True)
        return

    # Ensure the message is in a text channel
    channel = message.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.followup.send("This command can only be used in a text channel.", ephemeral=True)
        return

    # Parse the archive data from the message content
    try:
        content = message.content
        # Extract the JSON data from the code block
        pattern = r'```json\s*(\{.*?\})\s*```'
        matches = re.findall(pattern, content, re.DOTALL)
        if not matches:
            raise ValueError("Archive data not found in message.")

        json_data = matches[-1]
        archive_data = json.loads(json_data)
    except Exception as _:
        await interaction.followup.send("Failed to parse archive data from the message.", ephemeral=True)
        return

    # Restore the previous permissions
    previous_permissions = archive_data.get('previous_permissions', [])
    for perm_data in previous_permissions:
        target_id = perm_data.get('id')
        target_type = perm_data.get('type')
        allow_value = perm_data.get('allow')
        deny_value = perm_data.get('deny')

        if target_type == 'role':
            target = interaction.guild.get_role(target_id)
        elif target_type == 'member':
            target = interaction.guild.get_member(target_id)
        else:
            target = None

        if target is None:
            # Skip if target no longer exists
            continue

        # Create PermissionOverwrite from allow and deny values
        overwrite = discord.PermissionOverwrite.from_pair(
            discord.Permissions(allow_value),
            discord.Permissions(deny_value)
        )

        await channel.set_permissions(target, overwrite=overwrite)

    # Remove per-user permissions set during archiving
    for member in channel.overwrites:
        if isinstance(member, discord.Member):
            await channel.set_permissions(member, overwrite=None)

    # Move the channel back to its previous category
    previous_category_data = archive_data.get('previous_category', {})
    previous_category_id = previous_category_data.get('id')
    if previous_category_id:
        previous_category = interaction.guild.get_channel(previous_category_id)
        if previous_category and isinstance(previous_category, discord.CategoryChannel):
            await channel.edit(category=previous_category)
        else:
            await channel.edit(category=None)  # Move to no category
    else:
        await channel.edit(category=None)  # Move to no category

    await interaction.followup.send("Channel has been unarchived.", ephemeral=True)


# If the bot joins a guild while running, it will call this function and creates a config file for it
@bot.event
async def on_guild_join(guild) -> None:
    logger.info(f"New guild joined: {guild.name} ({guild.id})")
    await create_guild_config()
