"""Génère 3 semaines d'activité réaliste pour tester dashboards et rapports.

À N'UTILISER QU'EN DÉVELOPPEMENT / DÉMONSTRATION, jamais en production.
Usage : python seed_demo.py
"""
import random
from datetime import date, time, timedelta
from decimal import Decimal

from flask import g

from app import create_app
from app.extensions import db
from app.models import Entreprise, Perte, Produit, User, Vente, VenteLigne
from app.services.cmup import enregistrer_achat

random.seed(42)
app = create_app()

with app.app_context(), app.test_request_context():
    entreprise = Entreprise.query.filter_by(nom="DONA").first()
    if entreprise is None:
        raise SystemExit("Entreprise DONA introuvable : lancez d'abord seed.py")
    g.entreprise_id = entreprise.id  # active l'auto-marquage entreprise_id

    if Vente.query.count() > 0:
        print("Des ventes existent déjà : seed_demo annulé par prudence.")
        raise SystemExit

    admin = User.query.filter_by(username="admin").first()
    produits = Produit.query.filter_by(actif=True).all()
    debut = date.today() - timedelta(days=21)

    # Approvisionnement initial massif
    for p in produits:
        enregistrer_achat(p, Decimal(random.randint(30, 80)),
                          p.prix_achat, "Fournisseur démo", debut, admin.id)
    db.session.commit()

    seq_global = 0
    jour = debut
    while jour <= date.today():
        if jour.weekday() == 6 and random.random() < 0.7:
            jour += timedelta(days=1)
            continue    # dimanche souvent fermé

        # Réapprovisionnement 2 fois par semaine environ
        if random.random() < 0.3:
            p = random.choice(produits)
            enregistrer_achat(p, Decimal(random.randint(10, 40)),
                              int(p.prix_achat * random.uniform(0.95, 1.08)),
                              "Fournisseur démo", jour, admin.id)

        # 5 à 15 ventes par jour
        for n in range(random.randint(5, 15)):
            seq_global += 1
            v = Vente(numero_ticket=f"D-{jour.strftime('%Y%m%d')}-{n+1:04d}",
                      date_vente=jour,
                      heure_vente=time(random.randint(8, 19),
                                       random.randint(0, 59)),
                      mode_paiement=random.choice(
                          ["especes", "especes", "mtn_momo", "moov_money",
                           "celtiis"]),
                      user_id=admin.id, boutique_id=1)
            total = 0
            for _ in range(random.randint(1, 3)):
                p = random.choice(produits)
                qte = (Decimal(random.randint(1, 4))
                       if p.unite == "piece"
                       else Decimal(str(round(random.uniform(0.5, 4), 3))))
                montant = int(qte * p.prix_vente)
                v.lignes.append(VenteLigne(
                    produit_id=p.id, quantite=qte,
                    prix_catalogue=p.prix_vente, prix_applique=p.prix_vente,
                    montant=montant, cmup_au_moment=p.cmup_actuel,
                    marge=int((p.prix_vente - p.cmup_actuel) * qte)))
                total += montant
            v.montant_total = total
            db.session.add(v)

        # Une perte de temps en temps
        if random.random() < 0.25:
            p = random.choice(produits)
            qte = Decimal(str(round(random.uniform(0.5, 3), 3)))
            db.session.add(Perte(
                produit_id=p.id, quantite=qte,
                motif=random.choice(["Périmé", "Casse congélateur", "Invendu"]),
                valeur_perte=int(qte * p.cmup_actuel),
                date_perte=jour, user_id=admin.id))
        jour += timedelta(days=1)

    db.session.commit()
    print(f"Démo générée : {Vente.query.count()} ventes, "
          f"{Perte.query.count()} pertes sur 3 semaines.")
