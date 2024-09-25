import os
import json
import discord
from discord.ext import commands
from logger import setup_logging
from datetime import datetime

# initialize logger
logger = setup_logging(level="INFO", log_file="logs/bot_core.log")

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
    for guild in bot.guilds:
        logger.info(f'Bot Logged in as: {bot.user.name} in {guild.name} (id: {guild.id})')


# Create a Config file for each guild the bot is in
async def create_guild_config():
    # Create the guilds directory if it doesn't exist already
    if not os.path.exists(f"configs/guilds"):
        logger.warning("Guilds directory not found. Creating a new folder...")
        os.makedirs(f"configs/guilds")
        logger.debug(f"Created guilds directory.")

    for guild in bot.guilds:
        guild_config = None
        if not os.path.exists(f"configs/guilds/{guild.id}.json"):
            logger.info(f"Creating config for guild: {guild.name} ({guild.id})")
            guild_config = {
                "day_added": datetime.now().strftime("%d-%m-%Y"),
                "active_extensions": []
            }

        with open(f"configs/guilds/{guild.id}.json", "w") as x:
            json.dump(guild_config, x, indent=4)
            logger.debug(f"Config for guild: {guild.name} ({guild.id}) saved.")


async def load_extensions():
    logger.info("Loading extensions...")
    pass


# If the bot joins a guild while running, it will call this function and creates a config file for it
@bot.event
async def on_guild_join(guild):
    logger.info(f"New guild joined: {guild.name} ({guild.id})")
    await create_guild_config()
