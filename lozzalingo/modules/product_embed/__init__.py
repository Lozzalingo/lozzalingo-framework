"""
Product Embed module.

Provides a proxy endpoint and sidebar template for embedding
products from the centralised E-commerce Service into any
Lozzalingo app.
"""

from .routes import product_embed_bp

__all__ = ['product_embed_bp']
