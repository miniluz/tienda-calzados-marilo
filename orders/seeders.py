"""
Orders seeder - creates sample orders for existing customers

This module is automatically discovered and executed by: python manage.py seed

IMPORTANT: Run after catalog and customer seeders (uses existing users and products)
"""

import random
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone

from catalog.models import Zapato
from customer.models import Customer
from orders.models import Order, OrderItem
from tienda_calzados_marilo.env import getEnvConfig

# Seeder priority (lower = runs first)
PRIORITY = 30


def seed():
    """Main seeding function for the orders app"""

    random.seed(42)

    print("  Clearing existing order data...")
    OrderItem.objects.all().delete()
    Order.objects.all().delete()
    print("  Order database cleared")

    env_config = getEnvConfig()
    tax_rate = Decimal(str(env_config.TAX_RATE)) / 100
    delivery_cost = Decimal(str(env_config.DELIVERY_COST))

    customer_users = list(User.objects.filter(is_staff=False, is_superuser=False).select_related("customer"))

    if not customer_users:
        print("  ⚠️  No customers found!")
        print("  Please run customer seeder first")
        return

    available_zapatos = list(
        Zapato.objects.filter(estaDisponible=True, tallas__stock__gt=0).distinct().prefetch_related("tallas")
    )

    if not available_zapatos:
        print("  ⚠️  No available shoes with stock found!")
        print("  Please run catalog seeder first")
        return

    print(f"  Found {len(customer_users)} customers and {len(available_zapatos)} available shoes")

    NUM_EXPIRED_ORDERS = 8
    MIN_ORDERS_PER_CUSTOMER = 1
    MAX_ORDERS_PER_CUSTOMER = 5

    cities = [
        ("Madrid", "28"),
        ("Barcelona", "08"),
        ("Valencia", "46"),
        ("Sevilla", "41"),
        ("Zaragoza", "50"),
        ("Málaga", "29"),
        ("Murcia", "30"),
        ("Palma", "07"),
        ("Bilbao", "48"),
        ("Alicante", "03"),
    ]

    order_counter = 1
    created_orders = []

    for user in customer_users:
        num_orders = random.randint(MIN_ORDERS_PER_CUSTOMER, MAX_ORDERS_PER_CUSTOMER)

        for _ in range(num_orders):
            codigo_pedido = f"SEED{order_counter:04d}"
            order_counter += 1

            try:
                customer = user.customer
                phone = customer.phone_number
                address = customer.address
                city = customer.city
                postal_code = customer.postal_code
            except Customer.DoesNotExist:
                phone = f"6{random.randint(10000000, 99999999)}"
                city_info = random.choice(cities)
                city = city_info[0]
                postal_code = f"{city_info[1]}{random.randint(100, 999):03d}"
                address = f"Calle de Ejemplo, {random.randint(1, 100)}"

            if random.random() < 0.1:
                billing_city_info = random.choice(cities)
                billing_city = billing_city_info[0]
                billing_postal = f"{billing_city_info[1]}{random.randint(100, 999):03d}"
                billing_address = f"Avenida Facturación, {random.randint(1, 100)}"
            else:
                billing_city = city
                billing_postal = postal_code
                billing_address = address

            estado_weights = [
                ("por_enviar", 0.3),
                ("en_envio", 0.4),
                ("recibido", 0.3),
            ]
            estado = random.choices([s[0] for s in estado_weights], weights=[s[1] for s in estado_weights])[0]

            metodo_pago = random.choice(["contrarembolso", "tarjeta"])

            if metodo_pago == "tarjeta":
                pagado = random.choice([True, True, True, False])
            else:
                pagado = random.choice([True, False, False])

            num_items = random.randint(1, 4)
            selected_items = []

            for _ in range(num_items):
                zapato = random.choice(available_zapatos)
                available_tallas = list(zapato.tallas.filter(stock__gt=0))

                if not available_tallas:
                    continue

                talla_zapato = random.choice(available_tallas)
                cantidad = random.randint(1, min(3, talla_zapato.stock))

                precio_unitario = zapato.precioOferta if zapato.precioOferta else zapato.precio

                if zapato.precioOferta:
                    descuento_unitario = zapato.precio - zapato.precioOferta
                    descuento_total = descuento_unitario * cantidad
                else:
                    descuento_total = Decimal("0.00")

                total_item = precio_unitario * cantidad

                selected_items.append(
                    {
                        "zapato": zapato,
                        "talla": talla_zapato.talla,
                        "cantidad": cantidad,
                        "precio_unitario": precio_unitario,
                        "total": total_item,
                        "descuento": descuento_total,
                    }
                )

            if not selected_items:
                continue

            subtotal = sum(item["total"] for item in selected_items)
            impuestos = (subtotal * tax_rate).quantize(Decimal("0.01"))
            total = subtotal + impuestos + delivery_cost

            order = Order.objects.create(
                codigo_pedido=codigo_pedido,
                usuario=user,
                estado=estado,
                metodo_pago=metodo_pago,
                pagado=pagado,
                subtotal=subtotal,
                impuestos=impuestos,
                coste_entrega=delivery_cost,
                total=total,
                nombre=user.first_name,
                apellido=user.last_name,
                email=user.email,
                telefono=phone,
                direccion_envio=address,
                ciudad_envio=city,
                codigo_postal_envio=postal_code,
                direccion_facturacion=billing_address,
                ciudad_facturacion=billing_city,
                codigo_postal_facturacion=billing_postal,
            )

            for item_data in selected_items:
                OrderItem.objects.create(
                    pedido=order,
                    zapato=item_data["zapato"],
                    talla=item_data["talla"],
                    cantidad=item_data["cantidad"],
                    precio_unitario=item_data["precio_unitario"],
                    total=item_data["total"],
                    descuento=item_data["descuento"],
                )

            days_old = random.randint(0, 30)
            hours_old = random.randint(0, 23)
            minutes_old = random.randint(0, 59)
            order.fecha_creacion = timezone.now() - timezone.timedelta(
                days=days_old, hours=hours_old, minutes=minutes_old
            )
            order.save()

            created_orders.append(order)

    print(f"  Created {len(created_orders)} orders")

    print(f"  Creating {NUM_EXPIRED_ORDERS} expired unpaid orders for cleanup testing...")
    expired_count = 0

    for i in range(NUM_EXPIRED_ORDERS):
        user = random.choice(customer_users)
        codigo_pedido = f"EXP{order_counter:04d}"
        order_counter += 1

        try:
            customer = user.customer
            phone = customer.phone_number
            address = customer.address
            city = customer.city
            postal_code = customer.postal_code
        except Customer.DoesNotExist:
            phone = f"6{random.randint(10000000, 99999999)}"
            city_info = random.choice(cities)
            city = city_info[0]
            postal_code = f"{city_info[1]}{random.randint(100, 999):03d}"
            address = f"Calle de Ejemplo, {random.randint(1, 100)}"

        num_items = random.randint(1, 2)
        selected_items = []

        for _ in range(num_items):
            zapato = random.choice(available_zapatos)
            available_tallas = list(zapato.tallas.filter(stock__gt=0))

            if not available_tallas:
                continue

            talla_zapato = random.choice(available_tallas)
            cantidad = 1
            precio_unitario = zapato.precioOferta if zapato.precioOferta else zapato.precio
            total_item = precio_unitario * cantidad

            selected_items.append(
                {
                    "zapato": zapato,
                    "talla": talla_zapato.talla,
                    "cantidad": cantidad,
                    "precio_unitario": precio_unitario,
                    "total": total_item,
                    "descuento": Decimal("0.00"),
                }
            )

        if not selected_items:
            continue

        subtotal = sum(item["total"] for item in selected_items)
        impuestos = (subtotal * tax_rate).quantize(Decimal("0.01"))
        total = subtotal + impuestos + delivery_cost

        order = Order.objects.create(
            codigo_pedido=codigo_pedido,
            usuario=user,
            estado="por_enviar",
            metodo_pago=random.choice(["contrarembolso", "tarjeta"]),
            pagado=False,
            subtotal=subtotal,
            impuestos=impuestos,
            coste_entrega=delivery_cost,
            total=total,
            nombre=user.first_name,
            apellido=user.last_name,
            email=user.email,
            telefono=phone,
            direccion_envio=address,
            ciudad_envio=city,
            codigo_postal_envio=postal_code,
            direccion_facturacion=address,
            ciudad_facturacion=city,
            codigo_postal_facturacion=postal_code,
        )

        for item_data in selected_items:
            OrderItem.objects.create(
                pedido=order,
                zapato=item_data["zapato"],
                talla=item_data["talla"],
                cantidad=item_data["cantidad"],
                precio_unitario=item_data["precio_unitario"],
                total=item_data["total"],
                descuento=item_data["descuento"],
            )

        minutes_old = random.randint(26, 120)
        order.fecha_creacion = timezone.now() - timezone.timedelta(minutes=minutes_old)
        order.save()

        expired_count += 1

    print(f"  Created {expired_count} expired unpaid orders")
    print(f"  Total orders created: {len(created_orders) + expired_count}")
    print("  Seeding complete!")
