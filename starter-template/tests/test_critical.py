"""
Critical tests for the Lozzalingo starter template.
Run with: pytest tests/test_critical.py -v
"""

import os
import sys
import pytest

# Add parent directory to path so we can import main
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def app():
    """Create application for testing."""
    from main import app
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


def test_app_starts(app):
    """App should start without errors."""
    assert app is not None


def test_health_endpoint(client):
    """Health endpoint should return 200."""
    response = client.get('/health')
    assert response.status_code == 200


def test_homepage(client):
    """Homepage should return 200."""
    response = client.get('/')
    assert response.status_code == 200
