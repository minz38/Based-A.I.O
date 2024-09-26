import logging
import os


class LoggerManager:
    _loggers = {}  # Dictionary to store loggers by name

    def __init__(self, name=None, level="INFO", log_file="logs/main.log"):
        """
        Initializes a LoggerManager instance, creating or retrieving a logger.

        Parameters:
        name (str): The name of the logger (optional).
        level (str): The logging level as a string (e.g., "INFO", "DEBUG").
        log_file (str): The path to the log file.
        """

        # Ensure the logs directory exists
        if not os.path.exists("logs"):
            os.makedirs("logs")

        # Create or retrieve the logger
        self.logger = self._get_logger(name, level, log_file)

    def _get_logger(self, name, level, log_file):
        """
        Retrieves or creates a logger with the given name.

        Parameters:
        name (str): The name of the logger.
        level (str): The logging level.
        log_file (str): The path to the log file.

        Returns:
        logger (logging.Logger): Configured logger instance.
        """

        # If the logger already exists in the _loggers dictionary, return it
        if name in self._loggers:
            return self._loggers[name]

        # Dictionary to map string levels to logging module levels
        level_dict = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }

        # Convert string level to the corresponding logging level
        log_level = level_dict.get(level.upper(), logging.INFO)  # Default to INFO if invalid level is passed

        # Create or get a logger with a specific name if provided
        logger = logging.getLogger(name)
        logger.setLevel(log_level)  # Set the logging level

        # Define the date format
        date_format = "%d/%m/%Y %H:%M:%S"

        # Check if the logger already has handlers to avoid duplication
        if not logger.hasHandlers():
            # File handler to log into a file
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(log_level)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt=date_format
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

            # Console handler to log to the console (stdout)
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt=date_format
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

        # Store the logger in the _loggers dictionary
        self._loggers[name] = logger

        return logger

    def get_logger(self):
        """
        Returns the logger instance for this LoggerManager.

        Returns:
        logger (logging.Logger): The logger instance.
        """
        return self.logger
