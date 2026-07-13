"""Modèle AuditLog : journal de toutes les écritures."""
from datetime import datetime, timezone
from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    entreprise_id = db.Column(db.Integer, db.ForeignKey("entreprises.id"), nullable=False)
    action = db.Column(db.Enum("create", "update", "delete", name="action_enum"),
                       nullable=False)
    table_nom = db.Column(db.String(50), nullable=False, index=True)
    enregistrement_id = db.Column(db.Integer, nullable=False)
    ancienne_valeur = db.Column(db.Text, nullable=True)   # JSON
    nouvelle_valeur = db.Column(db.Text, nullable=True)   # JSON
    created_at = db.Column(db.DateTime, nullable=False, index=True,
                           default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User")
