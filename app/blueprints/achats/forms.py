"""Formulaires du module Achats."""
from datetime import date

from flask_wtf import FlaskForm
from wtforms import SelectField, IntegerField, StringField, DateField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Length, Optional

from app.utils.fields import DecimalLocalField, MontantFCFAField


class AchatForm(FlaskForm):
    boutique_id = SelectField("Boutique", coerce=int,
                              validators=[DataRequired(message="Champ obligatoire")])
    produit_id = SelectField("Produit", coerce=int,
                             validators=[DataRequired(message="Champ obligatoire")])
    quantite = DecimalLocalField("Quantité (kg ou pièces, ex. 25 ou 12,5)", places=3,
                                 validators=[DataRequired(message="Champ obligatoire"),
                                             NumberRange(min=0.001)])
    prix_unitaire = MontantFCFAField("Prix d'achat (FCFA / unité)",
                                 validators=[DataRequired(message="Champ obligatoire"),
                                             NumberRange(min=1)])
    fournisseur = StringField("Fournisseur (optionnel)",
                              validators=[Optional(), Length(max=100)])
    date_achat = DateField("Date de l'achat", default=date.today,
                           validators=[DataRequired(message="Champ obligatoire")])
    submit = SubmitField("Enregistrer l'achat")
