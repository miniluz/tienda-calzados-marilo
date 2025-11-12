from django.db import models
from django.urls import reverse


class Zapato(models.Model):
    nombre = models.CharField("Nombre", max_length=200)
    descripcion = models.TextField("Descripción", blank=True)
    precio = models.IntegerField("Precio")
    precioOferta = models.IntegerField("Precio de Oferta", blank=True, null=True)
    genero = models.CharField(
        "Género",
        max_length=50,
        choices=[
            ("Hombre", "Hombre"),
            ("Mujer", "Mujer"),
            ("Niño", "Niño"),
            ("Niña", "Niña"),
            ("Unisex", "Unisex"),
        ],
    )
    color = models.CharField("Color", max_length=50, blank=True)
    material = models.CharField("Material", max_length=100, blank=True)
    estaDisponible = models.BooleanField("Disponible", default=True)
    estaDestacado = models.BooleanField("Destacado", default=False)
    fechaCreacion = models.DateField("Fecha de Creación", auto_now_add=True)
    fechaActualizacion = models.DateField("Fecha de Actualización", auto_now=True)
    marca = models.ForeignKey("Marca", on_delete=models.PROTECT, related_name="zapatos")
    categoria = models.ForeignKey("Categoria", on_delete=models.SET_NULL, related_name="zapatos", blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} ({self.descripcion})"

    def get_absolute_url(self):
        return reverse("catalog:zapato_detail", args=[str(self.id)])

    @property
    def descuento_porcentaje(self):
        """Calculate discount percentage if there's an offer price"""
        if self.precioOferta and self.precio > 0:
            return round(((self.precio - self.precioOferta) / self.precio) * 100)
        return 0

    class Meta:
        ordering = ["-fechaCreacion"]
        verbose_name = "Zapato"
        verbose_name_plural = "Zapatos"


class Marca(models.Model):
    nombre = models.CharField("Nombre de la Marca", max_length=100)
    imagen = models.ImageField("Imagen de la Marca", upload_to="marcas/", blank=True, null=True)
    fechaCreacion = models.DateField("Fecha de Creación", auto_now_add=True)
    fechaActualizacion = models.DateField("Fecha de Actualización", auto_now=True)


class TallaZapato(models.Model):
    talla = models.IntegerField("Talla")
    stock = models.IntegerField("Stock", default=0)
    fechaCreacion = models.DateField("Fecha de Creación", auto_now_add=True)
    fechaActualizacion = models.DateField("Fecha de Actualización", auto_now=True)
    zapato = models.ForeignKey(Zapato, on_delete=models.CASCADE, related_name="tallas")


class ImagenZapato(models.Model):
    zapato = models.ForeignKey(Zapato, on_delete=models.CASCADE, related_name="imagenes")
    imagen = models.ImageField("Imagen del Zapato", upload_to="zapatos/", blank=True, null=True)
    esPrincipal = models.BooleanField("Imagen Principal", default=False)
    fechaCreacion = models.DateField("Fecha de Creación", auto_now_add=True)
    fechaActualizacion = models.DateField("Fecha de Actualización", auto_now=True)


class Categoria(models.Model):
    nombre = models.CharField("Nombre de la Categoría", max_length=100)
    imagen = models.ImageField("Imagen de la Categoría", upload_to="categorias/", blank=True, null=True)
    fechaCreacion = models.DateField("Fecha de Creación", auto_now_add=True)
    fechaActualizacion = models.DateField("Fecha de Actualización", auto_now=True)
