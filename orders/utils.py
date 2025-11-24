import secrets
import string
import os
import stripe

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from catalog.models import TallaZapato
from tienda_calzados_marilo.env import getEnvConfig


def generate_order_code():
    """
    Generate a random alphanumeric order code.

    Args:
        length: Minimum length of the code (default: 10)

    Returns:
        A random alphanumeric string of the specified length
    """
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(10))


def calculate_order_prices(cart_items, delivery_cost=None, tax_rate=None):
    """
    Calculate subtotal, tax, and total for an order.

    Args:
        cart_items: List of dicts with 'zapato', 'talla', 'cantidad' keys
        delivery_cost: Override delivery cost (uses env config if None)
        tax_rate: Override tax rate (uses env config if None)

    Returns:
        Dict with 'subtotal', 'impuestos', 'coste_entrega', 'total', 'descuento'

    Raises:
        ValueError: If cart_items is empty or invalid
    """
    # Validate cart_items
    if not cart_items:
        raise ValueError("El carrito no puede estar vacío")

    if not isinstance(cart_items, list):
        raise ValueError("cart_items debe ser una lista")

    env_config = getEnvConfig()

    if delivery_cost is None:
        delivery_cost = Decimal(str(env_config.DELIVERY_COST))
    else:
        delivery_cost = Decimal(str(delivery_cost))

    if tax_rate is None:
        tax_rate = Decimal(str(env_config.TAX_RATE))
    else:
        tax_rate = Decimal(str(tax_rate))

    subtotal = Decimal("0.00")
    descuento_total = Decimal("0.00")

    for item in cart_items:
        zapato = item["zapato"]
        cantidad = item["cantidad"]

        # Use offer price if available, otherwise regular price
        if zapato.precioOferta:
            precio_unitario = Decimal(str(zapato.precioOferta))
            precio_original = Decimal(str(zapato.precio))
            descuento_total += (precio_original - precio_unitario) * cantidad
        else:
            precio_unitario = Decimal(str(zapato.precio))

        subtotal += precio_unitario * cantidad

    # Calculate tax on subtotal + delivery cost
    base_imponible = subtotal + delivery_cost
    impuestos = (base_imponible * tax_rate / Decimal("100")).quantize(Decimal("0.01"))

    # Calculate total
    total = subtotal + delivery_cost + impuestos

    return {
        "subtotal": subtotal.quantize(Decimal("0.01")),
        "impuestos": impuestos,
        "coste_entrega": delivery_cost,
        "total": total.quantize(Decimal("0.01")),
        "descuento": descuento_total.quantize(Decimal("0.01")),
    }


@transaction.atomic
def reserve_stock(cart_items):
    """
    Reserve stock for cart items by deducting from TallaZapato.stock.

    Args:
        cart_items: List of dicts with 'zapato', 'talla', 'cantidad' keys

    Returns:
        True if all items were successfully reserved

    Raises:
        ValueError: If cart is empty, invalid, or insufficient stock for any item
    """
    # Validate cart_items
    if not cart_items:
        raise ValueError("El carrito no puede estar vacío")

    if not isinstance(cart_items, list):
        raise ValueError("cart_items debe ser una lista")

    # Validate each item
    for i, item in enumerate(cart_items):
        if not isinstance(item, dict):
            raise ValueError(f"El item {i} debe ser un diccionario")

        # Check required keys
        if "zapato" not in item:
            raise ValueError(f"El item {i} no tiene la clave 'zapato'")
        if "talla" not in item:
            raise ValueError(f"El item {i} no tiene la clave 'talla'")
        if "cantidad" not in item:
            raise ValueError(f"El item {i} no tiene la clave 'cantidad'")

        # Validate cantidad
        cantidad = item["cantidad"]
        if not isinstance(cantidad, int):
            raise ValueError(f"El item {i} tiene una cantidad inválida (debe ser entero)")
        if cantidad <= 0:
            raise ValueError(f"El item {i} tiene una cantidad inválida (debe ser mayor que 0)")
        if cantidad > 10000:  # Reasonable upper limit
            raise ValueError(f"La cantidad solicitada ({cantidad}) es demasiado grande")

    # First, check if all items have sufficient stock
    for item in cart_items:
        zapato = item["zapato"]
        talla = item["talla"]
        cantidad = item["cantidad"]

        try:
            talla_zapato = TallaZapato.objects.select_for_update().get(zapato=zapato, talla=talla)
        except TallaZapato.DoesNotExist:
            raise ValueError(f"Talla {talla} no disponible para {zapato.nombre}")

        if talla_zapato.stock < cantidad:
            raise ValueError(
                f"Stock insuficiente para {zapato.nombre} talla {talla}. "
                f"Disponible: {talla_zapato.stock}, Solicitado: {cantidad}"
            )

    # If all checks pass, deduct the stock
    for item in cart_items:
        zapato = item["zapato"]
        talla = item["talla"]
        cantidad = item["cantidad"]

        talla_zapato = TallaZapato.objects.select_for_update().get(zapato=zapato, talla=talla)
        talla_zapato.stock -= cantidad
        talla_zapato.save()

    return True


