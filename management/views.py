from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from django.contrib.auth.models import User
from django.db import transaction
from django.views import View
from django.db.models import Sum, F, Q
from customer.models import Customer
from catalog.models import Zapato, Marca, Categoria, TallaZapato
from .forms import (
    CustomerEditForm,
    CustomerFilterForm,
    AdminCreateForm,
    AdminEditForm,
    ZapatoForm,
    MarcaForm,
    CategoriaForm,
    OrderFilterForm,
)


def staff_required(function=None):
    """Decorator that checks if the user is staff, redirecting to custom login if not authenticated"""
    actual_decorator = user_passes_test(lambda u: u.is_staff, login_url="login", redirect_field_name="next")
    if function:
        return actual_decorator(function)
    return actual_decorator


@method_decorator(staff_required, name="dispatch")
class AdminDashboardView(View):
    template_name = "management/dashboard.html"

    def get(self, request):
        customer_count = Customer.objects.count()
        admin_count = User.objects.filter(is_staff=True).count()
        zapato_count = Zapato.objects.count()
        marca_count = Marca.objects.count()
        categoria_count = Categoria.objects.count()

        return render(
            request,
            self.template_name,
            {
                "customer_count": customer_count,
                "admin_count": admin_count,
                "zapato_count": zapato_count,
                "marca_count": marca_count,
                "categoria_count": categoria_count,
            },
        )


@method_decorator(staff_required, name="dispatch")
class CustomerListView(View):
    template_name = "management/customer_list.html"

    def get(self, request):
        customers = Customer.objects.select_related("user").all()

        # Initialize filter form with GET data
        filter_form = CustomerFilterForm(request.GET)

        if filter_form.is_valid():
            # Filter by nombre (searches in first_name and last_name)
            nombre = filter_form.cleaned_data.get("nombre")
            if nombre:
                customers = customers.filter(
                    Q(user__first_name__icontains=nombre) | Q(user__last_name__icontains=nombre)
                )

            # Filter by email
            email = filter_form.cleaned_data.get("email")
            if email:
                customers = customers.filter(user__email__icontains=email)

            # Filter by telefono (exact match)
            telefono = filter_form.cleaned_data.get("telefono")
            if telefono:
                customers = customers.filter(phone_number__icontains=telefono)

        # Always order by creation date (newest first)
        customers = customers.order_by("-created_at")

        return render(request, self.template_name, {"customers": customers, "filter_form": filter_form})


@method_decorator(staff_required, name="dispatch")
class CustomerDetailView(View):
    template_name = "management/customer_detail.html"

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        try:
            customer = user.customer
        except Customer.DoesNotExist:
            messages.error(request, "Este usuario no es un cliente.")
            return redirect("customer_list")

        return render(request, self.template_name, {"user": user, "customer": customer})


@method_decorator(staff_required, name="dispatch")
class CustomerEditView(View):
    template_name = "management/customer_edit.html"

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        try:
            customer = user.customer
        except Customer.DoesNotExist:
            messages.error(request, "Este usuario no es un cliente.")
            return redirect("customer_list")

        form = CustomerEditForm(
            user_id=user.id,
            initial={
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone_number": customer.phone_number,
                "address": customer.address,
                "city": customer.city,
                "postal_code": customer.postal_code,
            },
        )

        return render(request, self.template_name, {"form": form, "user": user, "customer": customer})

    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        try:
            customer = user.customer
        except Customer.DoesNotExist:
            messages.error(request, "Este usuario no es un cliente.")
            return redirect("customer_list")

        form = CustomerEditForm(request.POST, user_id=user.id)

        if form.is_valid():
            try:
                with transaction.atomic():
                    old_email = user.email
                    new_email = form.cleaned_data["email"]

                    user.email = new_email
                    user.first_name = form.cleaned_data["first_name"]
                    user.last_name = form.cleaned_data["last_name"]

                    if old_email != new_email:
                        user.username = new_email

                    user.save()

                    customer.phone_number = form.cleaned_data["phone_number"]
                    customer.address = form.cleaned_data["address"]
                    customer.city = form.cleaned_data["city"]
                    customer.postal_code = form.cleaned_data["postal_code"]
                    customer.save()

                messages.success(request, "Cliente actualizado correctamente.")
                return redirect("customer_detail", user_id=user.id)

            except Exception:
                messages.error(request, "Ha ocurrido un error al actualizar el cliente.")

        return render(request, self.template_name, {"form": form, "user": user, "customer": customer})


