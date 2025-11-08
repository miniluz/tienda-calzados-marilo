from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.views import View
from .forms import UserRegistrationForm, CustomerProfileForm, ProfileEditForm


class RegisterView(View):
    template_name = "accounts/register.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("home")

        user_form = UserRegistrationForm()
        customer_form = CustomerProfileForm()
        return render(request, self.template_name, {"user_form": user_form, "customer_form": customer_form})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect("home")

        user_form = UserRegistrationForm(request.POST)
        customer_form = CustomerProfileForm(request.POST)

        if user_form.is_valid() and customer_form.is_valid():
            try:
                with transaction.atomic():
                    user = user_form.save()

                    customer = customer_form.save(commit=False)
                    customer.user = user
                    customer.save()

                login(request, user)

                messages.success(request, f"¡Bienvenido {user.first_name}! Tu cuenta ha sido creada exitosamente.")
                return redirect("home")

            except Exception:
                messages.error(request, "Ha ocurrido un error al crear la cuenta. Por favor, inténtalo de nuevo.")

        return render(request, self.template_name, {"user_form": user_form, "customer_form": customer_form})


class ProfileView(LoginRequiredMixin, View):
    template_name = "accounts/profile.html"

    def get(self, request):
        try:
            customer = request.user.customer
        except ObjectDoesNotExist:
            messages.error(request, "No se encontró el perfil de cliente.")
            return redirect("home")

        return render(request, self.template_name, {"user": request.user, "customer": customer})


class ProfileEditView(LoginRequiredMixin, View):
    template_name = "accounts/profile_edit.html"

    def get(self, request):
        try:
            customer = request.user.customer
        except ObjectDoesNotExist:
            messages.error(request, "No se encontró el perfil de cliente.")
            return redirect("home")

        form = ProfileEditForm(
            initial={
                "first_name": request.user.first_name,
                "last_name": request.user.last_name,
                "phone_number": customer.phone_number,
                "address": customer.address,
                "city": customer.city,
                "postal_code": customer.postal_code,
            }
        )

        return render(request, self.template_name, {"form": form, "email": request.user.email})

    def post(self, request):
        try:
            customer = request.user.customer
        except ObjectDoesNotExist:
            messages.error(request, "No se encontró el perfil de cliente.")
            return redirect("home")

        form = ProfileEditForm(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    request.user.first_name = form.cleaned_data["first_name"]
                    request.user.last_name = form.cleaned_data["last_name"]
                    request.user.save()

                    customer.phone_number = form.cleaned_data["phone_number"]
                    customer.address = form.cleaned_data["address"]
                    customer.city = form.cleaned_data["city"]
                    customer.postal_code = form.cleaned_data["postal_code"]
                    customer.save()

                messages.success(request, "Perfil actualizado correctamente.")
                return redirect("profile")

            except Exception:
                messages.error(request, "Ha ocurrido un error al actualizar el perfil.")

        return render(request, self.template_name, {"form": form, "email": request.user.email})
