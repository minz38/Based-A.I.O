import os
import json
import discord
from discord.ext import commands
from logger import LoggerManager
from datetime import datetime
from typing import Dict, Any


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


# If the bot joins a guild while running, it will call this function and creates a config file for it
@bot.event
async def on_guild_join(guild) -> None:
    logger.info(f"New guild joined: {guild.name} ({guild.id})")
    await create_guild_config()
