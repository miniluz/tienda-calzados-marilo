from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class CustomerEditForm(forms.Form):
    email = forms.EmailField(
        required=True,
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "correo@ejemplo.com"}),
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label="Nombre",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre"}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        label="Apellidos",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Apellidos"}),
    )
    phone_number = forms.CharField(
        max_length=9,
        required=True,
        label="Número de teléfono",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "612345678"}),
    )
    address = forms.CharField(
        required=True,
        label="Dirección",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Calle, número, piso..."}),
    )
    city = forms.CharField(
        required=True,
        label="Ciudad",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Madrid"}),
    )
    postal_code = forms.CharField(
        max_length=5,
        required=True,
        label="Código postal",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "28001"}),
    )

    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop("user_id", None)
        super().__init__(*args, **kwargs)

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number")
        if not phone.isdigit() or len(phone) != 9:
            raise forms.ValidationError("El teléfono debe tener 9 dígitos.")
        return phone

    def clean_postal_code(self):
        postal_code = self.cleaned_data.get("postal_code")
        if not postal_code.isdigit() or len(postal_code) != 5:
            raise forms.ValidationError("El código postal debe tener 5 dígitos.")
        return postal_code

    def clean_email(self):
        email = self.cleaned_data.get("email")
        existing_user = User.objects.filter(email=email).exclude(pk=self.user_id).first()
        if existing_user:
            raise forms.ValidationError("Ya existe una cuenta con este correo electrónico.")
        existing_username = User.objects.filter(username=email).exclude(pk=self.user_id).first()
        if existing_username:
            raise forms.ValidationError("Ya existe una cuenta con este correo electrónico.")
        return email


class AdminCreateForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "correo@ejemplo.com"}),
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label="Nombre",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre"}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        label="Apellidos",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Apellidos"}),
    )

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({"class": "form-control"})
        self.fields["password2"].widget.attrs.update({"class": "form-control"})

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
        user.is_staff = True
        if commit:
            user.save()
        return user


class AdminEditForm(forms.Form):
    email = forms.EmailField(
        required=True,
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "correo@ejemplo.com"}),
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label="Nombre",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre"}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        label="Apellidos",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Apellidos"}),
    )

    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop("user_id", None)
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data.get("email")
        existing_user = User.objects.filter(email=email).exclude(pk=self.user_id).first()
        if existing_user:
            raise forms.ValidationError("Ya existe una cuenta con este correo electrónico.")
        existing_username = User.objects.filter(username=email).exclude(pk=self.user_id).first()
        if existing_username:
            raise forms.ValidationError("Ya existe una cuenta con este correo electrónico.")
        return email
