from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from django.contrib.auth.models import User
from django.db import transaction
from django.views import View
from customer.models import Customer
from .forms import CustomerEditForm, AdminCreateForm, AdminEditForm


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
        return render(
            request,
            self.template_name,
            {"customer_count": customer_count, "admin_count": admin_count},
        )


@method_decorator(staff_required, name="dispatch")
class CustomerListView(View):
    template_name = "management/customer_list.html"

    def get(self, request):
        customers = Customer.objects.select_related("user").all().order_by("-created_at")
        return render(request, self.template_name, {"customers": customers})


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
