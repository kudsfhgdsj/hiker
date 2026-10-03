"""Entry point for the WSGI server: `gunicorn hiker_web.wsgi:app`."""

from hiker_web import create_app

app = create_app()