@method_decorator(staff_required, name="dispatch")
class CustomerDeleteView(View):
    template_name = "management/customer_confirm_delete.html"

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        try:
            customer = user.customer
        except Customer.DoesNotExist:
            messages.error(request, "Este usuario no es un cliente.")
            return redirect("customer_list")

        return render(request, self.template_name, {"user": user, "customer": customer})

    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        try:
            user.customer
        except Customer.DoesNotExist:
            messages.error(request, "Este usuario no es un cliente.")
            return redirect("customer_list")

        user_name = f"{user.first_name} {user.last_name}"
        user.delete()
        messages.success(request, f"Cliente {user_name} eliminado correctamente.")
        return redirect("customer_list")


@method_decorator(staff_required, name="dispatch")
class AdminListView(View):
    template_name = "management/admin_list.html"

    def get(self, request):
        admins = User.objects.filter(is_staff=True).order_by("-date_joined")
        return render(request, self.template_name, {"admins": admins})


@method_decorator(staff_required, name="dispatch")
class AdminCreateView(View):
    template_name = "management/admin_create.html"

    def get(self, request):
        form = AdminCreateForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = AdminCreateForm(request.POST)

        if form.is_valid():
            try:
                user = form.save()
                messages.success(request, f"Administrador {user.first_name} {user.last_name} creado correctamente.")
                return redirect("admin_list")
            except Exception:
                messages.error(request, "Ha ocurrido un error al crear el administrador.")

        return render(request, self.template_name, {"form": form})


@method_decorator(staff_required, name="dispatch")
class AdminEditView(View):
    template_name = "management/admin_edit.html"

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id, is_staff=True)

        form = AdminEditForm(
            user_id=user.id,
            initial={
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        )

        return render(request, self.template_name, {"form": form, "admin_user": user})

    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id, is_staff=True)
        form = AdminEditForm(request.POST, user_id=user.id)

        if form.is_valid():
            try:
                with transaction.atomic():
                    old_email = user.email
                    new_email = form.cleaned_data["email"]

                    user.email = new_email
                    user.first_name = form.cleaned_data["first_name"]
                    user.last_name = form.cleaned_data["last_name"]

                    if old_email != new_email:
                        user.username = new_email

                    user.save()

                messages.success(request, "Administrador actualizado correctamente.")
                return redirect("admin_list")

            except Exception:
                messages.error(request, "Ha ocurrido un error al actualizar el administrador.")

        return render(request, self.template_name, {"form": form, "admin_user": user})


@method_decorator(staff_required, name="dispatch")
class AdminDeleteView(View):
    template_name = "management/admin_confirm_delete.html"

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id, is_staff=True)

        if user.id == request.user.id:
            messages.error(request, "No puedes eliminar tu propia cuenta de administrador.")
            return redirect("admin_list")

        return render(request, self.template_name, {"admin_user": user})

    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id, is_staff=True)

        if user.id == request.user.id:
            messages.error(request, "No puedes eliminar tu propia cuenta de administrador.")
            return redirect("admin_list")

        user_name = f"{user.first_name} {user.last_name}"
        user.delete()
        messages.success(request, f"Administrador {user_name} eliminado correctamente.")
        return redirect("admin_list")


# ==================== ZAPATO (SHOE) MANAGEMENT VIEWS ====================


@method_decorator(staff_required, name="dispatch")
class ZapatoAdminListView(View):
    """Stock overview - shows all shoes with their stock levels"""

    template_name = "management/zapato_list.html"

    def get(self, request):
        zapatos = Zapato.objects.select_related("marca", "categoria").prefetch_related("tallas").all()

        # Calculate total stock for each zapato
        for zapato in zapatos:
            zapato.total_stock = zapato.tallas.aggregate(total=Sum("stock"))["total"] or 0

        return render(request, self.template_name, {"zapatos": zapatos})


