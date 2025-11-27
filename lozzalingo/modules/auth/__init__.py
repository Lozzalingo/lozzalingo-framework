"""
Lozzalingo Auth Module

Provides user authentication functionality including:
- Email/password authentication
- Email verification
- Password reset
- OAuth integration (Google, GitHub)
- User session management
"""

from .routes import signin_bp as auth_bp, init_oauth
from .database import SignInDatabase
from .utils import configure_oauth, oauth

__all__ = ['auth_bp', 'SignInDatabase', 'init_oauth', 'configure_oauth', 'oauth']
