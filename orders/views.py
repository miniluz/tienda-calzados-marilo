from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from catalog.models import Zapato
from orders.emails import send_order_confirmation_email
from orders.forms import (
    BillingAddressForm,
    ContactInfoForm,
    OrderLookupForm,
    PaymentMethodForm,
    ShippingAddressForm,
)
from orders.models import Order, OrderItem
from orders.utils import (
    calculate_order_prices,
    generate_order_code,
    process_payment,
    reserve_stock,
)
from tienda_calzados_marilo.env import getEnvConfig


class CheckoutStartView(View):
    """Start checkout process - creates order and reserves stock"""

    def get(self, request):
        # TODO: Get cart items from actual cart implementation
        zapatos = Zapato.objects.filter(estaDisponible=True)[:2]

        if not zapatos.exists():
            messages.error(
                request,
                "No hay productos disponibles para comprar.",
            )
            return redirect("catalog:zapato_list")

        cart_items = []
        for i, zapato in enumerate(zapatos):
            talla_obj = zapato.tallas.filter(stock__gt=0).first()
            if talla_obj:
                cart_items.append(
                    {
                        "zapato": zapato,
                        "talla": talla_obj.talla,
                        "cantidad": 2 if i == 0 else 1,
                    }
                )

        if not cart_items:
            messages.error(
                request,
                "No hay suficiente stock para los productos seleccionados.",
            )
            return redirect("catalog:zapato_list")

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
                    raise ValueError("No se pudo generar un código de pedido único. Por favor, inténtalo de nuevo.")
                continue
            except ValueError as e:
                messages.error(request, str(e))
                return redirect("catalog:zapato_list")

        if order is None:
            raise ValueError("Error al crear el pedido.")

        try:
            for item in cart_items:
                zapato = item["zapato"]
                precio_unitario = (
                    Decimal(str(zapato.precioOferta)) if zapato.precioOferta else Decimal(str(zapato.precio))
                )
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

            env_config = getEnvConfig()
            messages.info(
                request,
                f"Tu pedido ha sido creado. Los artículos están reservados durante {env_config.get_order_reservation_minutes()} minutos. "
                f"Tienes {env_config.CHECKOUT_FORM_WINDOW_MINUTES} minutos para completar el formulario "
                f"y {env_config.PAYMENT_WINDOW_MINUTES} minutos adicionales para realizar el pago.",
            )

            return redirect("orders:checkout_contact")

        except ValueError as e:
            messages.error(request, str(e))
            return redirect("catalog:zapato_list")


class CheckoutContactView(View):
    """Step 1: Collect contact information"""

    def get(self, request):
        order = self._get_order(request)
        if not order:
            env_config = getEnvConfig()
            messages.warning(
                request,
                f"Tu pedido ha expirado. Los artículos se reservan durante {env_config.get_order_reservation_minutes()} minutos. "
                "Por favor, inicia el proceso de nuevo.",
            )
            return redirect("orders:checkout_start")

        initial = {}
        if request.user.is_authenticated:
            initial = {
                "nombre": request.user.first_name,
                "apellido": request.user.last_name,
                "email": request.user.email,
            }
            if hasattr(request.user, "customer"):
                initial["telefono"] = request.user.customer.phone_number

        form = ContactInfoForm(initial=initial)

        context = {
            "form": form,
            "order": order,
            "step": 1,
            "step_name": "Información de Contacto",
            "user_data": initial if request.user.is_authenticated else None,
        }

        return render(request, "orders/checkout_contact.html", context)

    def post(self, request):
        order = self._get_order(request)
        if not order:
            env_config = getEnvConfig()
            messages.warning(
                request,
                f"Tu pedido ha expirado. Los artículos se reservan durante {env_config.get_order_reservation_minutes()} minutos. "
                "Por favor, inicia el proceso de nuevo.",
            )
            return redirect("orders:checkout_start")

        form = ContactInfoForm(request.POST)

        if form.is_valid():
            order.nombre = form.cleaned_data["nombre"]
            order.apellido = form.cleaned_data["apellido"]
            order.email = form.cleaned_data["email"]
            order.telefono = form.cleaned_data["telefono"]
            order.save()

            return redirect("orders:checkout_shipping")

        context = {
            "form": form,
            "order": order,
            "step": 1,
            "step_name": "Información de Contacto",
        }

        return render(request, "orders/checkout_contact.html", context)

    def _get_order(self, request):
        order_id = request.session.get("checkout_order_id")
        if not order_id:
            return None
        try:
            order = Order.objects.get(id=order_id, pagado=False)

            if request.user.is_authenticated and order.usuario is not None:
                if order.usuario != request.user:
                    return None

            return order
        except Order.DoesNotExist:
            return None


