"""This file creates the Flask app and starts the project."""

from flask import Flask

from config import SECRET_KEY
from db import init_db
from routes.page_routes import pages_bp
from routes.api_routes import api_bp


def create_app() -> Flask:
    """Create and configure the Flask app."""
    app = Flask(__name__)
    app.secret_key = SECRET_KEY

    # Create tables if they do not exist yet
    init_db()

    # Register route groups
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)