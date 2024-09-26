# Main execution file to start the Bot
import json
import os
from colorama import Fore, init
from logger import LoggerManager


# Initialize colorama for terminal colors
init(autoreset=True)

# make sure the log directory exists
if not os.path.exists("logs"):
    os.makedirs("logs")

logger = LoggerManager(name="Main", level="INFO", log_file="logs/main.log").get_logger()
# logger = setup_logging(name="Main", level="WARNING", log_file="logs/main.log")


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
        "admin_user_id": admin_user_id,
        "active_extensions": {}
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
                bot_config_data = json.load(bot_config_file)
                logger.info(f"Bot configuration loaded successfully.")
                return bot_config_data

        except Exception as e:
            logger.error(f"Error loading bot configuration: {e}")
            exit()


def extension_check(bot_config_file):
    # check if the extensions directory exists, if not create it.
    if not os.path.exists("extensions"):
        logger.warning("Extensions directory not found. Creating a new one...")
        os.makedirs("extensions")
        open("extensions/__init__.py", "a").close()

    for filename in os.listdir("extensions"):
        if filename.endswith(".py") and filename != "__init__.py":
            extension_name = filename.split(".")[0]
            if extension_name not in bot_config_file["active_extensions"]:
                bot_config_file["active_extensions"][extension_name] = True

    for extension_name in list(bot_config_file["active_extensions"].keys()):
        if f"{extension_name}.py" not in os.listdir("extensions"):
            del bot_config_file["active_extensions"][extension_name]

    # Save the updated bot configuration.
    with open("configs/bot_config.json", "w") as file:
        json.dump(bot_config_file, file, indent=4)
        logger.info(f"Bot configuration updated successfully.")

    return bot_config_file  # return the updated bot configuration for the bot to use.


if __name__ == "__main__":
    config = bot_config_check()  # load the bot configuration
    config = extension_check(config)  # check and add new extension and update the bot config.
    bot_config = config  # Use this across other COG's to access the bot's configuration.
    token = bot_config["bot_token"]
    from bot import bot
    try:
        bot.run(token)
        logger.info(f"Bot started successfully.")
    except Exception as e:
        logger.error(f"Error when running the bot: {e}")
