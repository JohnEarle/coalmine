"""
Centralized logging configuration for Coalmine.

Provides structured JSON logging with configurable log levels.
"""
import logging
import os
import json
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra context if present
        if hasattr(record, "canary_id"):
            log_data["canary_id"] = record.canary_id
        if hasattr(record, "resource_type"):
            log_data["resource_type"] = record.resource_type
        if hasattr(record, "action"):
            log_data["action"] = record.action
            
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger for the given module name.
    
    Usage:
        from src.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Message", extra={"canary_id": "abc123"})
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler()
        
        # Use JSON format in production, simple format in development
        log_format = os.getenv("LOG_FORMAT", "json")
        if log_format == "json":
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            ))
        
        logger.addHandler(handler)
        
        # Set log level from environment
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    return logger
