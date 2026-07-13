"""Données initiales Poissonnerie DONA : 3 boutiques + 5 comptes.

Usage : python seed.py
Mots de passe par défaut À CHANGER dès la première connexion.
"""
from app import create_app
from app.extensions import db
from app.models import Boutique, Entreprise, User

BOUTIQUES = ["Boutique 1 Marché", "Boutique 2 Pavé", "Boutique 3 Chambre Froide"]

# (username, nom complet, rôle, boutique, mot de passe par défaut)
UTILISATEURS = [
    ("admin",     "Administrateur", "admin",     1, "Admin@2026"),
    ("promoteur", "Promoteur",      "promoteur", 1, "Promoteur@2026"),
    ("gerant",    "Gérant",         "gerant",    1, "Gerant@2026"),
    ("caissier1", "Caissier 1",     "caissier",  1, "Caissier1@2026"),
    ("caissier2", "Caissier 2",     "caissier",  2, "Caissier2@2026"),
]

app = create_app()
with app.app_context():
    # Entreprise DONA : ce script ne seed que sa propre entreprise
    entreprise = Entreprise.query.filter_by(nom="DONA").first()
    if entreprise is None:
        entreprise = Entreprise(nom="DONA", statut_abonnement="actif")
        db.session.add(entreprise)
        db.session.commit()
    print("Entreprise :", entreprise.nom)

    # Boutiques : renomme la 1re si elle existe, crée les manquantes
    for i, nom in enumerate(BOUTIQUES, start=1):
        b = db.session.get(Boutique, i)
        if b:
            b.nom = nom
        else:
            db.session.add(Boutique(id=i, nom=nom, entreprise_id=entreprise.id))
    db.session.commit()
    print("3 boutiques en place :", ", ".join(BOUTIQUES))

    for username, nom, role, btq, mdp in UTILISATEURS:
        u = User.query.filter_by(username=username).first()
        if u is None:
            u = User(username=username, nom_complet=nom, role=role,
                     boutique_id=btq, entreprise_id=entreprise.id)
            u.set_password(mdp)
            db.session.add(u)
            print(f"Compte créé : {username} / {mdp} ({role}, boutique {btq})")
        else:
            u.role, u.nom_complet, u.boutique_id = role, nom, btq
            print(f"Compte mis à jour : {username} ({role})")
    db.session.commit()
