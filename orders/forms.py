from django import forms


class ContactInfoForm(forms.Form):
    """Form for collecting contact information during checkout"""

    nombre = forms.CharField(
        label="Nombre",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Introduce tu nombre",
            }
        ),
    )
    apellido = forms.CharField(
        label="Apellido",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Introduce tu apellido",
            }
        ),
    )
    email = forms.EmailField(
        label="Correo Electrónico",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "ejemplo@correo.com",
            }
        ),
    )
    telefono = forms.CharField(
        label="Teléfono",
        max_length=15,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "600123456",
            }
        ),
    )

    def clean_telefono(self):
        telefono = self.cleaned_data.get("telefono")
        if not telefono.isdigit() or len(telefono) != 9:
            raise forms.ValidationError("El teléfono debe tener 9 dígitos.")
        return telefono


class ShippingAddressForm(forms.Form):
    """Form for collecting shipping address during checkout"""

    direccion_envio = forms.CharField(
        label="Dirección de Envío",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Calle, número, piso, puerta...",
            }
        ),
    )
    ciudad_envio = forms.CharField(
        label="Ciudad",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ciudad",
            }
        ),
    )
    codigo_postal_envio = forms.CharField(
        label="Código Postal",
        max_length=10,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "41001",
            }
        ),
    )

    def clean_codigo_postal_envio(self):
        codigo_postal = self.cleaned_data.get("codigo_postal_envio")
        if not codigo_postal.isdigit() or len(codigo_postal) != 5:
            raise forms.ValidationError("El código postal debe tener 5 dígitos.")
        return codigo_postal


class BillingAddressForm(forms.Form):
    """Form for collecting billing address during checkout"""

    direccion_facturacion = forms.CharField(
        label="Dirección de Facturación",
        required=True,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Calle, número, piso, puerta...",
            }
        ),
    )
    ciudad_facturacion = forms.CharField(
        label="Ciudad",
        max_length=100,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ciudad",
            }
        ),
    )
    codigo_postal_facturacion = forms.CharField(
        label="Código Postal",
        max_length=10,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "41001",
            }
        ),
    )

    def clean_codigo_postal_facturacion(self):
        codigo_postal = self.cleaned_data.get("codigo_postal_facturacion")
        if not codigo_postal.isdigit() or len(codigo_postal) != 5:
            raise forms.ValidationError("El código postal debe tener 5 dígitos.")
        return codigo_postal


class PaymentMethodForm(forms.Form):
    """Form for selecting payment method"""

    metodo_pago = forms.ChoiceField(
        label="Método de Pago",
        choices=[
            ("contrarembolso", "Contrarreembolso (pago al recibir)"),
            ("tarjeta", "Tarjeta de Crédito/Débito"),
        ],
        initial="tarjeta",
        widget=forms.RadioSelect(
            attrs={
                "class": "form-check-input",
            }
        ),
    )


class OrderLookupForm(forms.Form):
    """Form for looking up an order by its code"""

    codigo_pedido = forms.CharField(
        label="Código de Pedido",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Introduce tu código de pedido",
            }
        ),
    )

    def clean_codigo_pedido(self):
        codigo = self.cleaned_data.get("codigo_pedido")
        if not codigo:
            raise forms.ValidationError("El código de pedido es obligatorio.")
        # Remove whitespace
        codigo = codigo.strip()
        if not codigo.isalnum():
            raise forms.ValidationError("El código de pedido debe ser alfanumérico (solo letras y números).")
        if len(codigo) < 5:
            raise forms.ValidationError("El código de pedido debe tener al menos 5 caracteres.")
        return codigo.upper()
