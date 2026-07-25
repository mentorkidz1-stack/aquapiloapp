"""Blueprint rapports : comparaisons, top/flop, exports. Accès gérant/admin."""
import calendar
from datetime import date, timedelta

from flask import (Blueprint, render_template, request, send_file, abort,
                   flash, redirect, url_for)
import io

from app.models import Boutique
from app.services.rapports import (indicateurs_periode, serie_semaines,
                                   serie_mois, top_flop)
from app.services.exports import export_excel, export_pdf
from app.utils.decorators import role_required
from flask_login import login_required, current_user


def _boutique_choisie():
    """None = consolidé toutes boutiques."""
    brut = request.args.get("boutique", "")
    try:
        return int(brut) if brut and brut != "all" else None
    except ValueError:
        return None

rapports_bp = Blueprint("rapports", __name__, url_prefix="/rapports")


def db_get_boutique(boutique_id):
    from app.extensions import db
    return db.session.get(Boutique, boutique_id)


def _bornes(type_p: str, jour: date):
    if type_p == "jour":
        return jour, jour
    if type_p == "semaine":
        lundi = jour - timedelta(days=jour.weekday())
        return lundi, lundi + timedelta(days=6)
    if type_p == "mois":
        return (date(jour.year, jour.month, 1),
                date(jour.year, jour.month,
                     calendar.monthrange(jour.year, jour.month)[1]))
    abort(404)


@rapports_bp.route("/")
@login_required
@role_required("gerant")
def index():
    # Le GÉRANT n'a plus accès aux rapports, quel que soit le verrou
    # acces_rapport_journalier (qui reste réservé au promoteur/admin).
    if current_user.role == "gerant":
        flash("Les rapports ne sont pas accessibles au rôle Gérant.", "warning")
        return redirect(url_for("main.dashboard"))

    boutique_id = _boutique_choisie()
    boutiques = Boutique.query.filter_by(actif=True).order_by(Boutique.id).all()
    auj = date.today()

    # Le GÉRANT ne voit jamais les points hebdo/mensuels.
    if not current_user.is_direction:
        if not current_user.peut_voir_rapport_journalier:
            flash("L'accès au rapport des ventes journalier a été verrouillé "
                  "par la direction.", "warning")
            return redirect(url_for("main.dashboard"))
        ind = indicateurs_periode(auj, auj, boutique_id)
        return render_template("rapports/jour.html", ind=ind,
                               boutiques=boutiques, boutique_id=boutique_id,
                               aujourdhui=auj)

    semaines = serie_semaines(8, boutique_id)
    mois = serie_mois(6, boutique_id)
    top, flop = top_flop(auj.replace(day=1), auj, 5, boutique_id)
    return render_template("rapports/index.html", semaines=semaines,
                           mois=mois, top=top, flop=flop,
                           boutiques=boutiques, boutique_id=boutique_id,
                           aujourdhui=auj)


@rapports_bp.route("/export/<type_p>/<fmt>")
@login_required
@role_required("gerant")
def export(type_p, fmt):
    if type_p not in ("jour", "semaine", "mois") or fmt not in ("xlsx", "pdf"):
        abort(404)
    # Le GÉRANT n'a plus accès aux rapports, quel que soit le verrou.
    if current_user.role == "gerant":
        abort(403)
    # Gérant : jamais d'export hebdo/mensuel ; journalier selon le verrou
    if not current_user.is_direction:
        if type_p != "jour" or not current_user.peut_voir_rapport_journalier:
            abort(403)
    try:
        jour = date.fromisoformat(request.args.get("jour", ""))
    except ValueError:
        jour = date.today()
    debut, fin = _bornes(type_p, jour)
    boutique_id = _boutique_choisie()
    boutique_nom = "Toutes boutiques"
    if boutique_id:
        b = db_get_boutique(boutique_id)
        boutique_nom = b.nom if b else boutique_nom

    if fmt == "xlsx":
        contenu = export_excel(type_p, debut, fin, boutique_id, boutique_nom)
        mimetype = ("application/vnd.openxmlformats-officedocument"
                    ".spreadsheetml.sheet")
    else:
        contenu = export_pdf(type_p, debut, fin, boutique_id, boutique_nom)
        mimetype = "application/pdf"

    nom = f"point_{type_p}_{debut.isoformat()}.{fmt}"
    return send_file(io.BytesIO(contenu), mimetype=mimetype,
                     as_attachment=True, download_name=nom)
