# File: app/core/logging.py
"""
Logging configuration.
"""
import logging
import sys
from app.config import get_settings

def setup_logging():
    """Configure application logging."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
        # Configure specific loggers
    loggers_config = {
        "uvicorn": logging.INFO,
        "uvicorn.error": logging.INFO,
        "uvicorn.access": logging.WARNING if settings.is_production else logging.INFO,
        "fastapi": logging.INFO,
        "qdrant_client": logging.WARNING,
        "sentence_transformers": logging.WARNING,
        "httpx": logging.WARNING,
        "motor": logging.WARNING,
        "pymongo": logging.WARNING,
        "pymongo.topology": logging.WARNING,
        "pymongo.connection": logging.WARNING,
        "pymongo.serverSelection": logging.WARNING,
        "pymongo.command": logging.WARNING
    }
    
    for logger_name, level in loggers_config.items():
        logging.getLogger(logger_name).setLevel(level)
    
    # Set specific loggers
    logger = logging.getLogger("json_xml_transformer")
    return logger