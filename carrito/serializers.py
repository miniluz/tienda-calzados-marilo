from rest_framework import serializers
from .models import Carrito, ZapatoCarrito


class CarritoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Carrito
        fields = ["id", "usuario", "zapatos", "sesion"]


class ZapatoCarritoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ZapatoCarrito
        fields = ["id", "carrito", "zapato", "cantidad", "talla"]
