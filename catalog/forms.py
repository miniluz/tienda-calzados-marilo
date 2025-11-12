from django import forms

from .models import Categoria, Marca


class ZapatoSearchForm(forms.Form):
    q = forms.CharField(label="Buscar", required=False)
    categoria = forms.ModelChoiceField(
        queryset=Categoria.objects.all(),
        required=False,
        empty_label="Todas las categorías",
        label="Categoría",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    marca = forms.ModelChoiceField(
        queryset=Marca.objects.all(),
        required=False,
        empty_label="Todas las marcas",
        label="Marca",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    genero = forms.ChoiceField(
        choices=[("", "Todos los géneros")]
        + [
            ("Hombre", "Hombre"),
            ("Mujer", "Mujer"),
            ("Niño", "Niño"),
            ("Niña", "Niña"),
            ("Unisex", "Unisex"),
        ],
        required=False,
        label="Género",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    talla = forms.IntegerField(required=False)
