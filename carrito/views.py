from decimal import Decimal

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.utils import OperationalError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalog.models import Zapato
from orders.models import Order, OrderItem
from orders.utils import calculate_order_prices, generate_order_code, reserve_stock
from tienda_calzados_marilo.env import getEnvConfig

from .models import Carrito, ZapatoCarrito


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

    # Verificar stock disponible para la talla seleccionada
    talla_obj = zapato.tallas.filter(talla=talla).first()
    if not talla_obj or talla_obj.stock <= 0:
        messages.error(request, f"La talla {talla} no está disponible para este producto.")
        return redirect(request.META.get("HTTP_REFERER", "catalog:zapato_list"))

    # Verificar si ya existe este producto con esta talla en el carrito
    zapato_carrito_existente = ZapatoCarrito.objects.filter(carrito=carrito, zapato=zapato, talla=talla).first()

    if zapato_carrito_existente:
        # Incrementar cantidad sin superar el stock
        nueva_cantidad = zapato_carrito_existente.cantidad + cantidad
        if nueva_cantidad > talla_obj.stock:
            nueva_cantidad = talla_obj.stock
            if zapato_carrito_existente.cantidad == talla_obj.stock:
                messages.warning(
                    request,
                    f"No se puede añadir más unidades de {zapato.nombre} (Talla {talla}).",
                )
            else:
                messages.info(
                    request,
                    f"Cantidad ajustada al máximo disponible para {zapato.nombre} (Talla {talla}).",
                )
        zapato_carrito_existente.cantidad = nueva_cantidad
        zapato_carrito_existente.save()
        messages.success(request, f"Se actualizó la cantidad de {zapato.nombre} (Talla {talla}) en el carrito")
    else:
        # Crear nuevo item sin superar el stock
        cantidad_crear = cantidad if cantidad <= talla_obj.stock else talla_obj.stock
        if cantidad_crear <= 0:
            messages.error(request, f"No hay stock disponible para {zapato.nombre} (Talla {talla}).")
            return redirect(request.META.get("HTTP_REFERER", "catalog:zapato_list"))
        if cantidad_crear < cantidad:
            messages.info(
                request,
                f"Cantidad solicitada ajustada por límite de stock para {zapato.nombre} (Talla {talla}).",
            )
        ZapatoCarrito.objects.create(carrito=carrito, zapato=zapato, cantidad=cantidad_crear, talla=talla)
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
        # Validar stock máximo para esa talla
        talla_obj = zapato_carrito.zapato.tallas.filter(talla=zapato_carrito.talla).first()
        max_stock = talla_obj.stock if talla_obj else 0
        if zapato_carrito.cantidad >= max_stock:
            messages.warning(
                request,
                f"No puedes añadir más unidades de {zapato_carrito.zapato.nombre} (Talla {zapato_carrito.talla}).",
            )
        else:
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


@require_POST
def checkout_from_carrito(request):
    """Create an order from cart items and redirect to checkout"""
    # Get the user's cart
    if request.user.is_authenticated:
        carrito = Carrito.objects.filter(usuario=request.user).first()
    else:
        session_key = request.session.session_key
        if not session_key:
            messages.error(request, "No se encontró un carrito activo.")
            return redirect("carrito:view_carrito")
        carrito = Carrito.objects.filter(sesion=session_key, usuario=None).first()

    if not carrito:
        messages.error(request, "No se encontró un carrito.")
        return redirect("carrito:view_carrito")

    # Get cart items
    zapatos_carrito = carrito.zapatos.all()

    if not zapatos_carrito.exists():
        messages.error(request, "Tu carrito está vacío.")
        return redirect("carrito:view_carrito")

    # Convert cart items to the format expected by order creation
    cart_items = []
    for item in zapatos_carrito:
        if not item.zapato.estaDisponible:
            messages.error(request, f"El producto {item.zapato.nombre} ya no está disponible.")
            return redirect("carrito:view_carrito")

        # Verify stock for this size
        talla_obj = item.zapato.tallas.filter(talla=item.talla, stock__gte=item.cantidad).first()
        if not talla_obj:
            messages.error(
                request,
                f"No hay suficiente stock para {item.zapato.nombre} (Talla {item.talla}).",
            )
            return redirect("carrito:view_carrito")

        cart_items.append(
            {
                "zapato": item.zapato,
                "talla": item.talla,
                "cantidad": item.cantidad,
            }
        )

    prices = calculate_order_prices(cart_items)

    max_retries = 5
    order = None
    for attempt in range(max_retries):
        codigo_pedido = generate_order_code()
        try:
            with transaction.atomic():
                reserve_stock(cart_items)

                order = Order.objects.create(
                    codigo_pedido=codigo_pedido,
                    usuario=request.user if request.user.is_authenticated else None,
                    subtotal=prices["subtotal"],
                    impuestos=prices["impuestos"],
                    coste_entrega=prices["coste_entrega"],
                    total=prices["total"],
                    metodo_pago="tarjeta",
                    pagado=False,
                    nombre="",
                    apellido="",
                    email="",
                    telefono="",
                    direccion_envio="",
                    ciudad_envio="",
                    codigo_postal_envio="",
                    direccion_facturacion="",
                    ciudad_facturacion="",
                    codigo_postal_facturacion="",
                )
                break
        except IntegrityError:
            if attempt == max_retries - 1:
                messages.error(
                    request,
                    "No se pudo generar un código de pedido único. Por favor, inténtalo de nuevo.",
                )
                return redirect("carrito:view_carrito")
            continue
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("carrito:view_carrito")

    if order is None:
        messages.error(request, "Error al crear el pedido.")
        return redirect("carrito:view_carrito")

    try:
        # Create order items
        for item in cart_items:
            zapato = item["zapato"]
            precio_unitario = Decimal(str(zapato.precioOferta)) if zapato.precioOferta else Decimal(str(zapato.precio))
            cantidad = item["cantidad"]

            descuento = Decimal("0.00")
            if zapato.precioOferta:
                precio_original = Decimal(str(zapato.precio))
                descuento = (precio_original - precio_unitario) * cantidad

            OrderItem.objects.create(
                pedido=order,
                zapato=zapato,
                talla=item["talla"],
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                total=precio_unitario * cantidad,
                descuento=descuento,
            )

        request.session["checkout_order_id"] = order.id
        request.session["checkout_descuento"] = str(prices["descuento"])

        # Clear the cart after creating the order
        carrito.zapatos.all().delete()

        env_config = getEnvConfig()
        messages.success(
            request,
            f"Tu pedido ha sido creado. Los artículos están reservados durante {env_config.get_order_reservation_minutes()} minutos. "
            f"Tienes {env_config.CHECKOUT_FORM_WINDOW_MINUTES} minutos para completar el formulario "
            f"y {env_config.PAYMENT_WINDOW_MINUTES} minutos adicionales para realizar el pago.",
        )

        return redirect("orders:checkout_contact")

    except ValueError as e:
        messages.error(request, str(e))
        return redirect("carrito:view_carrito")
