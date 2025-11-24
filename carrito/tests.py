from django.test import TestCase

from catalog.models import Marca, TallaZapato, Zapato

from .models import Carrito, ZapatoCarrito


class CarritoModelTest(TestCase):

    def setUp(self):
        self.cart = Carrito.objects.create(usuario=None)  # Assuming user is optional for testing

    def test_cart_creation(self):
        self.assertIsInstance(self.cart, Carrito)
        self.assertEqual(self.cart.zapatos.count(), 0)


class ZapatoCarritoModelTest(TestCase):

    def setUp(self):
        self.carrito = Carrito.objects.create(usuario=None)
        # Create proper Zapato instance
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(
            nombre="Test Product", precio=100, genero="Unisex", marca=self.marca, estaDisponible=True
        )
        TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=10)
        self.zapato_carrito = ZapatoCarrito.objects.create(
            carrito=self.carrito, zapato=self.zapato, talla=42, cantidad=1
        )

    def test_cart_item_creation(self):
        self.assertIsInstance(self.zapato_carrito, ZapatoCarrito)
        self.assertEqual(self.zapato_carrito.carrito, self.carrito)
        self.assertEqual(self.zapato_carrito.zapato, self.zapato)
        self.assertEqual(self.zapato_carrito.cantidad, 1)

    def test_cart_item_quantity_update(self):
        self.zapato_carrito.cantidad = 2
        self.zapato_carrito.save()
        self.assertEqual(self.zapato_carrito.cantidad, 2)
