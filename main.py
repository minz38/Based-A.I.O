import asyncio
from dep.logger import LoggerManager
from dep.config_handler import BotConfigHandler


# Set up logger
logger = LoggerManager(name="Main", level="INFO", log_name="bot").get_logger()

def load_or_create_bot_config() -> dict[str, any]:
    handler = BotConfigHandler()

    if not handler.config_path.exists():
        logger.warning("Bot configuration file not found.")
        BotConfigHandler.create_interactively()

    try:
        updated_config = handler.check_extensions()
        return updated_config
    except Exception as e:
        logger.error(f"Error while loading/updating bot configuration: {e}")
        exit()

async def run_bot(token: str):
    # Optional: add async startup logic here
    # from bot import start_api
    # await asyncio.gather(start_api(), bot.start(token))

    from src.bot import bot
    try:
        await bot.start(token)
    except Exception as e:
        logger.error(f"Error running the bot: {e}")

if __name__ == "__main__":
    bot_config = load_or_create_bot_config()

    bot_token = bot_config.get("bot_token")
    if not bot_token:
        logger.error("Bot token is missing in configuration. Exiting.")
        exit()

    try:
        asyncio.run(run_bot(bot_token))
    except KeyboardInterrupt:
        logger.info("Bot shutdown via KeyboardInterrupt.")
