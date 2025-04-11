import logging
from os import getenv
from pathlib import Path

from colorama import Fore, Back, Style, init

# Initialize colorama for automatic reset after each print statement
init(autoreset=True)

DATA_PATH: Path = Path(getenv("DATA_PATH", "./data"))
LOG_FOLDER_PATH: Path = DATA_PATH / getenv("LOG_FOLDER_PATH", "logs")

# Ensure the logs directory exists
Path.mkdir(LOG_FOLDER_PATH, parents=True, exist_ok=True)


class LoggerManager:
    _loggers = {}  # Shared logger registry

    def __init__(self, name: str = None, level: str = "INFO", log_name: str = "main") -> None:
        """
        Initialize the LoggerManager.

        Parameters:
        - name: Optional display name for the logger (used in log lines).
        - level: Logging level (DEBUG, INFO, WARNING, etc).
        - log_name: Base name for the log file (no .log extension).
        """
        log_filename = f"{log_name}.log"
        self.log_file: Path = LOG_FOLDER_PATH / log_filename

        logger_name = name or log_name
        self.logger = self._get_logger(logger_name, level, self.log_file)

    def _get_logger(self, name: str, level: str, log_file: Path) -> logging.Logger:
        if name in self._loggers:
            return self._loggers[name]

        level_dict = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        log_level = level_dict.get(level.upper(), logging.INFO)

        logger = logging.getLogger(name)
        logger.setLevel(log_level)

        if not logger.hasHandlers():
            # File Handler
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(log_level)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt="%d/%m/%Y %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

            # Console Handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_formatter = ColoredFormatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt="%d/%m/%Y %H:%M:%S"
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

        self._loggers[name] = logger
        return logger

    def get_logger(self) -> logging.Logger:
        return self.logger


class ColoredFormatter(logging.Formatter):
    def format(self, record) -> str:
        if record.levelno == logging.INFO:
            record.msg = Fore.LIGHTWHITE_EX + str(record.msg) + Style.RESET_ALL
        elif record.levelno == logging.WARNING:
            record.msg = Fore.YELLOW + str(record.msg) + Style.RESET_ALL
        elif record.levelno == logging.ERROR:
            record.msg = Fore.RED + str(record.msg) + Style.RESET_ALL
        elif record.levelno == logging.CRITICAL:
            record.msg = Fore.YELLOW + Back.RED + str(record.msg) + Style.RESET_ALL

        return super().format(record)
