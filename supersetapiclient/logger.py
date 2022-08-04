
from logging.config import dictConfig
import logging


class LogConfig:
    """ Logging configuration to be set for the server

    Args:

        name (str): The name of your logger, typically the application or API
            that the logger is being used in
        log_level (str): Default log level of your logger, default value is 'DEBUG'
        log_fomat (str): The format of how logs are printed, default value is
            '%(levelprefix)s | %(asctime)s | %(message)s'

    Examples:

        >>> encoding_logger = LogConfig("lakehouse_api").logger

        >>> encoding_logger.info("This happened")
        >>> encoding_logger.error("Uh oh")

        >>> airflow_logger = LogConfig("airflow").logger

        >>> airflow_logger.info("And this happened in Airflow")
    """

    def __init__(
            self,
            name: str,
            log_level: str = "DEBUG",
            log_format: str = "%(funcName)s >> %(levelname)s | %(asctime)s | %(message)s"):
        self.name = name
        self.log_level = log_level
        self.log_format = log_format

    @property
    def config(self):
        """ Configurations property for logger

        Returns:
            dict: The logger configurations
        """
        return dict(
            LOGGER_NAME=self.name,
            LOG_FORMAT=self.log_format,
            LOG_LEVEL=self.log_level,
            version=1,
            disable_existing_loggers=False,
            formatters={
                "default": {
                    "format": self.log_format,
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            handlers={
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                },
            },
            loggers={
                self.name: {"handlers": ["default"], "level": self.log_level},
            }
        )

    @property
    def logger(self):
        """ The logger itself with configurations applied

        Examples:

            >>> mylogger = LogConfig("example").logger
            >>> mylogger.info("my informational message")
            >>> mylogger.error("my error message")
            >>> mylogger.critical("my critical message")
            >>> mylogger.warning("my warning message")

        Returns:
            logging.Logger: The logger
        """
        dictConfig(self.config)
        return logging.getLogger(self.name)