@method_decorator(staff_required, name="dispatch")
class ZapatoAdminDetailView(View):
    """Edit shoe details and manage image"""

    template_name = "management/zapato_detail.html"

    def get(self, request, zapato_id):
        zapato = get_object_or_404(Zapato, pk=zapato_id)
        form = ZapatoForm(instance=zapato)

        # Calculate total stock
        total_stock = zapato.tallas.aggregate(total=Sum("stock"))["total"] or 0

        return render(
            request,
            self.template_name,
            {
                "zapato": zapato,
                "form": form,
                "total_stock": total_stock,
            },
        )

    def post(self, request, zapato_id):
        zapato = get_object_or_404(Zapato, pk=zapato_id)
        form = ZapatoForm(request.POST, request.FILES, instance=zapato)

        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Zapato actualizado correctamente.")
                return redirect("zapato_admin_detail", zapato_id=zapato.id)
            except Exception:
                messages.error(request, "Ha ocurrido un error al actualizar el zapato.")

        total_stock = zapato.tallas.aggregate(total=Sum("stock"))["total"] or 0

        return render(
            request,
            self.template_name,
            {
                "zapato": zapato,
                "form": form,
                "total_stock": total_stock,
            },
        )


@method_decorator(staff_required, name="dispatch")
class ZapatoAdminCreateView(View):
    """Create a new shoe"""

    template_name = "management/zapato_create.html"

    def get(self, request):
        form = ZapatoForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = ZapatoForm(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    zapato = form.save()

                    # Create all sizes (34-49) with 0 stock by default
                    for talla in range(34, 50):
                        TallaZapato.objects.create(zapato=zapato, talla=talla, stock=0)

                messages.success(request, f"Zapato {zapato.nombre} creado correctamente.")
                return redirect("zapato_admin_detail", zapato_id=zapato.id)
            except Exception:
                messages.error(request, "Ha ocurrido un error al crear el zapato.")

        return render(request, self.template_name, {"form": form})


@method_decorator(staff_required, name="dispatch")
class ZapatoStockEditView(View):
    """Edit stock levels for all sizes of a shoe - prevents data races"""

    template_name = "management/zapato_stock.html"

    def get(self, request, zapato_id):
        zapato = get_object_or_404(Zapato, pk=zapato_id)
        tallas = zapato.tallas.all().order_by("talla")

        return render(request, self.template_name, {"zapato": zapato, "tallas": tallas})

    def post(self, request, zapato_id):
        zapato = get_object_or_404(Zapato, pk=zapato_id)
        action = request.POST.get("action")

        try:
            if action == "add":
                # Add stock to a specific size
                talla_id = request.POST.get("talla_id")
                amount = int(request.POST.get("amount", 1))
                talla = get_object_or_404(TallaZapato, pk=talla_id, zapato=zapato)

                # Use F() expression to prevent race conditions
                talla.stock = F("stock") + amount
                talla.save()
                talla.refresh_from_db()  # Reload to get actual value

                messages.success(request, f"Se añadieron {amount} unidades a la talla {talla.talla}.")

            elif action == "remove":
                # Remove stock from a specific size
                talla_id = request.POST.get("talla_id")
                amount = int(request.POST.get("amount", 1))
                talla = get_object_or_404(TallaZapato, pk=talla_id, zapato=zapato)

                # Ensure we don't go negative
                if talla.stock >= amount:
                    talla.stock = F("stock") - amount
                    talla.save()
                    talla.refresh_from_db()
                    messages.success(request, f"Se quitaron {amount} unidades de la talla {talla.talla}.")
                else:
                    messages.error(request, f"No hay suficiente stock. Stock actual: {talla.stock}")

            elif action == "delete":
                # Delete a size
                talla_id = request.POST.get("talla_id")
                talla = get_object_or_404(TallaZapato, pk=talla_id, zapato=zapato)
                talla_num = talla.talla
                talla.delete()
                messages.success(request, f"Talla {talla_num} eliminada correctamente.")

            elif action == "create":
                # Create a new size
                talla_num = int(request.POST.get("talla"))
                stock_inicial = int(request.POST.get("stock_inicial", 0))

                # Check if size already exists
                if zapato.tallas.filter(talla=talla_num).exists():
                    messages.error(request, f"La talla {talla_num} ya existe para este zapato.")
                else:
                    TallaZapato.objects.create(zapato=zapato, talla=talla_num, stock=stock_inicial)
                    messages.success(request, f"Talla {talla_num} creada con {stock_inicial} unidades.")

            else:
                messages.error(request, "Acción no válida.")

        except ValueError:
            messages.error(request, "Valores inválidos en el formulario.")
        except Exception as e:
            messages.error(request, f"Ha ocurrido un error: {str(e)}")

        # Redirect to avoid form resubmission
        return redirect("zapato_stock_edit", zapato_id=zapato.id)


@method_decorator(staff_required, name="dispatch")
class ZapatoAdminDeleteView(View):
    """Delete a shoe"""

    template_name = "management/zapato_confirm_delete.html"

    def get(self, request, zapato_id):
        zapato = get_object_or_404(Zapato, pk=zapato_id)
        return render(request, self.template_name, {"zapato": zapato})

    def post(self, request, zapato_id):
        zapato = get_object_or_404(Zapato, pk=zapato_id)
        zapato_nombre = zapato.nombre
        zapato.delete()
        messages.success(request, f"Zapato {zapato_nombre} eliminado correctamente.")
        return redirect("zapato_admin_list")


# ==================== MARCA (BRAND) MANAGEMENT VIEWS ====================


@method_decorator(staff_required, name="dispatch")
class MarcaListView(View):
    """List all brands"""

    template_name = "management/marca_list.html"

    def get(self, request):
        marcas = Marca.objects.all().order_by("nombre")
        return render(request, self.template_name, {"marcas": marcas})


@method_decorator(staff_required, name="dispatch")
class MarcaCreateView(View):
    """Create a new brand"""

    template_name = "management/marca_create.html"

    def get(self, request):
        form = MarcaForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = MarcaForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                marca = form.save()
                messages.success(request, f"Marca {marca.nombre} creada correctamente.")
                return redirect("marca_list")
            except Exception:
                messages.error(request, "Ha ocurrido un error al crear la marca.")

        return render(request, self.template_name, {"form": form})


@method_decorator(staff_required, name="dispatch")
class MarcaEditView(View):
    """Edit a brand"""

    template_name = "management/marca_edit.html"

    def get(self, request, marca_id):
        marca = get_object_or_404(Marca, pk=marca_id)
        form = MarcaForm(instance=marca)
        return render(request, self.template_name, {"marca": marca, "form": form})

    def post(self, request, marca_id):
        marca = get_object_or_404(Marca, pk=marca_id)
        form = MarcaForm(request.POST, request.FILES, instance=marca)

        if form.is_valid():
            try:
                marca = form.save()
                messages.success(request, f"Marca {marca.nombre} actualizada correctamente.")
                return redirect("marca_list")
            except Exception:
                messages.error(request, "Ha ocurrido un error al actualizar la marca.")

        return render(request, self.template_name, {"marca": marca, "form": form})


@method_decorator(staff_required, name="dispatch")
class MarcaDeleteView(View):
    """Delete a brand"""

    template_name = "management/marca_confirm_delete.html"

    def get(self, request, marca_id):
        marca = get_object_or_404(Marca, pk=marca_id)

        # Check if marca has associated zapatos
        zapatos_count = marca.zapatos.count()

        return render(request, self.template_name, {"marca": marca, "zapatos_count": zapatos_count})

    def post(self, request, marca_id):
        marca = get_object_or_404(Marca, pk=marca_id)

        # Check if marca has associated zapatos
        if marca.zapatos.exists():
            messages.error(request, "No se puede eliminar la marca porque tiene zapatos asociados.")
            return redirect("marca_list")

        marca_nombre = marca.nombre
        marca.delete()
        messages.success(request, f"Marca {marca_nombre} eliminada correctamente.")
        return redirect("marca_list")


# ==================== CATEGORIA (CATEGORY) MANAGEMENT VIEWS ====================


@method_decorator(staff_required, name="dispatch")
class CategoriaListView(View):
    """List all categories"""

    template_name = "management/categoria_list.html"

    def get(self, request):
        categorias = Categoria.objects.all().order_by("nombre")
        return render(request, self.template_name, {"categorias": categorias})


@method_decorator(staff_required, name="dispatch")
class CategoriaCreateView(View):
    """Create a new category"""

    template_name = "management/categoria_create.html"

    def get(self, request):
        form = CategoriaForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = CategoriaForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                categoria = form.save()
                messages.success(request, f"Categoría {categoria.nombre} creada correctamente.")
                return redirect("categoria_list")
            except Exception:
                messages.error(request, "Ha ocurrido un error al crear la categoría.")

        return render(request, self.template_name, {"form": form})


@method_decorator(staff_required, name="dispatch")
class CategoriaEditView(View):
    """Edit a category"""

    template_name = "management/categoria_edit.html"

    def get(self, request, categoria_id):
        categoria = get_object_or_404(Categoria, pk=categoria_id)
        form = CategoriaForm(instance=categoria)
        return render(request, self.template_name, {"categoria": categoria, "form": form})

    def post(self, request, categoria_id):
        categoria = get_object_or_404(Categoria, pk=categoria_id)
        form = CategoriaForm(request.POST, request.FILES, instance=categoria)

        if form.is_valid():
            try:
                categoria = form.save()
                messages.success(request, f"Categoría {categoria.nombre} actualizada correctamente.")
                return redirect("categoria_list")
            except Exception:
                messages.error(request, "Ha ocurrido un error al actualizar la categoría.")

        return render(request, self.template_name, {"categoria": categoria, "form": form})


@method_decorator(staff_required, name="dispatch")
class CategoriaDeleteView(View):
    """Delete a category"""

    template_name = "management/categoria_confirm_delete.html"

    def get(self, request, categoria_id):
        categoria = get_object_or_404(Categoria, pk=categoria_id)

        # Check if categoria has associated zapatos
        zapatos_count = categoria.zapatos.count()

        return render(request, self.template_name, {"categoria": categoria, "zapatos_count": zapatos_count})

    def post(self, request, categoria_id):
        categoria = get_object_or_404(Categoria, pk=categoria_id)

        # Categoria can be deleted even if it has zapatos (SET_NULL on delete)
        categoria_nombre = categoria.nombre
        categoria.delete()
        messages.success(request, f"Categoría {categoria_nombre} eliminada correctamente.")
        return redirect("categoria_list")


# Order Management Views


@method_decorator(staff_required, name="dispatch")
class OrderManagementListView(View):
    """View for managing all orders in the system"""

    template_name = "management/order_list.html"

    def get(self, request):
        from orders.models import Order

        orders = Order.objects.filter(pagado=True).select_related("usuario").order_by("-fecha_creacion")

        # Initialize filter form with GET data
        filter_form = OrderFilterForm(request.GET, estado_choices=Order.ESTADO_CHOICES)

        if filter_form.is_valid():
            # Filter by email
            email = filter_form.cleaned_data.get("email")
            if email:
                orders = orders.filter(Q(usuario__email__icontains=email) | Q(email__icontains=email))

            # Filter by name (searches in first_name, last_name, nombre, and apellido)
            nombre = filter_form.cleaned_data.get("nombre")
            if nombre:
                orders = orders.filter(
                    Q(usuario__first_name__icontains=nombre)
                    | Q(usuario__last_name__icontains=nombre)
                    | Q(nombre__icontains=nombre)
                    | Q(apellido__icontains=nombre)
                )

            # Filter by status
            estado = filter_form.cleaned_data.get("estado")
            if estado:
                orders = orders.filter(estado=estado)

        context = {
            "orders": orders,
            "filter_form": filter_form,
            "status_choices": Order.ESTADO_CHOICES,
        }

        return render(request, self.template_name, context)


@method_decorator(staff_required, name="dispatch")
class OrderManagementDetailView(View):
    """View for viewing and managing a specific order"""

    template_name = "management/order_detail.html"

    def get(self, request, codigo):
        from orders.models import Order

        order = get_object_or_404(Order, codigo_pedido=codigo)

        context = {
            "order": order,
            "status_choices": Order.ESTADO_CHOICES,
        }

        return render(request, self.template_name, context)

    def post(self, request, codigo):
        from orders.models import Order

        order = get_object_or_404(Order, codigo_pedido=codigo)

        # Update order status
        new_status = request.POST.get("estado")
        if new_status and new_status in dict(Order.ESTADO_CHOICES):
            order.estado = new_status
            order.save()
            messages.success(request, f"Estado del pedido actualizado a {order.get_estado_display()}")
        else:
            messages.error(request, "Estado inválido")

        return redirect("order_management_detail", codigo=codigo)


@method_decorator(staff_required, name="dispatch")
class CleanupExpiredOrdersView(View):
    """View for manually triggering cleanup of expired unpaid orders"""

    def post(self, request):
        from orders.utils import cleanup_expired_orders

        result = cleanup_expired_orders()

        messages.success(
            request,
            f"Limpieza completada: {result['deleted_count']} pedidos eliminados, "
            f"{result['restored_items']} items restaurados al stock.",
        )

        return redirect("admin_dashboard")
