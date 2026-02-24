"""
Cross-Post Module
=================

Service for cross-posting blog/project content to external platforms:
- LinkedIn (article share via Posts API)
- Medium (full HTML via official API)
- Substack (Markdown via python-substack library)
"""

from .crosspost_service import CrossPostService, crosspost_service

__all__ = ['CrossPostService', 'crosspost_service']
