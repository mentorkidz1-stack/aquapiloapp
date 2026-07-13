"""Modèle DemandeAcces — formulaire de la landing page publique.

Une poissonnerie intéressée par la plateforme remplit ce formulaire.
Aucune activation automatique de compte ni d'entreprise : c'est un
prospect à traiter manuellement (l'exploitant crée l'Entreprise et le
premier compte lui-même, comme pour DONA)."""
from datetime import datetime, timezone
from app.extensions import db


class DemandeAcces(db.Model):
    __tablename__ = "demandes_acces"

    id = db.Column(db.Integer, primary_key=True)
    nom_poissonnerie = db.Column(db.String(150), nullable=False)
    responsable = db.Column(db.String(100), nullable=False)
    telephone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    nombre_boutiques = db.Column(db.Integer, nullable=False)
    traite = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<DemandeAcces {self.nom_poissonnerie}>"
