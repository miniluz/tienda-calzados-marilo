import secrets
import string
from decimal import Decimal

from django.db import transaction
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
        Number of items restored
    """
    restored_count = 0

    for item in order.items.all():
        try:
            talla_zapato = TallaZapato.objects.select_for_update().get(zapato=item.zapato, talla=item.talla)
            talla_zapato.stock += item.cantidad
            talla_zapato.save()
            restored_count += 1
        except TallaZapato.DoesNotExist:
            # Talla no longer exists, skip
            continue

    return restored_count


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

    return {
        "success": True,
        "transaction_id": f"MOCK_{order.codigo_pedido}_{timezone.now().timestamp()}",
        "message": "Pago procesado correctamente",
    }


def cleanup_expired_orders():
    """
    Clean up unpaid orders that are older than the total reservation time.
    Reservation time = CHECKOUT_FORM_WINDOW_MINUTES + PAYMENT_WINDOW_MINUTES + 5 (buffer)
    Default: 10 + 5 + 5 = 20 minutes

    Restores stock and deletes the orders.

    Returns:
        Dict with 'deleted_count' and 'restored_items' keys
    """
    from orders.models import Order

    env_config = getEnvConfig()
    reservation_minutes = env_config.get_order_reservation_minutes()

    expiration_time = timezone.now() - timezone.timedelta(minutes=reservation_minutes)

    expired_orders = Order.objects.filter(pagado=False, fecha_creacion__lt=expiration_time)

    deleted_count = 0
    restored_items = 0

    for order in expired_orders:
        restored_items += restore_stock(order)
        order.delete()
        deleted_count += 1

    return {"deleted_count": deleted_count, "restored_items": restored_items}
