from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class Carrito(models.Model):
    usuario = models.ForeignKey("auth.User", on_delete=models.SET_NULL, related_name="carritos", null=True, blank=True)
    fechaCreacion = models.DateField("Fecha de Creación", auto_now_add=True)
    fechaActualizacion = models.DateField("Fecha de Actualización", auto_now=True)
    sesion = models.CharField("ID de Sesión", max_length=100, blank=True, null=True)

    def __str__(self):
        usuario_nombre = self.usuario.username if self.usuario else "Usuario no registrado"
        return f"Carrito de {usuario_nombre} - {self.id}"

    def get_absolute_url(self):
        return reverse("carrito:carrito_detail", args=[str(self.id)])

    class Meta:
        ordering = ["-fechaCreacion"]
        verbose_name = "Carrito"
        verbose_name_plural = "Carritos"


class ZapatoCarrito(models.Model):
    carrito = models.ForeignKey("Carrito", on_delete=models.CASCADE, related_name="zapatos")
    zapato = models.ForeignKey("catalog.Zapato", on_delete=models.CASCADE, related_name="zapatos_carrito")
    cantidad = models.IntegerField("Cantidad", validators=[MinValueValidator(1)], default=1)
    talla = models.IntegerField("Talla")
    fechaCreacion = models.DateField("Fecha de Creación", auto_now_add=True)
    fechaActualizacion = models.DateField("Fecha de Actualización", auto_now=True)

    def __str__(self):
        return f"{self.cantidad} x {self.zapato.nombre} en Carrito {self.carrito.id}"

    def get_absolute_url(self):
        return reverse("carrito:zapatocarrito_detail", args=[str(self.id)])

    class Meta:
        ordering = ["-fechaCreacion"]
        verbose_name = "Zapato del Carrito"
        verbose_name_plural = "Zapatos del Carrito"
