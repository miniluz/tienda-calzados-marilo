from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView

from orders.utils import create_order_from_items
from tienda_calzados_marilo.env import getEnvConfig

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

        # Use the unified order creation utility
        order, success, error_message = create_order_from_items(cart_items, request.user, request)

        if not success:
            messages.error(request, error_message)
            return redirect("catalog:zapato_detail", pk=pk)

        env_config = getEnvConfig()
        messages.success(
            request,
            f"Producto añadido al pedido. Los artículos están reservados durante {env_config.get_order_reservation_minutes()} minutos. "
            "Procede con el pago para completar tu compra.",
        )

        return redirect("orders:checkout_contact")
