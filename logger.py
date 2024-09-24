import logging
import os

# Ensure the logs directory exists
if not os.path.exists("logs"):
    os.makedirs("logs")


def setup_logging(name=None, level=logging.INFO, log_file="logs/main.log"):
    """
    Sets up logging with both file and console handlers.

    Parameters:
    name (str): The name of the logger (optional).
    level (int): The logging level (e.g., logging.INFO, logging.DEBUG).
    log_file (str): The path to the log file.

    Returns:
    logger (logging.Logger): Configured logger instance.
    """
    # Create or get a logger with a specific name if provided
    logger = logging.getLogger(name)
    logger.setLevel(level)  # Set the logging level

    # Define the date format
    date_format = "%d/%m/%Y %H:%M:%S"

    # Check if the logger already has handlers to avoid duplication
    if not logger.hasHandlers():
        # File handler to log into a file
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt=date_format
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console handler to log to the console (stdout)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt=date_format
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger