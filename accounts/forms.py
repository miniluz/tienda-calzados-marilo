from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from customer.models import Customer


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "correo@ejemplo.com"}),
        label="Correo electrónico",
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Tu nombre"}),
        label="Nombre",
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Tus apellidos"}),
        label="Apellidos",
    )

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({"class": "form-control", "placeholder": "Contraseña"})
        self.fields["password1"].label = "Contraseña"

        self.fields["password2"].widget.attrs.update({"class": "form-control", "placeholder": "Confirmar contraseña"})
        self.fields["password2"].label = "Confirmar contraseña"

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo electrónico.")
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo electrónico.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user


class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["phone_number", "address", "city", "postal_code"]
        widgets = {
            "phone_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "612345678", "maxlength": "9"}
            ),
            "address": forms.Textarea(
                attrs={"class": "form-control", "placeholder": "Calle, número, piso, puerta", "rows": 3}
            ),
            "city": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ciudad"}),
            "postal_code": forms.TextInput(attrs={"class": "form-control", "placeholder": "12345", "maxlength": "5"}),
        }
        labels = {
            "phone_number": "Teléfono",
            "address": "Dirección de envío",
            "city": "Ciudad",
            "postal_code": "Código postal",
        }

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number")
        if phone and not phone.isdigit():
            raise forms.ValidationError("El teléfono debe contener solo dígitos.")
        if phone and len(phone) != 9:
            raise forms.ValidationError("El teléfono debe tener 9 dígitos.")
        return phone

    def clean_postal_code(self):
        postal_code = self.cleaned_data.get("postal_code")
        if postal_code and not postal_code.isdigit():
            raise forms.ValidationError("El código postal debe contener solo dígitos.")
        if postal_code and len(postal_code) != 5:
            raise forms.ValidationError("El código postal debe tener 5 dígitos.")
        return postal_code


class ProfileEditForm(forms.Form):
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Nombre",
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Apellidos",
    )
    phone_number = forms.CharField(
        max_length=9,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "maxlength": "9"}),
        label="Número de teléfono",
    )
    address = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        label="Dirección asociada",
    )
    city = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label="Ciudad",
    )
    postal_code = forms.CharField(
        max_length=5,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "maxlength": "5"}),
        label="Código postal",
    )

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number")
        if phone and not phone.isdigit():
            raise forms.ValidationError("El teléfono debe contener solo dígitos.")
        if phone and len(phone) != 9:
            raise forms.ValidationError("El teléfono debe tener 9 dígitos.")
        return phone

    def clean_postal_code(self):
        postal_code = self.cleaned_data.get("postal_code")
        if postal_code and not postal_code.isdigit():
            raise forms.ValidationError("El código postal debe contener solo dígitos.")
        if postal_code and len(postal_code) != 5:
            raise forms.ValidationError("El código postal debe tener 5 dígitos.")
        return postal_code
