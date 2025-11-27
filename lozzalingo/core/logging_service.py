"""
Centralized logging service for the Mario Pinto application.
Provides structured logging with database storage and easy integration.
"""

import sqlite3
import json
from datetime import datetime
from flask import request, has_request_context
from .database import Database
from .config import Config


class LoggingService:
    """Centralized logging service for application-wide logging"""

    @staticmethod
    def _ensure_logs_table():
        """Ensure the app_logs table exists"""
        try:
            with Database.connect(Config.ANALYTICS_DB) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS app_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        level TEXT NOT NULL,
                        source TEXT NOT NULL,
                        message TEXT NOT NULL,
                        details TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        request_path TEXT,
                        user_id TEXT
                    )
                """)

                # Create index for better performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_logs_timestamp
                    ON app_logs(timestamp DESC)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_logs_level
                    ON app_logs(level)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_logs_source
                    ON app_logs(source)
                """)

                conn.commit()
        except Exception as e:
            print(f"Failed to ensure logs table: {e}")

    @staticmethod
    def _get_request_context():
        """Extract request context information"""
        if not has_request_context():
            return None, None, None

        try:
            ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
            if ip_address and ',' in ip_address:
                ip_address = ip_address.split(',')[0].strip()

            user_agent = request.headers.get('User-Agent', '')
            request_path = request.path

            return ip_address, user_agent, request_path
        except Exception:
            return None, None, None

    @staticmethod
    def log(level, source, message, details=None, user_id=None):
        """
        Log a message to the database

        Args:
            level (str): Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            source (str): Source component (analytics, news, merchandise, etc.)
            message (str): Main log message
            details (str/dict): Additional details (will be JSON-encoded if dict)
            user_id (str): Optional user identifier
        """
        try:
            # Ensure table exists
            LoggingService._ensure_logs_table()

            # Get request context
            ip_address, user_agent, request_path = LoggingService._get_request_context()

            # Process details
            if isinstance(details, dict):
                details = json.dumps(details, indent=2)

            # Store log entry
            timestamp = datetime.now().isoformat()

            with Database.connect(Config.ANALYTICS_DB) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO app_logs
                    (timestamp, level, source, message, details, ip_address, user_agent, request_path, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp, level.upper(), source, message, details,
                    ip_address, user_agent, request_path, user_id
                ))
                conn.commit()

        except Exception as e:
            # Fallback to console logging if database fails
            print(f"[{datetime.now().isoformat()}] [{level.upper()}] [{source}] {message}")
            if details:
                print(f"Details: {details}")
            print(f"Logging service error: {e}")

    @staticmethod
    def debug(source, message, details=None, user_id=None):
        """Log debug message"""
        LoggingService.log('DEBUG', source, message, details, user_id)

    @staticmethod
    def info(source, message, details=None, user_id=None):
        """Log info message"""
        LoggingService.log('INFO', source, message, details, user_id)

    @staticmethod
    def warning(source, message, details=None, user_id=None):
        """Log warning message"""
        LoggingService.log('WARNING', source, message, details, user_id)

    @staticmethod
    def error(source, message, details=None, user_id=None):
        """Log error message"""
        LoggingService.log('ERROR', source, message, details, user_id)

    @staticmethod
    def critical(source, message, details=None, user_id=None):
        """Log critical message"""
        LoggingService.log('CRITICAL', source, message, details, user_id)

    @staticmethod
    def log_user_action(source, action, user_id=None, details=None):
        """Log user actions (login, signup, purchase, etc.)"""
        LoggingService.info(source, f"User action: {action}", details, user_id)

    @staticmethod
    def log_api_call(source, endpoint, method='GET', status_code=200, details=None):
        """Log API calls"""
        message = f"API {method} {endpoint} - Status: {status_code}"
        level = 'INFO' if 200 <= status_code < 400 else 'WARNING' if status_code < 500 else 'ERROR'
        LoggingService.log(level, source, message, details)

    @staticmethod
    def log_error_with_traceback(source, error, details=None):
        """Log error with full traceback"""
        import traceback
        error_details = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc()
        }
        if details:
            error_details['additional_details'] = details

        LoggingService.error(source, f"Exception occurred: {type(error).__name__}", error_details)

    @staticmethod
    def log_security_event(message, details=None, ip_address=None):
        """Log security-related events"""
        if ip_address and has_request_context():
            # Override request IP if provided
            details = details or {}
            details['provided_ip'] = ip_address

        LoggingService.warning('security', message, details)

    @staticmethod
    def cleanup_old_logs(days_to_keep=30):
        """Clean up old log entries"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            cutoff_iso = cutoff_date.isoformat()

            with Database.connect(Config.ANALYTICS_DB) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM app_logs
                    WHERE timestamp < ?
                """, (cutoff_iso,))

                deleted_count = cursor.rowcount
                conn.commit()

                LoggingService.info('system', f"Cleaned up {deleted_count} old log entries")
                return deleted_count

        except Exception as e:
            LoggingService.error('system', f"Failed to cleanup old logs: {e}")
            return 0


# Convenience instance for easy importing
logger = LoggingService()