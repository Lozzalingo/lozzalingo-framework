"""
Lozzalingo Core
===============

Core utilities and shared functionality for Lozzalingo modules.
"""

from .config import Config
from .database import Database
from .logging_service import LoggingService, logger


def db_log(level, source, message, details=None):
    """Convenience helper for persistent DB logging from any module.

    Usage:
        from lozzalingo.core import db_log
        db_log('error', 'subscribers', 'Database error in subscribe', {'error': str(e)})
    """
    try:
        getattr(logger, level)(source, message, details)
    except Exception:
        pass  # Never let logging break the caller


__all__ = ['Config', 'Database', 'LoggingService', 'logger', 'db_log']
