from django.test import TestCase
from .models import Carrito, ZapatoCarrito


class CarritoModelTest(TestCase):

    def setUp(self):
        self.cart = Carrito.objects.create(usuario=None)  # Assuming user is optional for testing

    def test_cart_creation(self):
        self.assertIsInstance(self.cart, Carrito)
        self.assertEqual(self.cart.items.count(), 0)


class ZapatoCarritoModelTest(TestCase):

    def setUp(self):
        self.carrito = Carrito.objects.create(usuario=None)
        self.zapato_carrito = ZapatoCarrito.objects.create(carrito=self.carrito, zapato="Test Product", cantidad=1)

    def test_cart_item_creation(self):
        self.assertIsInstance(self.zapato_carrito, ZapatoCarrito)
        self.assertEqual(self.zapato_carrito.carrito, self.carrito)
        self.assertEqual(self.zapato_carrito.zapato, "Test Product")
        self.assertEqual(self.zapato_carrito.cantidad, 1)

    def test_cart_item_quantity_update(self):
        self.zapato_carrito.cantidad = 2
        self.zapato_carrito.save()
        self.assertEqual(self.zapato_carrito.cantidad, 2)
