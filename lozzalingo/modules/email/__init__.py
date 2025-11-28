"""
Email Module
============

Provides email sending functionality with Resend API integration.
Includes configurable templates for welcome, purchase, shipping, and news emails.
"""

from .routes import email_preview_bp
from .email_service import EmailService, email_service

__all__ = ['email_preview_bp', 'EmailService', 'email_service']
