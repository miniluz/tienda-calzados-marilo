from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.forms import inlineformset_factory
from catalog.models import Zapato, Marca, Categoria, TallaZapato


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


# ==================== CATALOG MANAGEMENT FORMS ====================


class ZapatoForm(forms.ModelForm):
    class Meta:
        model = Zapato
        fields = [
            "nombre",
            "descripcion",
            "marca",
            "precio",
            "precioOferta",
            "categoria",
            "genero",
            "material",
            "color",
            "imagen",
            "estaDisponible",
            "estaDestacado",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre del producto"}),
            "descripcion": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Descripción del producto"}
            ),
            "marca": forms.Select(attrs={"class": "form-select"}),
            "precio": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "15.99", "step": "0.01", "min": "1"}
            ),
            "precioOferta": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "11.99", "step": "0.01", "min": "1"}
            ),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "genero": forms.Select(attrs={"class": "form-select"}),
            "material": forms.TextInput(attrs={"class": "form-control", "placeholder": "Tela, Cuero, etc."}),
            "color": forms.TextInput(attrs={"class": "form-control", "placeholder": "Negro, Marrón y blanco, etc."}),
            "imagen": forms.FileInput(attrs={"class": "form-control"}),
            "estaDisponible": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "estaDestacado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "estaDisponible": "Disponible",
            "estaDestacado": "Destacado",
        }


class TallaZapatoForm(forms.ModelForm):
    class Meta:
        model = TallaZapato
        fields = ["talla", "stock"]
        widgets = {
            "talla": forms.NumberInput(attrs={"class": "form-control"}),
            "stock": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
        }


# Formset for managing all sizes for a shoe
TallaZapatoFormSet = inlineformset_factory(
    Zapato,
    TallaZapato,
    form=TallaZapatoForm,
    extra=0,  # Don't show extra blank forms
    can_delete=True,  # Allow deletion
)


class MarcaForm(forms.ModelForm):
    class Meta:
        model = Marca
        fields = ["nombre", "imagen"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre de la marca"}),
            "imagen": forms.FileInput(attrs={"class": "form-control"}),
        }


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "imagen"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre de la categoría"}),
            "imagen": forms.FileInput(attrs={"class": "form-control"}),
        }
