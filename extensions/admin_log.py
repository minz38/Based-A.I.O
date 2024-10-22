import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from logger import LoggerManager

logger = LoggerManager(name="Admin Log", level="INFO", log_file="logs/admin_log.log").get_logger()


class AdminLog(commands.Cog):
    def __init__(self, bot: commands.Bot, interaction: discord.Interaction = None) -> None:
        self.bot = bot

    async def log_interaction(self, interaction: discord.Interaction) -> None:
        # send a message into the admin-log channel specified in the bot config.json (configs/guilds/{guild_id}.json)
        pass

    async def get_admin_log_channel(self, guild_id: int) -> None | discord.TextChannel:
        with open(f"configs/guilds/{guild_id}.json", "r") as file:
            guild_config = json.load(file)

        if "admin_log_channel" in guild_config:
            log_channel: discord.TextChannel = self.bot.get_channel(int(guild_config["admin_log_channel"]))
            if log_channel is None:
                logger.error(f"Admin log channel not found for guild: {guild_id}")
                return None
            else:
                return log_channel
        else:
            logger.error(f"Admin log key is nor present in the guild config file")
            return None

    @app_commands.command(name="set_log_channel", description="Set the admin log channel for this Bot")
    async def setup_log_channel(self, interaction: discord.Interaction, log_channel: discord.TextChannel) -> None:
        pass
