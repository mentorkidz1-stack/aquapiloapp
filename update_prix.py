# -*- coding: utf-8 -*-
import sys, unicodedata
from app import create_app, db
from app.models import Produit

PRIX = {"25+":1800,"20+":1700,"16+":1500,"Salomon":1400,"Vitchim":1000,
"Tilapia":1400,"Faux bar":1800,"Guessou":1300,"MTN":1700,"Aran":1300,
"Saucisse":800,"Gésier de poule":1500,"Poulet":2200,"Cuisse normale":1900,
"Cuisse rapide":1700,"Aileron":3000,"Pointe":2200,"Aile de poule":2300,
"Gésier de dinde":2700,"Kpali grand":1500,"Frite":1600,"Pilon":1800}

def norm(t):
    t = unicodedata.normalize("NFD", t or "")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " ".join(t.lower().split())

app = create_app()
with app.app_context():
    produits = {norm(p.nom): p for p in Produit.query.all()}
    apply_ = "--apply" in sys.argv
    absents = []
    for nom, prix in PRIX.items():
        p = produits.get(norm(nom))
        if p is None:
            cand = [x for k, x in produits.items() if norm(nom) in k or k in norm(nom)]
            p = cand[0] if len(cand) == 1 else None
        if p is None:
            absents.append(nom); continue
        print(f"  {p.nom:<25} {p.prix_vente_kilo} -> {prix} FCFA")
        if apply_:
            p.prix_vente_kilo = prix
    if absents:
        print("INTROUVABLES (a creer) :", ", ".join(absents))
    if apply_:
        db.session.commit(); print(">>> PRIX ENREGISTRES.")
    else:
        print(">>> Apercu seulement. Relance avec : python update_prix.py --apply")