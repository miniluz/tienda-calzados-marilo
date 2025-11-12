from django.contrib import admin
from .models import Zapato


@admin.register(Zapato)
class ZapatoAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "descripcion",
        "precio",
        "precioOferta",
        "genero",
        "estaDisponible",
        "estaDestacado",
        "fechaCreacion",
        "fechaActualizacion",
        "marca",
        "categoria",
    )
    list_filter = ("estaDisponible", "marca", "categoria")
    search_fields = ("nombre", "marca", "descripcion")
