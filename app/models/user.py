"""Modèle User — rôles : admin, promoteur, gerant, caissier.

Hiérarchie des droits :
- admin / promoteur ("direction") : tout, y compris rapports hebdo/mensuels,
  clôture de mois, réouvertures, audit, utilisateurs, et le verrou du gérant.
- gerant : tout l'opérationnel sur les 3 boutiques ; JAMAIS de points
  hebdo/mensuels ; rapport journalier soumis au drapeau
  `acces_rapport_journalier` (contrôlé par la direction).
- caissier : la caisse et la clôture de sa journée, rien d'autre.
"""
from datetime import datetime, timezone
from flask_login import UserMixin
from app.extensions import db, bcrypt, login_manager

ROLES = ("admin", "promoteur", "gerant", "caissier")


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    nom_complet = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.Enum(*ROLES, name="role_enum"), nullable=False, default="caissier"
    )
    actif = db.Column(db.Boolean, nullable=False, default=True)
    boutique_id = db.Column(
        db.Integer, db.ForeignKey("boutiques.id"), nullable=False, default=1
    )
    entreprise_id = db.Column(db.Integer, db.ForeignKey("entreprises.id"), nullable=False)
    # Verrou direction : accès du GÉRANT au rapport des ventes journalier
    acces_rapport_journalier = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    boutique = db.relationship("Boutique", back_populates="users")
    entreprise = db.relationship("Entreprise", back_populates="users")

    # ---------- Mot de passe ----------
    def set_password(self, mot_de_passe: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(mot_de_passe).decode("utf-8")

    def check_password(self, mot_de_passe: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, mot_de_passe)

    # ---------- Hiérarchie des rôles ----------
    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_direction(self) -> bool:
        """Admin ou promoteur : pilotage complet."""
        return self.role in ("admin", "promoteur")

    @property
    def is_gerant(self) -> bool:
        """Gérant ou au-dessus : opérationnel multi-boutiques."""
        return self.role in ("admin", "promoteur", "gerant")

    @property
    def peut_voir_rapport_journalier(self) -> bool:
        if self.is_direction:
            return True
        if self.role == "gerant":
            return self.acces_rapport_journalier
        return False

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


@login_manager.user_loader
def load_user(user_id: str):
    # Rechargement de l'utilisateur depuis le cookie de session : appelé
    # avant que g.entreprise_id soit résolu (avant_request en dépend via
    # current_user.entreprise_id), donc nécessairement cross-tenant par id,
    # comme la recherche par username à la connexion (cf. auth/routes.py).
    from app.services.tenant import sans_filtre_tenant
    with sans_filtre_tenant():
        return db.session.get(User, int(user_id))
