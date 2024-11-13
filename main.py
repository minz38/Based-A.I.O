# Main execution file to start the Bot
import os
import json
from typing import Dict, Any
from dotenv import load_dotenv
from logger import LoggerManager

load_dotenv()  # Load environment variables from .env file

# Ensure the logs directory exists
if not os.path.exists("logs"):
    os.makedirs("logs")

logger = LoggerManager(name="Main", level="INFO", log_file="logs/main.log").get_logger()


# Function to create a bot config file
def create_bot_config() -> None:
    """
    This function is responsible for creating a new bot configuration file.
    It prompts the user to input the bot token, prefix, and admin user ID.
    The function then saves the configuration to a JSON file.

    Parameters:
    None

    Returns:
    None

    Raises:
    None
    """
    logger.info("Creating a new Bot configuration...")
    bot_token: str | None = None
    while bot_token is None:
        bot_token = input(f"Enter your Discord Bot Token: ")
    prefix: str | None = None
    while prefix is None:
        prefix: str = input(f"Enter your Discord Bot Prefix: ")
    admin_user_id = input(f"Enter the Discord User ID of your admin (leave blank for none):")

    if admin_user_id:
        admin_user_id = int(admin_user_id)

    new_bot_config = {
        "bot_token": bot_token,
        "prefix": prefix,
        "admin_user_id": admin_user_id,
        "active_extensions": {}
    }

    confirm: str = input(f"Do you confirm the bot configuration above? (yes/no): ")

    if confirm.lower() in ("yes", "y"):
        with open("configs/bot_config.json", "w") as file:
            json.dump(new_bot_config, file, indent=4)
        logger.info(f"Bot configuration saved successfully.")
    else:
        logger.warning("Bot configuration not saved. Exiting.")
        exit()


def bot_config_check() -> Dict[str, Any]:
    """
    This function checks if the bot configuration file exists in the 'configs' directory.
    If the file does not exist, it creates a new one using the `create_bot_config` function.
    Then, it loads the bot configuration file and updates it with available extension files using the
    `extension_check` function.
    Finally, it returns the updated bot configuration.

    Parameters:
    None

    Returns:
    Dict[str, Any]: The updated bot configuration.

    Raises:
    None
    """
    # Ensure config directory exists
    if not os.path.exists("configs"):
        logger.warning("Config directory not found. Creating a new one...")
        os.makedirs("configs")

    # If config file doesn't exist, create one
    if not os.path.exists("configs/bot_config.json"):
        logger.warning("Bot configuration file not found. Creating a new one...")
        create_bot_config()

    # Load and return the bot configuration
    try:
        with open("configs/bot_config.json", "r") as bot_config_file:
            bot_config_data = json.load(bot_config_file)
            logger.info("Bot configuration loaded successfully.")

            # Check for extensions and update the configuration
            updated_config = extension_check(bot_config_data)
            return updated_config

    except Exception as err:
        logger.error(f"Error loading bot configuration: {err}")
        exit()


def extension_check(bot_config_file: Dict[str, Any]) -> Dict[str, Any]:
    """
    Checks for available extensions in the 'extensions' directory,
    updates the bot configuration with these extensions, and saves the updated configuration.
    It also ensures the existence of the 'extensions' and 'dependencies' directories.

    Parameters:
    bot_config_file (Dict[str, Any]): The current bot configuration file.

    Returns:
    Dict[str, Any]: The updated bot configuration file.
    """
    # Ensure the extensions directory exists
    if not os.path.exists("extensions"):
        logger.warning("Extensions directory not found. Creating a new one...")
        os.makedirs("extensions")
        open("extensions/__init__.py", "a").close()

    # Add missing extensions to active_extensions
    for filename in os.listdir("extensions"):
        if filename.endswith(".py") and filename != "__init__.py":
            extension_name = filename.split(".")[0]
            if extension_name not in bot_config_file["active_extensions"]:
                bot_config_file["active_extensions"][extension_name] = True

    # Ensure the dependencies directory exists
    if not os.path.exists("dependencies"):
        logger.warning("Dependencies directory not found. Creating a new one...")
        os.makedirs("dependencies")
        open("dependencies/__init__.py", "a").close()

    # Remove extensions no longer present in the directory
    active_extensions = list(bot_config_file["active_extensions"].keys())
    for extension_name in active_extensions:
        if f"{extension_name}.py" not in os.listdir("extensions"):
            del bot_config_file["active_extensions"][extension_name]

    # Save the updated bot configuration
    with open("configs/bot_config.json", "w") as file:
        json.dump(bot_config_file, file, indent=4)
        logger.info("Bot configuration updated successfully.")

    return bot_config_file


if __name__ == "__main__":
    # Load, check, and update bot configuration
    bot_config: Dict[str, Any] = bot_config_check()

    # Extract bot token and start the bot
    token = bot_config["bot_token"]
    from bot import bot

    try:
        bot.run(token)
        logger.info("Bot started successfully.")
    except Exception as e:
        logger.error(f"Error when running the bot: {e}")
