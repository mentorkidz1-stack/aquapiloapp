"""Application factory."""
import os
from flask import Flask, render_template

from config import config_map
from app.extensions import db, migrate, login_manager, bcrypt, csrf


def format_fcfa(valeur) -> str:
    """1500 -> '1 500 FCFA' (espace insécable fine comme séparateur de milliers)."""
    if valeur is None:
        return "0 FCFA"
    return f"{int(valeur):,}".replace(",", "\u202f") + " FCFA"


def create_app(config_name: str | None = None,
               config_surcharges: dict | None = None) -> Flask:
    config_name = config_name or os.environ.get("FLASK_ENV", "dev")
    app = Flask(__name__)
    app.config.from_object(config_map.get(config_name, config_map["dev"]))
    if config_surcharges:  # utilisé par les tests (URI SQLite éphémère...)
        app.config.update(config_surcharges)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)

    # Filtre Jinja pour le format monétaire
    app.jinja_env.filters["fcfa"] = format_fcfa

    # Blueprints
    from app.blueprints.auth.routes import auth_bp
    from app.blueprints.main.routes import main_bp
    from app.blueprints.ventes.routes import ventes_bp
    from app.blueprints.produits.routes import produits_bp
    from app.blueprints.achats.routes import achats_bp
    from app.blueprints.pertes.routes import pertes_bp
    from app.blueprints.stocks.routes import stocks_bp
    from app.blueprints.clotures.routes import clotures_bp
    from app.blueprints.rapports.routes import rapports_bp
    from app.blueprints.admin.routes import admin_bp
    from app.blueprints.operateur.routes import operateur_bp
    from app.blueprints.associes.routes import associes_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(ventes_bp)
    app.register_blueprint(produits_bp)
    app.register_blueprint(achats_bp)
    app.register_blueprint(pertes_bp)
    app.register_blueprint(stocks_bp)
    app.register_blueprint(clotures_bp)
    app.register_blueprint(rapports_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(operateur_bp)
    app.register_blueprint(associes_bp)

    # Modèles (import nécessaire pour flask db migrate)
    from app import models  # noqa: F401

    # Journal d'audit automatique (événements SQLAlchemy)
    from app.services.audit import init_audit
    init_audit()

    # Isolation multi-tenant : filtre automatique + auto-marquage + garde-fous
    from app.services.tenant import init_tenant_context, init_isolation
    init_tenant_context(app)
    init_isolation()

    # Pages d'erreur
    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    return app
