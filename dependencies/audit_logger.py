import os
import discord
from typing import Literal
from logger import LoggerManager
from bot import bot as shadow_bot

logger = LoggerManager(name="Audit / Mod", level="INFO", log_file="logs/audit.log").get_logger()

# load environment variables
AUDIT_LOG_CHANNEL_ID: int | None = int(os.getenv("AUDIT_LOG_CHANNEL_ID"))
MOD_LOG_CHANNEL_ID: int | None = int(os.getenv("MOD_LOG_CHANNEL_ID"))


async def verify_functionality(interaction: discord.Interaction) -> bool:
    # Check if the env variables are set
    if not AUDIT_LOG_CHANNEL_ID or not MOD_LOG_CHANNEL_ID:
        logger.error("Missing AUDIT_LOG_CHANNEL_ID or MOD_LOG_CHANNEL_ID environment variables.")
        return False

    # check if the channels exist in the guild
    guild = interaction.guild
    if not guild:
        logger.error("Interaction is not in a guild.")
        return False

    try:
        audit_channel, mod_channel = None, None
        audit_channel = guild.get_channel(AUDIT_LOG_CHANNEL_ID)
        mod_channel = guild.get_channel(MOD_LOG_CHANNEL_ID)

    except discord.NotFound:
        logger.error(f"Either AUDIT_LOG_CHANNEL_ID or MOD_LOG_CHANNEL_ID points to non-existent channels.")
        return False

    if not audit_channel or not mod_channel:
        logger.error("Either AUDIT_LOG_CHANNEL_ID or MOD_LOG_CHANNEL_ID points to non-existent channels.")
        return False

    return True


# helper function to send log messages to respective channels
async def log_interaction(
        interaction: discord.Interaction,
        log_type: Literal["audit", "mod"],
        reason: str | int | None) -> bool:

    """ Sends a log message to the specified audit or moderation log channel. """

    if not await verify_functionality(interaction):
        return False

    match log_type:
        case "audit":
            channel_id = AUDIT_LOG_CHANNEL_ID
            logger.debug(f"Sending audit log message to channel: {channel_id}")
        case "mod":
            channel_id = MOD_LOG_CHANNEL_ID
            logger.debug(f"Sending moderation log message to channel: {channel_id}")
        case _:
            logger.error("Invalid log type specified.")
            return False

    # Send the log message to the respective channel
    # create a embed for the log message providing necessary information about which user,
    # executed which command, and why

    guild: discord.Guild = interaction.guild
    channel: discord.TextChannel = guild.get_channel(channel_id)

    embed = discord.Embed(
        title=f"{interaction.command.name}",
        description=f"User: {interaction.user.mention}\nCommand: {interaction.command.name}\nReason: {reason}",
        color=0x7F00FF
    )

    try:
        await channel.send(embed=embed)
        return True

    except discord.Forbidden:
        logger.error(f"Bot lacks permissions to send messages in channel: {channel_id}")
        return False

