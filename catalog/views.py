from decimal import Decimal

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView

from orders.models import Order, OrderItem
from orders.utils import calculate_order_prices, generate_order_code, reserve_stock

from .forms import ZapatoSearchForm
from .models import Zapato


class ZapatoListView(ListView):
    model = Zapato
    template_name = "catalog/zapato_list.html"
    context_object_name = "zapatos"
    paginate_by = 12

    def get_queryset(self):
        qs = super().get_queryset().filter(estaDisponible=True)
        q = self.request.GET.get("q")
        categoria = self.request.GET.get("categoria")
        marca = self.request.GET.get("marca")
        genero = self.request.GET.get("genero")
        talla = self.request.GET.get("talla")

        if q:
            qs = qs.filter(Q(nombre__icontains=q) | Q(marca__nombre__icontains=q) | Q(descripcion__icontains=q))

        if categoria:
            try:
                qs = qs.filter(categoria__id=int(categoria))
            except (ValueError, TypeError):
                pass

        if marca:
            try:
                qs = qs.filter(marca__id=int(marca))
            except (ValueError, TypeError):
                pass

        if genero:
            qs = qs.filter(genero=genero)

        if talla:
            try:
                talla_int = int(talla)
                qs = qs.filter(tallas__talla=talla_int)
            except (ValueError, TypeError):
                pass

        # Prioritize featured products, then sort by newest
        return qs.order_by("-estaDestacado", "-fechaCreacion")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = ZapatoSearchForm(self.request.GET)
        return ctx


class ZapatoDetailView(DetailView):
    model = Zapato
    template_name = "catalog/zapato_detail.html"
    context_object_name = "zapato"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Sort tallas by size (ascending)
        ctx["tallas_ordenadas"] = self.object.tallas.all().order_by("talla")
        return ctx


def zapato_list_api(request):
    zapatos = list(
        Zapato.objects.filter(estaDisponible=True).values(
            "id", "nombre", "precio", "precioOferta", "descripcion", "marca__nombre"
        )
    )
    return JsonResponse({"zapatos": zapatos})


class BuyNowView(View):
    """View to handle direct purchase of a single product"""

    def post(self, request, pk):
        zapato = get_object_or_404(Zapato, pk=pk, estaDisponible=True)
        talla = request.POST.get("talla")

        if not talla:
            messages.error(request, "Por favor, selecciona una talla.")
            return redirect("catalog:zapato_detail", pk=pk)

        try:
            talla = int(talla)
        except (ValueError, TypeError):
            messages.error(request, "Talla inválida.")
            return redirect("catalog:zapato_detail", pk=pk)

        # Verify that the size exists and has stock
        talla_obj = zapato.tallas.filter(talla=talla, stock__gt=0).first()
        if not talla_obj:
            messages.error(request, f"La talla {talla} no está disponible para este producto.")
            return redirect("catalog:zapato_detail", pk=pk)

        # Create cart items with this single product
        cart_items = [
            {
                "zapato": zapato,
                "talla": talla,
                "cantidad": 1,
            }
        ]

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
                    return redirect("catalog:zapato_detail", pk=pk)
                continue
            except ValueError as e:
                messages.error(request, str(e))
                return redirect("catalog:zapato_detail", pk=pk)

        if order is None:
            messages.error(request, "Error al crear el pedido.")
            return redirect("catalog:zapato_detail", pk=pk)

        try:
            precio_unitario = Decimal(str(zapato.precioOferta)) if zapato.precioOferta else Decimal(str(zapato.precio))
            cantidad = 1

            descuento = Decimal("0.00")
            if zapato.precioOferta:
                precio_original = Decimal(str(zapato.precio))
                descuento = (precio_original - precio_unitario) * cantidad

            OrderItem.objects.create(
                pedido=order,
                zapato=zapato,
                talla=talla,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                total=precio_unitario * cantidad,
                descuento=descuento,
            )

            request.session["checkout_order_id"] = order.id
            request.session["checkout_descuento"] = str(prices["descuento"])

            messages.success(
                request,
                "Producto añadido al pedido. Procede con el pago para completar tu compra.",
            )

            return redirect("orders:checkout_contact")

        except ValueError as e:
            messages.error(request, str(e))
            return redirect("catalog:zapato_detail", pk=pk)
