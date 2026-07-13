"""Calculs de facturation SaaS — revenu ATTENDU d'après les abonnements
enregistrés (Entreprise.tarif_mensuel()), pas un encaissement bancaire
réel : aucune passerelle de paiement n'est intégrée à l'application."""
from app.models import Entreprise
from app.services.tenant import sans_filtre_tenant


def total_mensuel_actif() -> int:
    """Somme des tarifs mensuels des entreprises au statut 'actif'."""
    with sans_filtre_tenant():
        entreprises = Entreprise.query.filter_by(statut_abonnement="actif").all()
        return sum(e.tarif_mensuel() for e in entreprises)


def detail_entreprises():
    """Liste (nom, statut_abonnement, tarif_mensuel) de toutes les
    entreprises, pour la transparence du calcul de répartition."""
    with sans_filtre_tenant():
        entreprises = Entreprise.query.order_by(Entreprise.created_at.desc()).all()
        return [(e.nom, e.statut_abonnement, e.tarif_mensuel()) for e in entreprises]
