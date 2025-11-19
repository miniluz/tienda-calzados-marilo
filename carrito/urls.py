from django.urls import path
from . import views

app_name = "carrito"

urlpatterns = [
    path("", views.view_carrito, name="view_carrito"),
    path("add/<int:zapato_id>/", views.add_to_carrito, name="add_to_carrito"),
    path("remove/<int:zapato_carrito_id>/", views.remove_from_carrito, name="remove_from_carrito"),
    path("update/<int:zapato_carrito_id>/", views.update_quantity_carrito, name="update_quantity_carrito"),
    path("checkout/", views.checkout_from_carrito, name="checkout_from_carrito"),
]