@transaction.atomic
def restore_stock(order):
    """
    Restore stock for an unpaid order by adding back to TallaZapato.stock.

    Args:
        order: Order instance

    Returns:
        List of dicts with restoration details:
        [
            {
                "zapato_nombre": "Nike Air Max",
                "zapato_id": 1,
                "talla": 42,
                "cantidad": 3
            },
            ...
        ]
    """
    restored_items = []

    for item in order.items.all():
        try:
            # Use select_for_update to prevent concurrent stock modifications
            talla_zapato = TallaZapato.objects.select_for_update().get(zapato=item.zapato, talla=item.talla)
            talla_zapato.stock += item.cantidad
            talla_zapato.save()

            restored_items.append(
                {
                    "zapato_nombre": item.zapato.nombre,
                    "zapato_id": item.zapato.id,
                    "talla": item.talla,
                    "cantidad": item.cantidad,
                }
            )
        except TallaZapato.DoesNotExist:
            # Talla no longer exists, skip
            continue

    return restored_items


def process_payment(order, payment_method="tarjeta"):
    """
    Process payment for an order.

    TODO: Integrate with Stripe API or other payment gateway for actual payment processing.
    For now, this is a mock function that always succeeds.

    PAYMENT GATEWAY INTEGRATION REQUIREMENTS:
    ========================================
    When implementing a real payment gateway integration, ensure the following:

    1. TIMEOUT REQUIREMENT:
       - The payment gateway MUST enforce a timeout based on PAYMENT_WINDOW_MINUTES (default: 5 minutes)
       - This timeout should be calculated from when the user reaches the payment step
       - If payment exceeds this window, it should fail automatically

    2. TRANSACTION HANDLING:
       - All payment operations must be idempotent (safe to retry)
       - Store transaction IDs for reconciliation and refunds
       - Handle partial payments appropriately

    3. ERROR HANDLING:
       - Distinguish between:
         * Timeout errors (return {"success": False, "error": "timeout"})
         * Payment declined (return {"success": False, "error": "declined"})
         * Network/technical errors (return {"success": False, "error": "technical"})
       - Always return a dict with at minimum: {"success": bool}

    4. SECURITY:
       - Never log full credit card details
       - Use PCI-compliant payment gateway (Stripe, PayPal, Redsys, etc.)
       - Validate payment amount matches order.total before processing

    5. CONTRAREMBOLSO (Cash on Delivery):
       - No actual payment processing needed
       - Simply return success with appropriate transaction ID

    Args:
        order: Order instance with order.total, order.codigo_pedido, order.email
        payment_method: Payment method ('tarjeta' or 'contrarembolso')

    Returns:
        Dict with at minimum:
        - 'success' (bool): Whether payment was successful
        - 'transaction_id' (str): Unique transaction identifier
        - 'message' (str): User-friendly message
        Optional keys for errors:
        - 'error' (str): Error type ('timeout', 'declined', 'technical')
    """
    # For contrarembolso, no payment processing needed
    if payment_method == "contrarembolso":
        return {
            "success": True,
            "transaction_id": f"COD_{order.codigo_pedido}",
            "message": "Pagarás al recibir el pedido",
        }

    # Mock payment processing for tarjeta
    # Real implementation should call payment gateway API with:
    # - Amount: order.total
    # - Currency: EUR
    # - Description: f"Pedido {order.codigo_pedido}"
    # - Customer email: order.email
    # - Timeout: PAYMENT_WINDOW_MINUTES * 60 seconds

    stripe_secret = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_secret:
        return {
            "success": False,
            "transaction_id": None,
            "error": "config",
            "message": "Error en la configuración de pago (falta STRIPE_SECRET_KEY).",
        }

    stripe.api_key = stripe_secret

    amount_cents = int(order.total * 100)

    # Nota: no todos los recursos/versions de la librería stripe aceptan
    # el parámetro `expires_at` en PaymentIntent.create. Para evitar
    # errores por atributos faltantes en la librería (que mostraban
    # 'No exception message supplied'), creamos el intent sin
    # `expires_at` y capturamos AttributeError para dar una respuesta
    # más útil.

    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="eur",
            payment_method_types=["card"],
            payment_method="pm_card_visa",  # tarjeta de prueba de Stripe
            confirm=True,
            description=f"Pedido {order.codigo_pedido}",
            metadata={
                "order_id": str(order.id),
                "codigo_pedido": order.codigo_pedido,
            },
            receipt_email=order.email if order.email else None,
        )

    except AttributeError as e:
        # Raised when the stripe module doesn't expose the expected
        # resource (e.g. PaymentIntent) due to version/mapping issues.
        return {
            "success": False,
            "transaction_id": None,
            "error": "technical",
            "message": (
                "Error de integración con la librería Stripe: recurso no encontrado. "
                "Comprueba la versión de la librería (`pip show stripe`) y la configuración."
            ),
            "detail": str(e),
        }

    except stripe.error.CardError as e:
        return {
            "success": False,
            "transaction_id": None,
            "error": "declined",
            "message": f"Tu tarjeta ha sido rechazada: {e.user_message or 'Tarjeta no válida'}",
        }
    except (ConnectionRefusedError, OSError) as e:
        # Network-level error connecting to Stripe (connection refused,
        # DNS, blocked port, etc.). Return a clear message so the front-end
        # can inform the user and the developer can debug.
        return {
            "success": False,
            "transaction_id": None,
            "error": "network",
            "message": (
                "No se ha podido conectar con el servicio de pagos. Comprueba tu conexión a internet, "
                "firewall/proxy, y que api.stripe.com es accesible desde este equipo."
            ),
            "detail": str(e),
        }

    except stripe.error.StripeError:
        return {
            "success": False,
            "transaction_id": None,
            "error": "technical",
            "message": "Ha ocurrido un problema al procesar el pago. Inténtalo de nuevo más tarde.",
        }
    except Exception:
        return {
            "success": False,
            "transaction_id": None,
            "error": "technical",
            "message": "Error inesperado al procesar el pago.",
        }

    if intent.status == "succeeded":
        return {
            "success": True,
            "transaction_id": intent.id,
            "message": "Pago procesado correctamente con Stripe.",
        }
    else:
        return {
            "success": False,
            "transaction_id": intent.id,
            "error": "incomplete",
            "message": f"El pago no se ha completado (estado: {intent.status}).",
        }


