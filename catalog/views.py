from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.db.models import Q
from .models import Zapato
from .forms import ZapatoSearchForm


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
        min_precio = self.request.GET.get("min_precio")
        max_precio = self.request.GET.get("max_precio")

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

        if min_precio:
            try:
                qs = qs.filter(precio__gte=int(min_precio))
            except (ValueError, TypeError):
                pass

        if max_precio:
            try:
                qs = qs.filter(precio__lte=int(max_precio))
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

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.estaDisponible:
            messages.error(request, "Este producto no está disponible actualmente.")
            return redirect("catalog:zapato_list")
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


def zapato_list_api(request):
    zapatos = list(
        Zapato.objects.filter(estaDisponible=True).values(
            "id", "nombre", "precio", "precioOferta", "descripcion", "marca__nombre"
        )
    )
    return JsonResponse({"zapatos": zapatos})
