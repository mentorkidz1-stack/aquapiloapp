"""Configuration de l'application — dev (SQLite) / prod (MySQL)."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Configuration commune."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-moi-en-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    # Session : déconnexion automatique après 8 h d'inactivité
    PERMANENT_SESSION_LIFETIME = 8 * 3600
    # Accès opérateur SaaS (support/facturation/activation, cross-tenant) :
    # identifiants distincts des comptes locataires, jamais dans le code ni
    # committés — uniquement dans .env (cf. app/blueprints/operateur).
    OPERATEUR_USERNAME = os.environ.get("OPERATEUR_USERNAME")
    OPERATEUR_PASSWORD_HASH = os.environ.get("OPERATEUR_PASSWORD_HASH")
    # Espace associés (répartition du chiffre d'affaires SaaS) : chaque
    # associé a son propre identifiant/mot de passe et son pourcentage,
    # jamais committés — uniquement dans .env (cf. app/blueprints/associes).
    ASSOCIES = [
        {
            "nom": os.environ.get("ASSOCIE_1_NOM"),
            "username": os.environ.get("ASSOCIE_1_USERNAME"),
            "password_hash": os.environ.get("ASSOCIE_1_PASSWORD_HASH"),
            "pourcentage": int(os.environ.get("ASSOCIE_1_POURCENTAGE") or 0),
        },
        {
            "nom": os.environ.get("ASSOCIE_2_NOM"),
            "username": os.environ.get("ASSOCIE_2_USERNAME"),
            "password_hash": os.environ.get("ASSOCIE_2_PASSWORD_HASH"),
            "pourcentage": int(os.environ.get("ASSOCIE_2_POURCENTAGE") or 0),
        },
    ]


class DevConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DEV_DATABASE_URL")
        or f"sqlite:///{BASE_DIR / 'poissonnerie_dev.db'}"
    )


class ProdConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = (
        "mysql+pymysql://{user}:{password}@{host}/{db}?charset=utf8mb4".format(
            user=os.environ.get("MYSQL_USER", ""),
            password=os.environ.get("MYSQL_PASSWORD", ""),
            host=os.environ.get("MYSQL_HOST", "localhost"),
            db=os.environ.get("MYSQL_DB", "poissonnerie"),
        )
    )
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}


config_map = {"dev": DevConfig, "prod": ProdConfig}
