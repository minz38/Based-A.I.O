from asyncio import run as asyncio_run
from os import getenv
from typing import Any
from dep.config_handler import BotConfigHandler
from dep.logger import LoggerManager

# Set up logger
log = LoggerManager(name="Main", level="INFO", log_name="bot").get_logger()


def load_or_create_bot_config() -> dict[str, Any]:
    handler = BotConfigHandler()

    if not handler.config_path.exists():
        if getenv("BOT_TOKEN") and getenv("BOT_PREFIX"):
            log.info("Creating bot config from environment variables...")
            handler = BotConfigHandler()
            handler.sync_with_env()
        else:
            log.warning("No bot config found and required env vars not set. Entering interactive setup.")
            BotConfigHandler.create_interactively()

    try:
        updated_config = handler.check_extensions()
        return updated_config
    except Exception as e:
        log.error(f"Error while loading/updating bot configuration: {e}")
        exit()


async def run_bot(token: str):
    # Optional: add async startup logic here
    # from bot import start_api
    # await asyncio.gather(start_api(), bot.start(token))

    from src.bot import bot
    try:
        await bot.start(token)
    except Exception as e:
        log.error(f"Error running the bot: {e}")


if __name__ == "__main__":
    bot_config = load_or_create_bot_config()

    bot_token = bot_config.get("bot_token")
    if not bot_token:
        log.error("Bot token is missing in configuration. Exiting.")
        exit()

    try:
        asyncio_run(run_bot(bot_token))
    except KeyboardInterrupt:
        log.info("Bot shutdown via KeyboardInterrupt.")
