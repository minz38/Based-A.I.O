import json
import discord
from discord import app_commands
from logger import LoggerManager

logger = LoggerManager(name="Bot", level="INFO", log_file="logs/bot.log").get_logger()


# load the bot configuration
with open("configs/bot_config.json", "r") as file:
    bot_config = json.load(file)
    logger.debug(f"Loaded bot configuration: {bot_config}")


def is_authorized(roles=None, permissions=None, bot_creator=True):
    """
    Custom decorator to check if a user has specific roles, permissions, or is the bot creator to use a command.

    Parameters:
    roles (list): List of role names that are allowed to use the command.
    permissions (dict): Dictionary of permission names and their required values (e.g., {"administrator": True}).
    bot_creator (bool): If True, allows the bot creator to use the command.

    Returns:
    A decorator function that performs the check.
    """

    def predicate(interaction: discord.Interaction) -> bool:
        # Check if the user is the bot creator
        if bot_creator and interaction.user.id == int(bot_config.get("admin_user_id", 0)):
            logger.debug(f"Bot creator {interaction.user.name} is using the command.")
            return True

        # Check for specific roles
        if roles:
            user_roles = [role.name for role in interaction.user.roles]
            if any(role in user_roles for role in roles):
                logger.debug(f"{interaction.user.name} has roles {roles} and is allowed to use the command.")
                return True

        # Check for specific permissions
        if permissions:
            for perm, value in permissions.items():
                if getattr(interaction.user.guild_permissions, perm, False) == value:
                    logger.debug(f"{interaction.user.name} has permission {perm} and is allowed to use the command.")
                    return True

        # If none of the checks pass, return False
        return False

    return app_commands.check(predicate)