class CheckoutShippingView(View):
    """Step 2: Collect shipping address"""

    def get(self, request):
        order = self._get_order(request)
        if not order:
            env_config = getEnvConfig()
            messages.warning(
                request,
                f"Tu pedido ha expirado. Los artículos se reservan durante {env_config.get_order_reservation_minutes()} minutos. "
                "Por favor, inicia el proceso de nuevo.",
            )
            return redirect("orders:checkout_start")

        initial = {}
        if request.user.is_authenticated and hasattr(request.user, "customer"):
            customer = request.user.customer
            initial = {
                "direccion_envio": customer.address,
                "ciudad_envio": customer.city,
                "codigo_postal_envio": customer.postal_code,
            }

        form = ShippingAddressForm(initial=initial)

        context = {
            "form": form,
            "order": order,
            "step": 2,
            "step_name": "Dirección de Envío",
            "user_data": initial if request.user.is_authenticated else None,
        }

        return render(request, "orders/checkout_shipping.html", context)

    def post(self, request):
        order = self._get_order(request)
        if not order:
            env_config = getEnvConfig()
            messages.warning(
                request,
                f"Tu pedido ha expirado. Los artículos se reservan durante {env_config.get_order_reservation_minutes()} minutos. "
                "Por favor, inicia el proceso de nuevo.",
            )
            return redirect("orders:checkout_start")

        form = ShippingAddressForm(request.POST)

        if form.is_valid():
            order.direccion_envio = form.cleaned_data["direccion_envio"]
            order.ciudad_envio = form.cleaned_data["ciudad_envio"]
            order.codigo_postal_envio = form.cleaned_data["codigo_postal_envio"]
            order.save()

            return redirect("orders:checkout_billing")

        context = {
            "form": form,
            "order": order,
            "step": 2,
            "step_name": "Dirección de Envío",
        }

        return render(request, "orders/checkout_shipping.html", context)

    def _get_order(self, request):
        order_id = request.session.get("checkout_order_id")
        if not order_id:
            return None
        try:
            order = Order.objects.get(id=order_id, pagado=False)

            if request.user.is_authenticated and order.usuario is not None:
                if order.usuario != request.user:
                    return None

            return order
        except Order.DoesNotExist:
            return None


class CheckoutBillingView(View):
    """Step 3: Collect billing address"""

    def get(self, request):
        order = self._get_order(request)
        if not order:
            env_config = getEnvConfig()
            messages.warning(
                request,
                f"Tu pedido ha expirado. Los artículos se reservan durante {env_config.get_order_reservation_minutes()} minutos. "
                "Por favor, inicia el proceso de nuevo.",
            )
            return redirect("orders:checkout_start")

        initial = {}
        if request.user.is_authenticated and hasattr(request.user, "customer"):
            customer = request.user.customer
            initial = {
                "direccion_facturacion": customer.address,
                "ciudad_facturacion": customer.city,
                "codigo_postal_facturacion": customer.postal_code,
            }

        form = BillingAddressForm(initial=initial)

        context = {
            "form": form,
            "order": order,
            "step": 3,
            "step_name": "Dirección de Facturación",
            "user_data": initial if request.user.is_authenticated else None,
        }

        return render(request, "orders/checkout_billing.html", context)

    def post(self, request):
        order = self._get_order(request)
        if not order:
            env_config = getEnvConfig()
            messages.warning(
                request,
                f"Tu pedido ha expirado. Los artículos se reservan durante {env_config.get_order_reservation_minutes()} minutos. "
                "Por favor, inicia el proceso de nuevo.",
            )
            return redirect("orders:checkout_start")

        form = BillingAddressForm(request.POST)

        if form.is_valid():
            order.direccion_facturacion = form.cleaned_data["direccion_facturacion"]
            order.ciudad_facturacion = form.cleaned_data["ciudad_facturacion"]
            order.codigo_postal_facturacion = form.cleaned_data["codigo_postal_facturacion"]
            order.save()

            return redirect("orders:checkout_payment")

        context = {
            "form": form,
            "order": order,
            "step": 3,
            "step_name": "Dirección de Facturación",
        }

        return render(request, "orders/checkout_billing.html", context)

    def _get_order(self, request):
        order_id = request.session.get("checkout_order_id")
        if not order_id:
            return None
        try:
            order = Order.objects.get(id=order_id, pagado=False)

            if request.user.is_authenticated and order.usuario is not None:
                if order.usuario != request.user:
                    return None

            return order
        except Order.DoesNotExist:
            return None


