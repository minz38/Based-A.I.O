import os
import json
import logging
import discord
from discord.ext import commands
from logger import setup_logging

# initialize logger
logger = setup_logging(name="Bot Core", level=logging.INFO, log_file="logs/bot_core.log")

# load the bot configuration
with open("configs/bot_config.json", "r") as file:
    bot_config = json.load(file)
    logger.DEBUG(f"Loaded bot configuration: {bot_config}")

# Load the bot Configuration
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=bot_config["prefix"], intents=intents)


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guilds")