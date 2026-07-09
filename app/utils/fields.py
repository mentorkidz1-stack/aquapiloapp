"""Champs WTForms adaptés à la saisie française (virgule décimale)."""
from decimal import Decimal, InvalidOperation
from wtforms import DecimalField, IntegerField


class DecimalLocalField(DecimalField):
    """DecimalField qui accepte '1,25' comme '1.25'."""

    def process_formdata(self, valuelist):
        if valuelist and valuelist[0]:
            valuelist = [valuelist[0].replace(",", ".").replace(" ", "")]
        try:
            super().process_formdata(valuelist)
        except (ValueError, InvalidOperation):
            self.data = None
            raise ValueError(self.gettext("Nombre invalide (ex. : 1,25)"))

class MontantFCFAField(IntegerField):
    """IntegerField qui accepte '1 450', '1.450', '1450' (séparateurs de milliers)."""
    def process_formdata(self, valuelist):
        if valuelist and valuelist[0]:
            nettoye = (valuelist[0].replace(" ", "").replace("\u202f", "")
                       .replace(".", "").replace(",", "").replace("FCFA", "")
                       .replace("F", "").strip())
            valuelist = [nettoye]
        super().process_formdata(valuelist)