"""Point d'entrée production (Gunicorn) : gunicorn wsgi:app"""
from app import create_app

app = create_app("prod")
