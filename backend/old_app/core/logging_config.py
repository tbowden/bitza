import logging.config
from app.core.config import settings


def _resolve_format():
    """
    Determines which formatter to use.
    """
    if settings.LOG_FORMAT == "console":
        return "console"
    if settings.LOG_FORMAT == "json":
        return "json"

    # auto mode
    return "console" if settings.DEBUG else "json"


def setup_logging():

    selected_formatter = _resolve_format()

    formatters = {
        "console": {
            "format": "%(levelname)s | %(name)s | %(message)s",
        },
        "standard": {
            "format": "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    }

    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "level": settings.LOG_LEVEL,
            "formatter": selected_formatter,
            "stream": "ext://sys.stdout",
        }
    }

    # Dev-only rotating file logs
    if settings.DEBUG:
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": settings.LOG_LEVEL,
            "formatter": "standard",
            "filename": settings.LOG_FILE_NAME,
            "maxBytes": settings.LOG_MAX_BYTES,
            "backupCount": settings.LOG_BACKUP_COUNT,
        }

    # Dev-only sql logging
    loggers = {}
    if settings.DEBUG:
        loggers["sqlalchemy.engine"] = {
            "level": "INFO",   # INFO = SQL statements
            # use DEBUG if you also want bound parameters
            "handlers": ["console"],
            "propagate": False,
        }


    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": handlers,
        "root": {
            "level": settings.LOG_LEVEL,
            "handlers": list(handlers.keys()),
        },
        "loggers": loggers,
    })
