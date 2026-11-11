"""Database initialisation and seeding scripts.

Kept in a package (not at the project root) so ``flask --app app seed-db`` can
import them, and so they can be executed directly::

    python scripts/init_db.py
    python scripts/seed_db.py
"""
