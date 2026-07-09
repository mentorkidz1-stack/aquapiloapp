"""Formulaire de saisie des pertes/avaries."""
from datetime import date
from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, DateField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Length
from app.utils.fields import DecimalLocalField


class PerteForm(FlaskForm):
    boutique_id = SelectField("Boutique", coerce=int, validators=[DataRequired()])
    produit_id = SelectField("Produit", coerce=int, validators=[DataRequired()])
    quantite = DecimalLocalField("Quantité perdue", places=3,
                                 validators=[DataRequired(message="Champ obligatoire"),
                                             NumberRange(min=0.001)])
    motif = StringField("Motif (périmé, casse, invendu...)",
                        validators=[DataRequired(message="Champ obligatoire"),
                                    Length(max=200)])
    date_perte = DateField("Date", default=date.today, validators=[DataRequired()])
    submit = SubmitField("Enregistrer la perte")
