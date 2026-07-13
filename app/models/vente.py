"""Modèles Vente (ticket) et VenteLigne."""
from datetime import datetime, timezone, date
from app.extensions import db

MODES_PAIEMENT = ("especes", "mtn_momo", "moov_money", "celtiis")
MODES_LIBELLES = {
    "especes": "Espèces",
    "mtn_momo": "MTN MoMo",
    "moov_money": "Moov Money",
    "celtiis": "Celtiis Cash",
}


class Vente(db.Model):
    __tablename__ = "ventes"

    id = db.Column(db.Integer, primary_key=True)
    numero_ticket = db.Column(db.String(20), unique=True, nullable=False)
    date_vente = db.Column(db.Date, nullable=False, default=date.today, index=True)
    heure_vente = db.Column(db.Time, nullable=False)
    mode_paiement = db.Column(db.Enum(*MODES_PAIEMENT, name="mode_paiement_enum"),
                              nullable=False)
    montant_total = db.Column(db.Integer, nullable=False, default=0)
    statut = db.Column(db.Enum("valide", "annule", name="statut_vente_enum"),
                       nullable=False, default="valide")
    boutique_id = db.Column(db.Integer, db.ForeignKey("boutiques.id"),
                            nullable=False, default=1)
    entreprise_id = db.Column(db.Integer, db.ForeignKey("entreprises.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    lignes = db.relationship("VenteLigne", back_populates="vente",
                             cascade="all, delete-orphan")
    user = db.relationship("User")

    @property
    def mode_paiement_libelle(self):
        return MODES_LIBELLES.get(self.mode_paiement, self.mode_paiement)

    @property
    def marge_totale(self):
        return sum(l.marge for l in self.lignes)


class VenteLigne(db.Model):
    __tablename__ = "vente_lignes"

    id = db.Column(db.Integer, primary_key=True)
    vente_id = db.Column(db.Integer, db.ForeignKey("ventes.id"),
                         nullable=False, index=True)
    produit_id = db.Column(db.Integer, db.ForeignKey("produits.id"),
                           nullable=False, index=True)
    quantite = db.Column(db.Numeric(10, 3), nullable=False)
    prix_catalogue = db.Column(db.Integer, nullable=False)  # prix officiel au moment T
    prix_applique = db.Column(db.Integer, nullable=False)   # prix réellement facturé
    montant = db.Column(db.Integer, nullable=False)
    cmup_au_moment = db.Column(db.Integer, nullable=False)  # figé : marge immuable
    marge = db.Column(db.Integer, nullable=False)

    vente = db.relationship("Vente", back_populates="lignes")
    produit = db.relationship("Produit")