@transaction.atomic
def validate_and_clean_cart(carrito):
    """
    Validate cart items and remove/adjust items that are no longer available or have insufficient stock.

    This function should be called:
    - When viewing the cart
    - After updating cart quantities
    - Before proceeding to checkout

    Args:
        carrito: Carrito instance

    Returns:
        List of message dicts:
        [
            {
                "type": "warning" | "error" | "info",
                "message": "User-friendly message about the issue"
            },
            ...
        ]
    """
    messages = []

    # Get all cart items - use select_related to avoid N+1 queries
    cart_items = carrito.zapatos.select_related("zapato", "zapato__marca").all()

    for item in cart_items:
        zapato = item.zapato

        # Check if product is still available
        if not zapato.estaDisponible:
            messages.append(
                {
                    "type": "warning",
                    "message": f"{zapato.nombre} ya no está disponible y ha sido eliminado del carrito.",
                }
            )
            item.delete()
            continue

        # Check if size still exists and has stock
        try:
            talla_obj = TallaZapato.objects.select_for_update().get(zapato=zapato, talla=item.talla)
        except TallaZapato.DoesNotExist:
            messages.append(
                {
                    "type": "warning",
                    "message": f"{zapato.nombre} (Talla {item.talla}) ya no está disponible y ha sido eliminado del carrito.",
                }
            )
            item.delete()
            continue

        # Check if there's sufficient stock
        if talla_obj.stock == 0:
            messages.append(
                {
                    "type": "warning",
                    "message": f"{zapato.nombre} (Talla {item.talla}) está agotado y ha sido eliminado del carrito.",
                }
            )
            item.delete()
            continue

        # Adjust quantity if stock is insufficient
        if item.cantidad > talla_obj.stock:
            old_cantidad = item.cantidad
            item.cantidad = talla_obj.stock
            item.save()
            messages.append(
                {
                    "type": "info",
                    "message": f"La cantidad de {zapato.nombre} (Talla {item.talla}) se ajustó de {old_cantidad} a {item.cantidad} debido al stock disponible.",
                }
            )

    return messages


