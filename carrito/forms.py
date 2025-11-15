from django import forms
from .models import ZapatoCarrito


class ZapatoCarritoForm(forms.ModelForm):
    class Meta:
        model = ZapatoCarrito
        fields = ["zapato", "cantidad"]
