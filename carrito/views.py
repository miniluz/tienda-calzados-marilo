from .models import Carrito, ZapatoCarrito
from .forms import ZapatoCarritoForm
from django.contrib import messages
from django.shortcuts import render, redirect
from django.db.utils import OperationalError


def view_carrito(request):
    try:
        carrito, created = Carrito.objects.get_or_create(usuario=request.user)
    except OperationalError:
        messages.error(request, "La base de datos no está disponible. Ejecuta las migraciones (manage.py migrate).")
        return redirect("home")  # ajusta la vista de destino si hace falta

    return render(request, "carrito/carrito_detail.html", {"carrito": carrito})


def add_to_carrito(request, zapato_id):
    carrito, created = Carrito.objects.get_or_create(usuario=request.user)
    form = ZapatoCarritoForm(request.POST)
    if form.is_valid():
        zapato_carrito = form.save(commit=False)
        zapato_carrito.carrito = carrito
        zapato_carrito.save()
        messages.success(request, "Zapato añadido al carrito con éxito")
    else:
        messages.error(request, "Fallo al añadir el zapato al carrito")
    return redirect("view_carrito")


def remove_from_carrito(request, zapato_carrito_id):
    zapato_carrito = ZapatoCarrito.objects.get(id=zapato_carrito_id)
    zapato_carrito.delete()
    messages.success(request, "Zapato eliminado del carrito con éxito")
    return redirect("view_carrito")