class CheckoutPaymentView(View):
    """Step 4: Review order and process payment"""

    def get(self, request):
        order = self._get_order(request)
        if not order:
            env_config = getEnvConfig()
            messages.warning(
                request,
                f"Tu pedido ha expirado. Los artículos se reservan durante {env_config.get_order_reservation_minutes()} minutos. "
                "Por favor, inicia el proceso de nuevo.",
            )
            return redirect("orders:checkout_start")

        env_config = getEnvConfig()
        order_age = timezone.now() - order.fecha_creacion
        if order_age.total_seconds() / 60 > env_config.CHECKOUT_FORM_WINDOW_MINUTES:
            messages.error(
                request,
                f"El tiempo para iniciar el pago ha expirado ({env_config.CHECKOUT_FORM_WINDOW_MINUTES} minutos). "
                "Los artículos han sido liberados. Por favor, inicia el proceso de nuevo.",
            )
            return redirect("orders:checkout_start")

        form = PaymentMethodForm()

        descuento = Decimal(request.session.get("checkout_descuento", "0"))

        context = {
            "form": form,
            "order": order,
            "step": 4,
            "step_name": "Pago y Revisión",
            "descuento": descuento,
        }

        return render(request, "orders/checkout_payment.html", context)

    def post(self, request):
        order = self._get_order(request)
        if not order:
            env_config = getEnvConfig()
            messages.warning(
                request,
                f"Tu pedido ha expirado. Los artículos se reservan durante {env_config.get_order_reservation_minutes()} minutos. "
                "Por favor, inicia el proceso de nuevo.",
            )
            return redirect("orders:checkout_start")

        env_config = getEnvConfig()
        order_age = timezone.now() - order.fecha_creacion
        total_window = env_config.CHECKOUT_FORM_WINDOW_MINUTES + env_config.PAYMENT_WINDOW_MINUTES
        if order_age.total_seconds() / 60 > total_window:
            messages.error(
                request,
                f"El tiempo total para completar el pago ha expirado ({total_window} minutos). "
                "Los artículos han sido liberados. Por favor, inicia el proceso de nuevo.",
            )
            return redirect("orders:checkout_start")

        form = PaymentMethodForm(request.POST)

        if form.is_valid():
            metodo_pago = form.cleaned_data["metodo_pago"]
            order.metodo_pago = metodo_pago
            order.save()

            result = process_payment(order, metodo_pago)

            if result["success"]:
                order.pagado = True
                order.save()

                email_sent = send_order_confirmation_email(order)
                if not email_sent:
                    # Do not fail the checkout if email cannot be sent; warn the user.
                    messages.warning(
                        request,
                        "El pedido se ha completado pero no se ha podido enviar el correo de confirmación. "
                        "Comprueba la configuración de correo o inténtalo más tarde.",
                    )

                if "checkout_order_id" in request.session:
                    del request.session["checkout_order_id"]
                if "checkout_descuento" in request.session:
                    del request.session["checkout_descuento"]

                messages.success(request, result["message"])
                return redirect("orders:order_success", codigo=order.codigo_pedido)
            else:
                messages.error(
                    request,
                    f"Error al procesar el pago: {result.get('message', 'Error desconocido')}",
                )

        descuento = Decimal(request.session.get("checkout_descuento", "0"))

        context = {
            "form": form,
            "order": order,
            "step": 4,
            "step_name": "Pago y Revisión",
            "descuento": descuento,
        }

        return render(request, "orders/checkout_payment.html", context)

    def _get_order(self, request):
        order_id = request.session.get("checkout_order_id")
        if not order_id:
            return None
        try:
            order = Order.objects.get(id=order_id, pagado=False)

            if request.user.is_authenticated and order.usuario is not None:
                if order.usuario != request.user:
                    return None

            return order
        except Order.DoesNotExist:
            return None


class OrderSuccessView(View):
    """Order success/confirmation page"""

    def get(self, request, codigo):
        order = get_object_or_404(Order, codigo_pedido=codigo)

        context = {
            "order": order,
        }

        return render(request, "orders/order_success.html", context)


@method_decorator(login_required, name="dispatch")
class OrderListView(View):
    """List all orders for the logged-in user"""

    def get(self, request):
        orders = Order.objects.filter(usuario=request.user, pagado=True).order_by("-fecha_creacion")

        context = {
            "orders": orders,
        }

        return render(request, "orders/order_list.html", context)


class OrderDetailView(View):
    """View details of a specific order"""

    def get(self, request, codigo):
        order = get_object_or_404(Order, codigo_pedido=codigo)

        context = {
            "order": order,
        }

        return render(request, "orders/order_detail.html", context)


class OrderLookupView(View):
    """Lookup an order by its code"""

    def get(self, request):
        form = OrderLookupForm()
        context = {
            "form": form,
        }
        return render(request, "orders/order_lookup.html", context)

    def post(self, request):
        form = OrderLookupForm(request.POST)

        if form.is_valid():
            codigo = form.cleaned_data["codigo_pedido"]

            try:
                Order.objects.get(codigo_pedido=codigo)
                return redirect("orders:order_detail", codigo=codigo)
            except Order.DoesNotExist:
                messages.error(
                    request,
                    "No se encontró ningún pedido con ese código. Por favor, verifica el código e inténtalo de nuevo.",
                )
                return render(request, "orders/order_lookup.html", {"form": form})

        context = {
            "form": form,
        }
        return render(request, "orders/order_lookup.html", context)
