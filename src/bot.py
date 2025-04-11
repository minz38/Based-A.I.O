# import os
# import json
import discord
from pathlib import Path
from discord.ext import commands
from dep.logger import LoggerManager
from dep.config_handler import BotConfigHandler, GuildConfigHandler
from datetime import datetime
from typing import Dict, Any

# initialize logger
logger = LoggerManager(name="Bot", level="INFO", log_name="bot").get_logger()

# load the bot configuration
bot_config: dict[str, Any] = BotConfigHandler().get_config()
logger.debug(f"Loaded bot configuration: {bot_config}")

# Load the bot Configuration
intents: discord.Intents = discord.Intents.all()

bot: commands.Bot = commands.Bot(
    command_prefix=bot_config["prefix"], intents=intents, help_command=None)


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    logger.info(f"Bot is connected to {len(bot.guilds)} guilds")

    for guild in bot.guilds:
        logger.debug(f'Bot active in guild: {guild.name} (ID: {guild.id})')

    await create_guild_config()
    await load_extensions()

    try:
        await bot.tree.sync()
        logger.info("Synced bot.tree commands successfully.")
    except Exception as err:
        logger.error(f"Error syncing bot.tree: {err}")


# Create a Config file for each guild the bot is in
async def create_guild_config():
    for guild in bot.guilds:
        handler = GuildConfigHandler(guild_id=guild.id)

        if handler.config_path.exists():
            logger.info(f"Loading existing config for guild: {guild.name} ({guild.id})")
            config = handler.get_config()
        else:
            logger.info(f"Creating new config for guild: {guild.name} ({guild.id})")
            config = {
                "day_added": datetime.now().strftime("%d-%m-%Y"),
                "active_extensions": []
            }

        handler.save_new_config(config)
        logger.debug(f"Config for guild '{guild.name}' saved.")


async def load_extensions():
    logger.info("Loading extensions...")
    for extension, enabled in bot_config.get("active_extensions", {}).items():
        if enabled:
            try:
                await bot.load_extension(f'cog.{extension}')
                logger.info(f"Loaded extension: {extension}")
            except Exception as e:
                if extension.startswith("CM"):
                    logger.warning(f"Extension {extension} has been touched: {e}")
                else:
                    logger.error(f"Failed to load extension '{extension}': {e}")

    logger.info("Finished loading extensions.")


# If the bot joins a guild while running, it will call this function and creates a config file for it
@bot.event
async def on_guild_join(guild):
    logger.info(f"Joined new guild: {guild.name} ({guild.id})")
    handler = GuildConfigHandler(guild_id=guild.id)
    if not handler.config_path.exists():
        config = {
            "day_added": datetime.now().strftime("%d-%m-%Y"),
            "active_extensions": []
        }
        handler.save_new_config(config)
        logger.info(f"Created config for new guild: {guild.name}")
