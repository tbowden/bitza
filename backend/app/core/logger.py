import logging

# Get these from the config.py
LOG_FILE_LEVEL = "INFO"
LOG_CONSOLE_LEVEL = "INFO"
LOG_FILE_NAME = "bitza.log"


numeric_log_file_level = getattr(logging, LOG_FILE_LEVEL, None)
numeric_log_console_level = getattr(logging, LOG_CONSOLE_LEVEL, None)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

stream_handler = logging.StreamHandler()
#stream_handler.setLevel()
logger.addHandler(stream_handler)

file_handler = logging.FileHandler(LOG_FILE_NAME)
logger.addHandler(file_handler)

#logger.info("info message")
#logger.debug("debug message")
#logger.warning("warning message")

