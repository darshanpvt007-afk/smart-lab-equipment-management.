"""Production entry point for a WSGI server, for example:

    gunicorn --config gunicorn.conf.py wsgi:app

Configuration comes only from environment variables set by the host (no
.env file is read here). With APP_ENV=production, create_app() refuses to
start when SECRET_KEY, DB_USER or DB_PASSWORD are missing or unsafe.
"""
from app import create_app

app = create_app()