@transaction.atomic
def create_order_from_items(cart_items, user, request):
    """
    Create an order from cart items. This unifies order creation logic between
    "Comprar ya" and "Proceed to checkout" flows.

    Args:
        cart_items: List of dicts with 'zapato', 'talla', 'cantidad' keys
        user: User instance (or None for guest)
        request: HttpRequest instance (for session management)

    Returns:
        Tuple of (order, success, error_message):
        - order: Order instance if successful, None otherwise
        - success: Boolean indicating success
        - error_message: String with error message if failed, None if successful
    """
    # Import here to avoid circular imports
    from orders.models import Order, OrderItem

    # Validate cart items
    if not cart_items:
        return None, False, "El carrito está vacío."

    # Calculate prices
    try:
        prices = calculate_order_prices(cart_items)
    except ValueError as e:
        return None, False, str(e)

    # Try to create order with retry logic for unique code
    max_retries = 5
    order = None

    for attempt in range(max_retries):
        codigo_pedido = generate_order_code()
        try:
            with transaction.atomic():
                # Reserve stock first (will raise ValueError if insufficient)
                reserve_stock(cart_items)

                # Create order
                order = Order.objects.create(
                    codigo_pedido=codigo_pedido,
                    usuario=user if user.is_authenticated else None,
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
            # Code collision - retry
            if attempt == max_retries - 1:
                return None, False, "No se pudo generar un código de pedido único. Por favor, inténtalo de nuevo."
            continue
        except ValueError as e:
            # Stock reservation failed
            return None, False, str(e)

    if order is None:
        return None, False, "Error al crear el pedido."

    # Create order items
    try:
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

        # Store order info in session
        request.session["checkout_order_id"] = order.id
        request.session["checkout_descuento"] = str(prices["descuento"])

        return order, True, None

    except Exception as e:
        # Unexpected error - order was created but items failed
        # Stock is already reserved, so we should not restore it here
        # The cleanup job will handle this if payment isn't completed
        return order, False, f"Error al crear los items del pedido: {str(e)}"


@transaction.atomic
def cleanup_expired_orders():
    """
    Clean up unpaid orders that are older than the total reservation time.
    Reservation time = CHECKOUT_FORM_WINDOW_MINUTES + PAYMENT_WINDOW_MINUTES + 5 (buffer)
    Default: 10 + 5 + 5 = 20 minutes

    Restores stock and deletes the orders.

    Uses select_for_update() to prevent concurrent cleanups from double-restoring stock.
    If another cleanup is in progress, this will block until it completes.

    Returns:
        Dict with:
        - 'deleted_count': Number of orders deleted
        - 'restored_items': Total number of order items restored
        - 'stock_details': List of dicts grouped by shoe with nested size details
          [
              {
                  "zapato_id": 1,
                  "zapato_nombre": "Nike Air Max",
                  "tallas": [
                      {"talla": 38, "cantidad": 4},
                      {"talla": 40, "cantidad": 1}
                  ]
              },
              ...
          ]
    """
    from collections import defaultdict
    from orders.models import Order

    env_config = getEnvConfig()
    reservation_minutes = env_config.get_order_reservation_minutes()

    expiration_time = timezone.now() - timezone.timedelta(minutes=reservation_minutes)

    # Lock expired orders to prevent concurrent cleanup from double-restoring stock
    expired_orders = Order.objects.select_for_update().filter(pagado=False, fecha_creacion__lt=expiration_time)

    deleted_count = 0
    restored_items_count = 0
    # Aggregate stock restorations by zapato_id -> {talla -> cantidad}
    shoe_aggregation = defaultdict(lambda: {"nombre": "", "tallas": defaultdict(int)})

    for order in expired_orders:
        restored_items = restore_stock(order)
        restored_items_count += len(restored_items)

        # Aggregate quantities by shoe -> talla
        for item in restored_items:
            zapato_id = item["zapato_id"]
            shoe_aggregation[zapato_id]["nombre"] = item["zapato_nombre"]
            shoe_aggregation[zapato_id]["tallas"][item["talla"]] += item["cantidad"]

        order.delete()
        deleted_count += 1

    # Convert aggregation to list of dicts with sorted tallas
    stock_details = []
    for zapato_id in sorted(shoe_aggregation.keys()):
        shoe_data = shoe_aggregation[zapato_id]
        tallas_list = [
            {"talla": talla, "cantidad": cantidad} for talla, cantidad in sorted(shoe_data["tallas"].items())
        ]
        stock_details.append({"zapato_id": zapato_id, "zapato_nombre": shoe_data["nombre"], "tallas": tallas_list})

    return {"deleted_count": deleted_count, "restored_items": restored_items_count, "stock_details": stock_details}
