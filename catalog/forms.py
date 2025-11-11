from django import forms


class ZapatoSearchForm(forms.Form):
    q = forms.CharField(label="Buscar", required=False)
    min_precio = forms.IntegerField(required=False)
    max_precio = forms.IntegerField(required=False)
    talla = forms.IntegerField(required=False)
