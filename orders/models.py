from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import Zapato


class Order(models.Model):
    """Pedido de compra"""

    ESTADO_CHOICES = [
        ("por_enviar", "Por Enviar"),
        ("en_envio", "En Envío"),
        ("recibido", "Recibido"),
    ]

    METODO_PAGO_CHOICES = [
        ("contrarembolso", "Contrarreembolso"),
        ("tarjeta", "Tarjeta"),
    ]

    codigo_pedido = models.CharField("Código de Pedido", max_length=20, unique=True, db_index=True)
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pedidos",
        verbose_name="Usuario",
    )

    fecha_creacion = models.DateTimeField("Fecha de Creación", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("Fecha de Actualización", auto_now=True)

    estado = models.CharField("Estado", max_length=20, choices=ESTADO_CHOICES, default="por_enviar")
    metodo_pago = models.CharField("Método de Pago", max_length=20, choices=METODO_PAGO_CHOICES)
    pagado = models.BooleanField("Pagado", default=False)

    subtotal = models.DecimalField("Subtotal", max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    impuestos = models.DecimalField("Impuestos", max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    coste_entrega = models.DecimalField(
        "Coste de Entrega",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    total = models.DecimalField("Total", max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    nombre = models.CharField("Nombre", max_length=100, blank=False)
    apellido = models.CharField("Apellido", max_length=100, blank=False)
    email = models.EmailField("Correo Electrónico", blank=False)
    telefono = models.CharField("Teléfono", max_length=15, blank=False)

    direccion_envio = models.TextField("Dirección de Envío", blank=False)
    ciudad_envio = models.CharField("Ciudad de Envío", max_length=100, blank=False)
    codigo_postal_envio = models.CharField("Código Postal de Envío", max_length=10, blank=False)

    direccion_facturacion = models.TextField("Dirección de Facturación", blank=False)
    ciudad_facturacion = models.CharField("Ciudad de Facturación", max_length=100, blank=False)
    codigo_postal_facturacion = models.CharField("Código Postal de Facturación", max_length=10, blank=False)

    class Meta:
        ordering = ["-fecha_creacion"]
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        indexes = [
            models.Index(fields=["pagado", "fecha_creacion"], name="orders_pagado_fecha_idx"),
        ]

    def __str__(self):
        return f"Pedido {self.codigo_pedido} - {self.get_estado_display()}"

    @property
    def descuento_total(self):
        """Calculate total discount from all items"""
        return sum(item.descuento for item in self.items.all())


class OrderItem(models.Model):
    """Item de un pedido"""

    pedido = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="Pedido")
    zapato = models.ForeignKey(Zapato, on_delete=models.PROTECT, verbose_name="Zapato")
    talla = models.IntegerField("Talla")
    cantidad = models.IntegerField("Cantidad", validators=[MinValueValidator(1)], default=1)
    precio_unitario = models.DecimalField(
        "Precio Unitario",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    total = models.DecimalField("Total", max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    descuento = models.DecimalField(
        "Descuento",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0,
    )

    class Meta:
        verbose_name = "Item de Pedido"
        verbose_name_plural = "Items de Pedido"
        unique_together = [["pedido", "zapato", "talla"]]

    def __str__(self):
        return f"{self.zapato.nombre} (Talla {self.talla}) x{self.cantidad}"
