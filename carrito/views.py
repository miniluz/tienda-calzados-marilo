from .models import Carrito, ZapatoCarrito
from catalog.models import Zapato
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db.utils import OperationalError
from django.views.decorators.http import require_POST


def view_carrito(request):
    try:
        if request.user.is_authenticated:
            carrito, created = Carrito.objects.get_or_create(usuario=request.user)
        else:
            # Para usuarios anónimos, usar sesión
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key
            carrito, created = Carrito.objects.get_or_create(sesion=session_key, usuario=None)
    except OperationalError:
        messages.error(request, "La base de datos no está disponible. Ejecuta las migraciones (manage.py migrate).")
        return redirect("home")  # ajusta la vista de destino si hace falta

    # Obtener los items del carrito
    zapatos_carrito = carrito.zapatos.all()

    # Calcular el total
    total = sum(
        (item.zapato.precioOferta if item.zapato.precioOferta else item.zapato.precio) * item.cantidad
        for item in zapatos_carrito
    )

    return render(
        request, "carrito/carrito_detail.html", {"carrito": carrito, "zapatos_carrito": zapatos_carrito, "total": total}
    )


@require_POST
def add_to_carrito(request, zapato_id):
    # Obtener o crear el carrito del usuario
    if request.user.is_authenticated:
        carrito, created = Carrito.objects.get_or_create(usuario=request.user)
    else:
        # Para usuarios anónimos, usar sesión
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        carrito, created = Carrito.objects.get_or_create(sesion=session_key, usuario=None)

    # Obtener el zapato
    zapato = get_object_or_404(Zapato, id=zapato_id)

    # Obtener datos del POST
    talla = request.POST.get("talla")
    cantidad = int(request.POST.get("cantidad", 1))

    if not talla:
        messages.error(request, "Debes seleccionar una talla")
        return redirect(request.META.get("HTTP_REFERER", "catalog:zapato_list"))

    talla = int(talla)

    # Verificar si ya existe este producto con esta talla en el carrito
    zapato_carrito_existente = ZapatoCarrito.objects.filter(carrito=carrito, zapato=zapato, talla=talla).first()

    if zapato_carrito_existente:
        # Incrementar cantidad
        zapato_carrito_existente.cantidad += cantidad
        zapato_carrito_existente.save()
        messages.success(request, f"Se actualizó la cantidad de {zapato.nombre} (Talla {talla}) en el carrito")
    else:
        # Crear nuevo item
        ZapatoCarrito.objects.create(carrito=carrito, zapato=zapato, cantidad=cantidad, talla=talla)
        messages.success(request, f"{zapato.nombre} (Talla {talla}) añadido al carrito con éxito")

    # Redirigir de vuelta a la página anterior o al catálogo
    return redirect(request.META.get("HTTP_REFERER", "catalog:zapato_list"))


@require_POST
def remove_from_carrito(request, zapato_carrito_id):
    zapato_carrito = get_object_or_404(ZapatoCarrito, id=zapato_carrito_id)
    nombre_zapato = zapato_carrito.zapato.nombre
    talla = zapato_carrito.talla
    zapato_carrito.delete()
    messages.success(request, f"{nombre_zapato} (Talla {talla}) eliminado del carrito con éxito")
    return redirect("carrito:view_carrito")


@require_POST
def update_quantity_carrito(request, zapato_carrito_id):
    zapato_carrito = get_object_or_404(ZapatoCarrito, id=zapato_carrito_id)
    action = request.POST.get("action")

    if action == "increase":
        zapato_carrito.cantidad += 1
        zapato_carrito.save()
        messages.success(request, f"Cantidad actualizada a {zapato_carrito.cantidad}")
    elif action == "decrease":
        if zapato_carrito.cantidad > 1:
            zapato_carrito.cantidad -= 1
            zapato_carrito.save()
            messages.success(request, f"Cantidad actualizada a {zapato_carrito.cantidad}")
        else:
            # Si la cantidad es 1, eliminar el item
            nombre_zapato = zapato_carrito.zapato.nombre
            talla = zapato_carrito.talla
            zapato_carrito.delete()
            messages.success(request, f"{nombre_zapato} (Talla {talla}) eliminado del carrito")

    return redirect("carrito:view_carrito")
