from decimal import Decimal
import os
import stripe

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
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

            # For card payments, use Stripe Checkout (two-step flow):
            # 1) Redirect user to Stripe Checkout page
            # 2) Stripe sends webhook on completion and redirects user back
            if metodo_pago == "tarjeta":
                stripe_secret = os.getenv("STRIPE_SECRET_KEY")
                if not stripe_secret:
                    messages.error(request, "Configuración de Stripe incompleta.")
                else:
                    stripe.api_key = stripe_secret
                    try:
                        # Create a single-line item for the whole order
                        session = stripe.checkout.Session.create(
                            payment_method_types=["card"],
                            line_items=[
                                {
                                    "price_data": {
                                        "currency": "eur",
                                        "product_data": {"name": f"Pedido {order.codigo_pedido}"},
                                        "unit_amount": int(order.total * 100),
                                    },
                                    "quantity": 1,
                                }
                            ],
                            mode="payment",
                            metadata={"order_id": str(order.id), "codigo_pedido": order.codigo_pedido},
                            # Include the Checkout Session id so we can retrieve status on user return
                            success_url=(
                                request.build_absolute_uri(reverse("orders:stripe_return"))
                                + "?session_id={CHECKOUT_SESSION_ID}"
                            ),
                            cancel_url=request.build_absolute_uri(reverse("orders:stripe_cancel")),
                        )

                        # Redirect the user to the Stripe Checkout page
                        return redirect(session.url)

                    except Exception as e:
                        messages.error(request, f"Error al iniciar el pago con Stripe: {e}")
            else:
                # Non-card payment: continue synchronous processing
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


class StripeWebhookView(View):
    """Endpoint to receive Stripe webhooks and mark orders as paid when appropriate."""

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

        if not webhook_secret:
            return HttpResponse("Webhook secret not configured", status=400)

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception:
            return HttpResponse(status=400)

        # Handle successful payment events
        event_type = event.get("type")
        data_obj = event.get("data", {}).get("object", {})

        order_id = None
        # metadata may be present on session or payment_intent
        metadata = data_obj.get("metadata") or {}
        order_id = metadata.get("order_id")

        if not order_id and event_type == "checkout.session.completed":
            # sometimes session object references payment_intent
            order_id = metadata.get("order_id")

        if order_id:
            try:
                order = Order.objects.get(id=int(order_id))
                if not order.pagado:
                    order.pagado = True
                    order.save()
                    # send confirmation email asynchronously if desired
                    send_order_confirmation_email(order)
            except Order.DoesNotExist:
                pass

        return JsonResponse({"received": True})


class StripeReturnView(View):
    """Handle user redirect from Stripe Checkout.

    GET: If order is already paid -> redirect to existing success page.
         Otherwise render a small validating page that reloads after 5s.

    POST: Some gateways may POST back. If Stripe posts here, verify signature
          using webhook secret and mark order paid, then redirect to success.
    """

    def get(self, request):
        order = None
        order_id = request.session.get("checkout_order_id")
        if order_id:
            try:
                order = Order.objects.get(id=order_id)
            except Order.DoesNotExist:
                order = None

        # fallback: allow codigo in querystring
        codigo = request.GET.get("codigo")
        if not order and codigo:
            try:
                order = Order.objects.get(codigo_pedido=codigo)
            except Order.DoesNotExist:
                order = None

        # If we have a session id from Stripe, check Stripe directly to avoid loop
        session_id = request.GET.get("session_id")
        stripe_secret = os.getenv("STRIPE_SECRET_KEY")
        if session_id and stripe_secret:
            try:
                stripe.api_key = stripe_secret
                checkout_session = stripe.checkout.Session.retrieve(session_id, expand=["payment_intent"])
                # retrieve metadata that we set when creating the session
                metadata = checkout_session.get("metadata") or {}
                # payment_status can be 'paid' when succeeded
                payment_status = checkout_session.get("payment_status")

                # try to find order from metadata if not available from session
                if not order:
                    order_id_meta = metadata.get("order_id")
                    if order_id_meta:
                        try:
                            order = Order.objects.get(id=int(order_id_meta))
                        except Order.DoesNotExist:
                            order = None

                # If Stripe reports the session as paid, mark the order paid and redirect to success
                if payment_status == "paid":
                    if order and not order.pagado:
                        order.pagado = True
                        order.save()
                        send_order_confirmation_email(order)
                        # clear the checkout session markers
                        if "checkout_order_id" in request.session:
                            try:
                                del request.session["checkout_order_id"]
                            except KeyError:
                                pass
                        if "checkout_descuento" in request.session:
                            try:
                                del request.session["checkout_descuento"]
                            except KeyError:
                                pass
                    if order:
                        return redirect("orders:order_success", codigo=order.codigo_pedido)

            except Exception:
                # If Stripe API call fails, fall back to existing logic (render validating)
                pass

        if order and order.pagado:
            return redirect("orders:order_success", codigo=order.codigo_pedido)

        # Not yet paid: render validating page that reloads to this view
        context = {"order": order}
        return render(request, "orders/validating.html", context)

    def post(self, request):
        # Validate that the POST comes from Stripe using webhook secret
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        if not webhook_secret or not sig_header:
            return HttpResponseForbidden("Missing or invalid signature")

        payload = request.body
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception:
            return HttpResponseForbidden("Invalid signature")

        data_obj = event.get("data", {}).get("object", {})
        metadata = data_obj.get("metadata") or {}
        order_id = metadata.get("order_id")

        if order_id:
            try:
                order = Order.objects.get(id=int(order_id))
                if not order.pagado:
                    order.pagado = True
                    order.save()
                    send_order_confirmation_email(order)
                return redirect("orders:order_success", codigo=order.codigo_pedido)
            except Order.DoesNotExist:
                return HttpResponse(status=404)

        return HttpResponse(status=400)


class StripeCancelView(View):
    """Display a simple cancellation page when Stripe cancel occurs."""

    def get(self, request):
        return render(request, "orders/payment_cancel.html")

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
