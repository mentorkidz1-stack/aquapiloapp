"""Verrouillage des périodes : clôtures jour/semaine/mois en cascade.

Règles :
- Jour : clôturable par tout utilisateur connecté (l'employé clôture sa journée).
- Semaine (lundi -> dimanche) : gérant/admin. Tous les jours AVEC ACTIVITÉ doivent
  être clôturés ; les jours sans aucune transaction sont clôturés automatiquement
  avec le drapeau sans_activite (le dimanche fermé ne bloque pas).
- Mois : admin uniquement. Tous les jours du mois doivent être clôturés.
- Réouverture : admin uniquement, motif obligatoire, tracée. On ne rouvre un jour
  que si aucune semaine/mois clôturé ne le couvre (réouverture du haut vers le bas).
"""
import calendar
import json
from datetime import date as date_type, timedelta

from app.extensions import db
from app.models import (Achat, Cloture, Perte, Reouverture, Vente)


# ---------------- Interrogation ----------------
def clotures_couvrant(jour: date_type, boutique_id: int = 1):
    """Clôtures ACTIVES de la boutique couvrant ce jour, tous types confondus."""
    return Cloture.query.filter(
        Cloture.statut == "cloture",
        Cloture.boutique_id == boutique_id,
        Cloture.periode_debut <= jour,
        Cloture.periode_fin >= jour,
    ).all()


def periode_est_cloturee(jour: date_type, boutique_id: int = 1) -> bool:
    return len(clotures_couvrant(jour, boutique_id)) > 0


def jour_a_activite(jour: date_type, boutique_id: int = 1) -> bool:
    return (Vente.query.filter_by(date_vente=jour,
                                  boutique_id=boutique_id).count() > 0
            or Achat.query.filter_by(date_achat=jour,
                                     boutique_id=boutique_id).count() > 0
            or Perte.query.filter_by(date_perte=jour,
                                     boutique_id=boutique_id).count() > 0)


# ---------------- Snapshot ----------------
def snapshot_periode(debut: date_type, fin: date_type,
                     boutique_id: int = 1) -> dict:
    ventes = Vente.query.filter(Vente.date_vente.between(debut, fin),
                                Vente.boutique_id == boutique_id,
                                Vente.statut == "valide").all()
    ca = sum(v.montant_total for v in ventes)
    marge = sum(v.marge_totale for v in ventes)
    achats = db.session.query(
        db.func.coalesce(db.func.sum(Achat.montant_total), 0)
    ).filter(Achat.date_achat.between(debut, fin),
             Achat.boutique_id == boutique_id).scalar()
    pertes = db.session.query(
        db.func.coalesce(db.func.sum(Perte.valeur_perte), 0)
    ).filter(Perte.date_perte.between(debut, fin),
             Perte.boutique_id == boutique_id).scalar()
    return {
        "ca": ca, "marge": marge, "nb_ventes": len(ventes),
        "achats": int(achats), "pertes": int(pertes),
    }


# ---------------- Clôtures ----------------
def _creer_cloture(type_periode, debut, fin, user, boutique_id,
                   sans_activite=False) -> Cloture:
    cloture = Cloture(
        type_periode=type_periode, periode_debut=debut, periode_fin=fin,
        sans_activite=sans_activite,
        snapshot_json=json.dumps(snapshot_periode(debut, fin, boutique_id)),
        user_id=user.id, boutique_id=boutique_id,
    )
    db.session.add(cloture)
    return cloture


def _cloture_existante(type_periode, debut, fin, boutique_id):
    return Cloture.query.filter_by(
        type_periode=type_periode, periode_debut=debut, periode_fin=fin,
        boutique_id=boutique_id,
    ).first()


def cloturer_jour(jour: date_type, user, boutique_id: int = 1) -> Cloture:
    existante = _cloture_existante("jour", jour, jour, boutique_id)
    if existante and existante.statut == "cloture":
        raise ValueError(f"Le {jour.strftime('%d/%m/%Y')} est déjà clôturé "
                         "pour cette boutique.")
    if existante:  # rouverte : on re-clôture en réutilisant la ligne
        existante.statut = "cloture"
        existante.sans_activite = not jour_a_activite(jour, boutique_id)
        existante.snapshot_json = json.dumps(
            snapshot_periode(jour, jour, boutique_id))
        existante.user_id = user.id
        return existante
    return _creer_cloture("jour", jour, jour, user, boutique_id,
                          sans_activite=not jour_a_activite(jour, boutique_id))


