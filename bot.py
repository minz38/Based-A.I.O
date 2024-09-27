import os
import json
import discord
from discord.ext import commands
from logger import LoggerManager
from datetime import datetime


# initialize logger
logger = LoggerManager(name="Bot", level="INFO", log_file="logs/bot.log").get_logger()

# load the bot configuration
with open("configs/bot_config.json", "r") as file:
    bot_config = json.load(file)
    logger.debug(f"Loaded bot configuration: {bot_config}")

# Load the bot Configuration
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=bot_config["prefix"], intents=intents)


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    logger.info(f"Bot is connected to {len(bot.guilds)} guilds")
    for guild in bot.guilds:
        logger.debug(f'Bot Logged in as: {bot.user.name} in {guild.name} (id: {guild.id})')
    await create_guild_config()
    await load_extensions()
    for guild_id in await get_guilds_to_sync_commands():
        await bot.tree.sync(guild=discord.Object(id=guild_id))
        logger.info(f"Synced bot.tree for guild: {guild_id}")


# Create a Config file for each guild the bot is in
async def create_guild_config():
    # Create the guilds directory if it doesn't exist already
    if not os.path.exists(f"configs/guilds"):
        logger.warning("Guilds directory not found. Creating a new folder...")
        os.makedirs(f"configs/guilds")
        logger.debug(f"Created guilds directory.")

    for guild in bot.guilds:
        guild_config = None
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
                "active_extensions": [],
                "sync_commands": True
            }

        # Save the guild configuration (whether new or loaded)
        with open(f"configs/guilds/{guild.id}.json", "w") as config_file:
            json.dump(guild_config, config_file, indent=4)
            logger.debug(f"Config for guild: {guild.name} ({guild.id}) saved.")


async def load_extensions():
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


# async def sync_active_guild_commands():
#     for guild_file in os.listdir("configs/guilds"):
#         if guild_file.endswith(".json"):
#             guild_id = int(guild_file[:-5])  # Extract the guild ID from the filename (removing ".json")
#
#             # Load the guild config
#             with open(f"configs/guilds/{guild_file}", "r") as file:
#                 guild_config = json.load(file)
#
#             # Check if sync_commands is True for this guild
#             if guild_config.get("sync_commands", False):
#                 try:
#                     # Sync the application commands for this guild
#                     logger.info(f"Syncing commands for guild: {guild_id}")
#                     await bot.tree.sync(guild=discord.Object(id=guild_id))
#                     logger.info(f"Commands synced for guild: {guild_id}")
#                 except Exception as e:
#                     logger.error(f"Failed to sync commands for guild {guild_id}: {e}")


# return a list of guilds to sync commands with
async def get_guilds_to_sync_commands():
    guilds_to_sync = []
    for guild_file in os.listdir("configs/guilds"):
        if guild_file.endswith(".json"):
            guild_id = int(guild_file[:-5])  # Extract the guild ID from the filename (removing ".json")

            # Load the guild config
            with open(f"configs/guilds/{guild_file}", "r") as file:
                guild_config = json.load(file)

            # Check if sync_commands is True for this guild
            if guild_config.get("sync_commands", False):
                guilds_to_sync.append(guild_id)

    return guilds_to_sync


# If the bot joins a guild while running, it will call this function and creates a config file for it
@bot.event
async def on_guild_join(guild):
    logger.info(f"New guild joined: {guild.name} ({guild.id})")
    await create_guild_config()
