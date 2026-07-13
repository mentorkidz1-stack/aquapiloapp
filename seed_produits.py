"""Chargement des 28 produits avec des prix de DÉMONSTRATION.

ATTENTION : les prix sont des valeurs plausibles à ajuster avec les
prix réels de la poissonnerie avant la mise en production.

Usage : python seed_produits.py
"""
from app import create_app
from app.extensions import db
from app.models import Entreprise, Produit

# (nom, catégorie, unité, prix_achat, prix_vente) — FCFA / unité
PRODUITS = [
    # ---- Poissons (calibres et noms locaux) ----
    ("14+",          "poisson", "kg", 1300, 1600),
    ("16+",          "poisson", "kg", 1350, 1650),
    ("20+",          "poisson", "kg", 1400, 1700),
    ("22+",          "poisson", "kg", 1450, 1750),
    ("25+",          "poisson", "kg", 1500, 1800),
    ("MTN",          "poisson", "kg", 1200, 1500),
    ("Guessou",      "poisson", "kg", 1000, 1300),
    ("Kpali",        "poisson", "kg", 1100, 1400),
    ("Salomon",      "poisson", "kg", 2500, 3000),
    ("Sardines",     "poisson", "kg",  900, 1200),
    ("Vitchim",      "poisson", "kg", 1000, 1300),
    ("Tilapia",      "poisson", "kg", 1500, 1900),
    ("Cica-Cica",    "poisson", "kg", 1100, 1400),
    ("Aran",         "poisson", "kg",  950, 1250),
    ("Tchêkê",       "poisson", "kg", 1200, 1500),
    ("Mademoiselle", "poisson", "kg", 1300, 1650),
    # ---- Viandes / Volaille ----
    ("Aileron",          "viande", "kg",    1500, 1900),
    ("Pointe",           "viande", "kg",    1600, 2000),
    ("Cuisse normale",   "viande", "kg",    1450, 1800),
    ("Cuisse rapide",    "viande", "kg",    1500, 1850),
    ("Poulet complet",   "viande", "piece", 3500, 4500),
    ("Karaté",           "viande", "kg",    1400, 1750),
    ("Gésier de poule",  "viande", "kg",    1800, 2200),
    ("Gésier de dinde",  "viande", "kg",    2000, 2500),
    ("Saucisse",         "viande", "kg",    1700, 2100),
    ("Frite",            "viande", "kg",    1500, 1900),
    ("Faux bar",         "viande", "kg",    1300, 1650),
    ("Pilon",            "viande", "kg",    1500, 1850),
]

app = create_app()
with app.app_context():
    entreprise = Entreprise.query.filter_by(nom="DONA").first()
    if entreprise is None:
        raise SystemExit("Entreprise DONA introuvable : lancez d'abord seed.py")

    crees = 0
    for nom, categorie, unite, pa, pv in PRODUITS:
        existant = Produit.query.filter_by(
            nom=nom, entreprise_id=entreprise.id).first()
        if existant is None:
            db.session.add(Produit(
                nom=nom, categorie=categorie, unite=unite,
                prix_achat=pa, prix_vente=pv,
                cmup_actuel=pa,      # avant tout achat, le CMUP démarre au prix d'achat
                seuil_alerte=10,
                entreprise_id=entreprise.id,
            ))
            crees += 1
    db.session.commit()
    print(f"{crees} produit(s) créé(s), {len(PRODUITS) - crees} déjà existant(s).")
