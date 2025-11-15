from django.urls import path
from . import views

app_name = "carrito"

urlpatterns = [
    path("", views.view_carrito, name="view_carrito"),
    path("add/", views.add_to_carrito, name="add_to_carrito"),
    path("remove/<int:zapato_carrito_id>/", views.remove_from_carrito, name="remove_from_carrito"),
]
