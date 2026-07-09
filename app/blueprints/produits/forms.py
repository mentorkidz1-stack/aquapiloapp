"""Formulaires du module Produits."""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange

from app.utils.fields import DecimalLocalField


class ProduitForm(FlaskForm):
    nom = StringField("Nom du produit",
                      validators=[DataRequired(message="Champ obligatoire"),
                                  Length(max=80)])
    categorie = SelectField("Catégorie",
                            choices=[("poisson", "Poisson"), ("viande", "Viande / Volaille")],
                            validators=[DataRequired()])
    unite = SelectField("Unité (achat, stock et vente)",
                        choices=[("kg", "Au kilo (kg)"), ("piece", "À la pièce")],
                        validators=[DataRequired()])
    prix_achat = IntegerField("Prix d'achat (FCFA / unité)",
                              validators=[DataRequired(message="Champ obligatoire"),
                                          NumberRange(min=0)])
    prix_vente = IntegerField("Prix de vente (FCFA / unité)",
                              validators=[DataRequired(message="Champ obligatoire"),
                                          NumberRange(min=0)])
    seuil_alerte = DecimalLocalField("Seuil d'alerte stock", places=3,
                                     validators=[DataRequired(message="Champ obligatoire"),
                                                 NumberRange(min=0)])
    actif = BooleanField("Produit actif", default=True)
    submit = SubmitField("Enregistrer")
