# Logger class definition
import sys

from loguru import logger


class Logger:
    @staticmethod
    def setup(config):
        logger.remove()  # Clear existing handlers

        # Setup file handler if filename is provided in the config
        if hasattr(config, "filename") and config.filename:
            logger.add(
                config.filename,
                rotation=config.max_size if hasattr(config, "max_size") else "50 MB",
                retention=config.max_age if hasattr(config, "max_age") else "30 days",
                level="DEBUG" if hasattr(config, "debug") and config.debug else "INFO",
                format="[{time:YYYY-MM-DD HH:mm:ss} {level:<8} | {file}:{module}.{function}:{line}]  {message}",
                compression=(
                    "zip" if hasattr(config, "compress") and config.compress else None
                ),
                mode="a",
            )
            logger.add(
                sys.stdout,
                level="DEBUG" if hasattr(config, "debug") and config.debug else "INFO",
            )

    @staticmethod
    def get_logger():
        return logger
