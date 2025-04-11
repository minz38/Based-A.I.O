from os import getenv
from pathlib import Path
from json import load, dump
from dep.logger import LoggerManager

logger = LoggerManager(name="Config Handler", level="INFO", log_name="bot").get_logger()

# Optional .env variables
logger.debug(msg="Loading environment variables...")
DATA_PATH: Path = Path(getenv("DATA_PATH", "./data"))
CONFIG_PATH: Path = DATA_PATH / getenv("CONFIG_FOLDER_PATH", "config")
GUILD_CONFIG: Path = CONFIG_PATH / getenv("GUILD_CONFIG_FOLDER_NAME", "guilds")
BOT_CONFIG: Path = CONFIG_PATH / getenv("BOT_CONFIG_FOLDER_NAME", "bot")

BOT_TOKEN: str | None = getenv("BOT_TOKEN", None)
BOT_PREFIX: str | None = getenv("BOT_PREFIX", None)
BOT_ADMIN_ID: str | None = getenv("BOT_ADMIN_ID", None)

# Create the folder structure
logger.debug("Checking config folder existence...")
BOT_CONFIG.mkdir(parents=True, exist_ok=True)
GUILD_CONFIG.mkdir(parents=True, exist_ok=True)


class GuildConfigHandler:
    def __init__(self, guild_id: int):
        self.guild_id: int = guild_id
        self.config_path: Path = GUILD_CONFIG / f"{self.guild_id}.json"
        self._config: dict[str, any] | None = None

    def get_config(self) -> dict[str, any]:
        if not self.config_path.exists():
            logger.warning(f"No config found for guild {self.guild_id}, creating new empty one.")
            self._config = {}
            self.save_new_config(self._config)
        else:
            with open(self.config_path, "r") as f:
                self._config = load(f)
        return self._config

    def save_new_config(self, config_data: dict[str, any]) -> None:
        logger.debug(f"Saving full config for Guild {self.guild_id}")
        with open(self.config_path, "w") as f:
            dump(config_data, f, indent=4)
        self._config = config_data

    def update_config(self, key: str, value: any) -> None:
        config = self.get_config()
        config[key] = value
        self.save_new_config(config)
        logger.info(f"Updated '{key}' in config for Guild {self.guild_id}")

    def remove_key(self, key: str) -> bool:
        config = self.get_config()
        if key in config:
            del config[key]
            self.save_new_config(config)
            logger.info(f"Removed '{key}' from config for Guild {self.guild_id}")
            return True
        else:
            logger.warning(f"Key '{key}' not found in config for Guild {self.guild_id}")
            return False

    def get_value(self, key: str) -> any:
        config = self.get_config()
        return config.get(key, None)

    def create_if_missing(self) -> None:
        if not self.config_path.exists():
            self.save_new_config({})
            logger.info(f"Created new empty config file for Guild {self.guild_id}")


class BotConfigHandler:
    def __init__(self, config_path: Path = BOT_CONFIG / "bot_config.json"):
        self.config_path: Path = config_path
        self._config: dict[str, any] | None = None

    def get_config(self) -> dict[str, any]:
        if not self.config_path.exists():
            logger.warning("Bot config not found, creating new empty config.")
            self._config = {}
            self.save_config(self._config)
        else:
            with open(self.config_path, "r") as f:
                self._config = load(f)

        self.sync_with_env()  # <- Check .env vars and update if needed
        return self._config

    def save_config(self, config_data: dict[str, any]) -> None:
        logger.debug("Saving bot configuration...")
        with open(self.config_path, "w") as f:
            dump(config_data, f, indent=4)
        self._config = config_data

    def update_config(self, key: str, value: any) -> None:
        config = self.get_config()
        config[key] = value
        self.save_config(config)
        logger.info(f"Updated key '{key}' in bot config.")

    def remove_key(self, key: str) -> bool:
        config = self.get_config()
        if key in config:
            del config[key]
            self.save_config(config)
            logger.info(f"Removed key '{key}' from bot config.")
            return True
        logger.warning(f"Key '{key}' not found in bot config.")
        return False

    def get_value(self, key: str) -> any:
        config = self.get_config()
        return config.get(key)

    def create_if_missing(self) -> None:
        if not self.config_path.exists():
            logger.info("Bot config missing. Creating a new one.")
            self.save_config({})

    def check_extensions(self) -> dict[str, any]:
        config = self.get_config()
        config.setdefault("active_extensions", {})

        ext_dir = Path("cog")
        if not ext_dir.exists():
            logger.warning("Creating 'cog' directory.")
            ext_dir.mkdir(parents=True)
            (ext_dir / "__init__.py").touch()

        for file in ext_dir.glob("*.py"):
            if file.name != "__init__.py":
                ext_name = file.stem
                config["active_extensions"].setdefault(ext_name, True)

        current_files = {f.stem for f in ext_dir.glob("*.py")}
        to_remove = [ext for ext in config["active_extensions"] if ext not in current_files]
        for ext in to_remove:
            del config["active_extensions"][ext]
            logger.info(f"Removed inactive extension: {ext}")

        self.save_config(config)
        return config

    def sync_with_env(self) -> None:
        """Update bot config using environment variables if provided."""
        updated = False
        config = self._config or {}

        token_env = getenv("BOT_TOKEN")
        prefix_env = getenv("BOT_PREFIX")
        admin_id_env = getenv("BOT_ADMIN_ID")

        if token_env and config.get("bot_token") != token_env:
            logger.info("Updating bot token from environment variable.")
            config["bot_token"] = token_env
            updated = True

        if prefix_env and config.get("prefix") != prefix_env:
            logger.info("Updating bot prefix from environment variable.")
            config["prefix"] = prefix_env
            updated = True

        if admin_id_env:
            try:
                admin_id_parsed = int(admin_id_env)
                if config.get("admin_user_id") != admin_id_parsed:
                    logger.info("Updating admin user ID from environment variable.")
                    config["admin_user_id"] = admin_id_parsed
                    updated = True
            except ValueError:
                logger.warning("Invalid BOT_ADMIN_ID in environment; must be an integer.")

        if updated:
            self.save_config(config)

    @staticmethod
    def create_interactively() -> None:
        logger.info("Creating a new Bot configuration...")
        print(f" ")
        bot_token = input("Enter your Discord Bot Token: ").strip()
        while not bot_token:
            bot_token = input("Bot Token cannot be empty. Try again: ").strip()

        prefix = input("Enter your Bot Prefix: ").strip()
        while not prefix:
            prefix = input("Prefix cannot be empty. Try again: ").strip()

        admin_user_id = input("Enter Admin User ID (optional): ").strip()
        admin_user_id = int(admin_user_id) if admin_user_id else ""

        new_config = {
            "bot_token": bot_token,
            "prefix": prefix,
            "admin_user_id": admin_user_id,
            "active_extensions": {}
        }

        print("\nPreview:")
        for k, v in new_config.items():
            print(f"  {k}: {v}")

        confirm = input("Save this config? (yes/no): ").strip().lower()
        if confirm in ("yes", "y"):
            handler = BotConfigHandler()
            handler.save_config(new_config)
            logger.info("Bot configuration saved successfully.")
        else:
            logger.warning("Bot configuration not saved.")
            exit()
