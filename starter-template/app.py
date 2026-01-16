"""
Lozzalingo Starter Template
===========================

A ready-to-run Flask application with all Lozzalingo modules enabled.

Run with:
    python app.py

Or with Docker:
    docker-compose up

Visit:
    http://localhost:5000        - Homepage
    http://localhost:5000/admin  - Admin panel
"""

from flask import Flask, render_template
from lozzalingo import Lozzalingo

# Create Flask app
app = Flask(__name__)

# Initialize Lozzalingo - this registers all modules automatically
lozzalingo = Lozzalingo(app)


# =============================================================================
# Your Routes - Add your own routes below
# =============================================================================

@app.route('/')
def index():
    """Homepage"""
    return render_template('index.html')


@app.route('/about')
def about():
    """About page"""
    return render_template('about.html')


# =============================================================================
# Run the app
# =============================================================================

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("Lozzalingo Starter Template")
    print("=" * 60)
    print(f"Homepage:        http://localhost:5000")
    print(f"Admin Panel:     http://localhost:5000/admin")
    print(f"Admin Login:     http://localhost:5000/admin/login")
    print(f"Create Admin:    http://localhost:5000/admin/create-admin")
    print("=" * 60 + "\n")

    app.run(host='0.0.0.0', port=5000, debug=True)
