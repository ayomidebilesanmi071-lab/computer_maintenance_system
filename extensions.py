"""Shared Flask extension instances.

These objects are created once and bound to the application inside the
application factory (``app.create_app``).  Keeping them in a dedicated module
prevents circular imports between models, routes and services.
"""

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

# SQLAlchemy ORM instance - every model inherits from ``db.Model``.
db = SQLAlchemy()

# Flask-Login session authentication.
login_manager = LoginManager()

# CSRF protection for every state-changing (POST/PUT/PATCH/DELETE) request.
csrf = CSRFProtect()