def cloturer_semaine(jour_dans_semaine: date_type, user,
                     boutique_id: int = 1) -> Cloture:
    lundi = jour_dans_semaine - timedelta(days=jour_dans_semaine.weekday())
    dimanche = lundi + timedelta(days=6)
    if dimanche >= date_type.today():
        raise ValueError("La semaine n'est pas terminée : clôture possible "
                         "à partir du lundi suivant.")
    existante = _cloture_existante("semaine", lundi, dimanche, boutique_id)
    if existante and existante.statut == "cloture":
        raise ValueError("Cette semaine est déjà clôturée pour cette boutique.")

    # Cascade : chaque jour doit être clôturé ; jours sans activité auto-clôturés
    for i in range(7):
        j = lundi + timedelta(days=i)
        cj = _cloture_existante("jour", j, j, boutique_id)
        if cj and cj.statut == "cloture":
            continue
        if jour_a_activite(j, boutique_id):
            raise ValueError(
                f"Impossible : le {j.strftime('%d/%m/%Y')} a de l'activité "
                "et n'est pas clôturé.")
        if cj:  # rouverte, sans activité
            cj.statut = "cloture"
        else:
            _creer_cloture("jour", j, j, user, boutique_id, sans_activite=True)

    if existante:
        existante.statut = "cloture"
        existante.snapshot_json = json.dumps(
            snapshot_periode(lundi, dimanche, boutique_id))
        existante.user_id = user.id
        return existante
    return _creer_cloture("semaine", lundi, dimanche, user, boutique_id)


def cloturer_mois(annee: int, mois: int, user, boutique_id: int = 1) -> Cloture:
    debut = date_type(annee, mois, 1)
    fin = date_type(annee, mois, calendar.monthrange(annee, mois)[1])
    if fin >= date_type.today():
        raise ValueError("Le mois n'est pas terminé.")
    existante = _cloture_existante("mois", debut, fin, boutique_id)
    if existante and existante.statut == "cloture":
        raise ValueError("Ce mois est déjà clôturé pour cette boutique.")

    # Cascade : tous les jours du mois doivent être clôturés
    j = debut
    while j <= fin:
        cj = _cloture_existante("jour", j, j, boutique_id)
        if not (cj and cj.statut == "cloture"):
            raise ValueError(
                f"Impossible : le {j.strftime('%d/%m/%Y')} n'est pas clôturé. "
                "Clôturez d'abord tous les jours (ou les semaines) du mois.")
        j += timedelta(days=1)

    if existante:
        existante.statut = "cloture"
        existante.snapshot_json = json.dumps(
            snapshot_periode(debut, fin, boutique_id))
        existante.user_id = user.id
        return existante
    return _creer_cloture("mois", debut, fin, user, boutique_id)


# ---------------- Réouverture ----------------
def rouvrir(cloture: Cloture, user, motif: str) -> None:
    if not motif or not motif.strip():
        raise ValueError("Le motif de réouverture est obligatoire.")
    if cloture.statut == "rouvert":
        raise ValueError("Cette période est déjà rouverte.")

    # Du haut vers le bas : on ne rouvre pas un jour couvert par une
    # semaine/mois encore clôturé, ni une semaine couverte par un mois clôturé
    rang = {"jour": 0, "semaine": 1, "mois": 2}
    for autre in clotures_couvrant(cloture.periode_debut, cloture.boutique_id):
        if autre.id != cloture.id and rang[autre.type_periode] > rang[cloture.type_periode]:
            raise ValueError(
                f"Impossible : cette période est couverte par une clôture "
                f"{autre.type_periode} encore active. Rouvrez-la d'abord.")

    cloture.statut = "rouvert"
    db.session.add(Reouverture(cloture_id=cloture.id, user_id=user.id,
                               motif=motif.strip()))
