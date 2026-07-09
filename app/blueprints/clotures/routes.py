"""Blueprint clôtures : verrouillage jour/semaine/mois, réouverture, audit.

Droits : jour = tous les rôles (l'employé clôture sa journée) ;
semaine = gérant/admin ; mois = admin ; réouverture = admin ;
journal d'audit = admin.
"""
from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import AuditLog, Boutique, Cloture
from app.services.clotures import (cloturer_jour, cloturer_semaine,
                                   cloturer_mois, rouvrir)
from app.utils.decorators import role_required

clotures_bp = Blueprint("clotures", __name__, url_prefix="/clotures")


@clotures_bp.route("/")
@login_required
def index():
    clotures = Cloture.query.order_by(Cloture.periode_debut.desc(),
                                      Cloture.id.desc()).limit(100).all()
    boutiques = Boutique.query.filter_by(actif=True).order_by(Boutique.id).all()
    noms_boutiques = {b.id: b.nom for b in boutiques}
    return render_template("clotures/index.html", clotures=clotures,
                           boutiques=boutiques, noms_boutiques=noms_boutiques,
                           aujourdhui=date.today())


def _date_soumise(defaut=None):
    try:
        return date.fromisoformat(request.form.get("jour", ""))
    except ValueError:
        return defaut or date.today()


def _boutique_soumise():
    """Boutique visée : le caissier clôture SA boutique, les autres choisissent."""
    if not current_user.is_gerant:
        return current_user.boutique_id
    try:
        return int(request.form.get("boutique_id", current_user.boutique_id))
    except (TypeError, ValueError):
        return current_user.boutique_id


@clotures_bp.route("/jour", methods=["POST"])
@login_required
def jour():
    try:
        c = cloturer_jour(_date_soumise(), current_user, _boutique_soumise())
        db.session.commit()
        s = c.snapshot
        flash(f"Journée du {c.periode_debut.strftime('%d/%m/%Y')} clôturée — "
              f"CA {s['ca']} FCFA, marge {s['marge']} FCFA, "
              f"{s['nb_ventes']} vente(s).", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("clotures.index"))


@clotures_bp.route("/semaine", methods=["POST"])
@login_required
@role_required("gerant")
def semaine():
    try:
        c = cloturer_semaine(_date_soumise(), current_user, _boutique_soumise())
        db.session.commit()
        flash(f"Semaine du {c.periode_debut.strftime('%d/%m')} au "
              f"{c.periode_fin.strftime('%d/%m/%Y')} clôturée.", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("clotures.index"))


@clotures_bp.route("/mois", methods=["POST"])
@login_required
@role_required("promoteur")
def mois():
    try:
        j = _date_soumise()
        c = cloturer_mois(j.year, j.month, current_user, _boutique_soumise())
        db.session.commit()
        flash(f"Mois de {c.periode_debut.strftime('%m/%Y')} clôturé.", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("clotures.index"))


@clotures_bp.route("/<int:cloture_id>/rouvrir", methods=["POST"])
@login_required
@role_required("promoteur")
def reouvrir(cloture_id):
    cloture = db.get_or_404(Cloture, cloture_id)
    try:
        rouvrir(cloture, current_user, request.form.get("motif", ""))
        db.session.commit()
        flash(f"Période {cloture.type_periode} du "
              f"{cloture.periode_debut.strftime('%d/%m/%Y')} rouverte "
              "(action tracée).", "warning")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("clotures.index"))


@clotures_bp.route("/audit")
@login_required
@role_required("promoteur")
def audit():
    table = request.args.get("table", "").strip()
    requete = AuditLog.query
    if table:
        requete = requete.filter_by(table_nom=table)
    entrees = requete.order_by(AuditLog.id.desc()).limit(200).all()
    tables = [t[0] for t in db.session.query(AuditLog.table_nom).distinct()]
    return render_template("clotures/audit.html", entrees=entrees,
                           tables=sorted(tables), table=table)
