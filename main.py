# Main execution file to start the Bot
import json
import os
import logging
from bot import bot
from colorama import Fore, init
from logger import setup_logging

# Initialize colorama for terminal colors
init(autoreset=True)

# make sure the log directory exists
if not os.path.exists("logs"):
    os.makedirs("logs")

logger = setup_logging(name="Main", level=logging.WARNING)


# function to create a bot config file
def create_bot_config():
    logger.info("Creating a new Bot configuration...")
    # Ask the user to input the necessary information for the bot to run
    bot_token = input(f"{Fore.YELLOW}Enter your Discord Bot Token: {Fore.RESET}")
    prefix = input(f"{Fore.YELLOW}Enter your Discord Bot Prefix: {Fore.RESET}")
    admin_user_id = input(f"{Fore.YELLOW}Enter the Discord User ID of your admin (leave blank for none): {Fore.RESET}")

    new_bot_config = {
        "bot_token": bot_token,
        "prefix": prefix,
        "admin_user_id": admin_user_id
    }

    # Ask the user to confirm the bot configuration.
    confirm = input(f"{Fore.YELLOW}Do you confirm the bot configuration above? (yes/no): {Fore.RESET}")

    if confirm.lower() == "yes" or confirm.lower() == "y":
        with open("configs/bot_config.json", "w") as file:
            json.dump(new_bot_config, file, indent=4)
            logger.info(f"Bot configuration saved successfully.")
    else:
        logger.warning("Bot configuration not saved and the Program exits.")
        exit()


def bot_config_check():
    # Check if the config file exists
    if not os.path.exists("configs"):
        logger.warning("Config directory not found. Creating a new one...")
        os.makedirs("configs")

    if not os.path.exists("configs/bot_config.json"):
        logger.warning(f"Bot configuration file not found. Creating a new one...")
        create_bot_config()

    # load the bot configuration if the config file exists
    if os.path.exists("configs/bot_config.json"):

        try:
            with open("configs/bot_config.json", "r") as bot_config_file:
                bot_config = json.load(bot_config_file)
                logger.info(f"Bot configuration loaded successfully.")
                return bot_config

        except Exception as e:
            logger.error(f"Error loading bot configuration: {e}")
            exit()


if __name__ == "__main__":
    config = bot_config_check()
    bot.run(config["bot_token"])
