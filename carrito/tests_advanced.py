"""
Advanced tests for carrito app: edge cases, concurrency, validation, and integration tests.
"""

import threading

from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from catalog.models import Marca, TallaZapato, Zapato
from carrito.models import Carrito, ZapatoCarrito
from orders.models import Order
from orders.utils import validate_and_clean_cart


class BasicCartOperationsTests(TestCase):
    """Test basic cart operations"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(
            nombre="Test Zapato",
            precio=100,
            genero="Unisex",
            marca=self.marca,
            estaDisponible=True,
        )
        self.talla = TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=10)

    def test_add_item_to_cart(self):
        """Should successfully add item to cart"""
        response = self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 2},
        )

        self.assertEqual(response.status_code, 302)
        carrito = Carrito.objects.first()
        self.assertIsNotNone(carrito)
        self.assertEqual(carrito.zapatos.count(), 1)
        item = carrito.zapatos.first()
        self.assertEqual(item.cantidad, 2)
        self.assertEqual(item.talla, 42)

    def test_add_item_exceeding_stock(self):
        """Should cap quantity to available stock"""
        response = self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 15},  # More than stock
        )

        self.assertEqual(response.status_code, 302)
        carrito = Carrito.objects.first()
        item = carrito.zapatos.first()
        self.assertEqual(item.cantidad, 10)  # Capped to stock

    def test_add_duplicate_item_increases_quantity(self):
        """Adding same item should increase quantity"""
        # Add first time
        self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 2},
        )
        # Add again
        self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 3},
        )

        carrito = Carrito.objects.first()
        self.assertEqual(carrito.zapatos.count(), 1)  # Still one item
        item = carrito.zapatos.first()
        self.assertEqual(item.cantidad, 5)  # 2 + 3

    def test_remove_item_from_cart(self):
        """Should successfully remove item from cart"""
        # Add item
        self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 2},
        )
        carrito = Carrito.objects.first()
        item = carrito.zapatos.first()

        # Remove it
        response = self.client.post(reverse("carrito:remove_from_carrito", args=[item.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(carrito.zapatos.count(), 0)

    def test_increase_quantity(self):
        """Should increase item quantity"""
        # Add item
        self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 2},
        )
        carrito = Carrito.objects.first()
        item = carrito.zapatos.first()

        # Increase quantity
        self.client.post(reverse("carrito:update_quantity_carrito", args=[item.id]), {"action": "increase"})

        item.refresh_from_db()
        self.assertEqual(item.cantidad, 3)

    def test_decrease_quantity(self):
        """Should decrease item quantity"""
        # Add item
        self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 3},
        )
        carrito = Carrito.objects.first()
        item = carrito.zapatos.first()

        # Decrease quantity
        self.client.post(reverse("carrito:update_quantity_carrito", args=[item.id]), {"action": "decrease"})

        item.refresh_from_db()
        self.assertEqual(item.cantidad, 2)

    def test_decrease_quantity_to_zero_removes_item(self):
        """Decreasing quantity to 0 should remove item"""
        # Add item with quantity 1
        self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 1},
        )
        carrito = Carrito.objects.first()
        item = carrito.zapatos.first()

        # Decrease quantity (will remove)
        self.client.post(reverse("carrito:update_quantity_carrito", args=[item.id]), {"action": "decrease"})

        self.assertEqual(carrito.zapatos.count(), 0)


class CartValidationTests(TestCase):
    """Test cart validation and cleaning"""

    def setUp(self):
        """Create test data"""
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(
            nombre="Test Zapato",
            precio=100,
            genero="Unisex",
            marca=self.marca,
            estaDisponible=True,
        )
        self.talla = TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=5)
        self.carrito = Carrito.objects.create()

    def test_validate_removes_unavailable_product(self):
        """Should remove items with unavailable products"""
        # Add item to cart
        ZapatoCarrito.objects.create(carrito=self.carrito, zapato=self.zapato, talla=42, cantidad=2)

        # Mark product as unavailable
        self.zapato.estaDisponible = False
        self.zapato.save()

        # Validate cart
        messages = validate_and_clean_cart(self.carrito)

        self.assertEqual(self.carrito.zapatos.count(), 0)
        self.assertTrue(any("ya no está disponible" in msg["message"] for msg in messages))

    def test_validate_removes_out_of_stock_item(self):
        """Should remove items with zero stock"""
        # Add item to cart
        ZapatoCarrito.objects.create(carrito=self.carrito, zapato=self.zapato, talla=42, cantidad=2)

        # Set stock to zero
        self.talla.stock = 0
        self.talla.save()

        # Validate cart
        messages = validate_and_clean_cart(self.carrito)

        self.assertEqual(self.carrito.zapatos.count(), 0)
        self.assertTrue(any("agotado" in msg["message"] for msg in messages))

    def test_validate_adjusts_quantity_to_stock(self):
        """Should adjust quantity when stock is insufficient"""
        # Add item with quantity 5
        ZapatoCarrito.objects.create(carrito=self.carrito, zapato=self.zapato, talla=42, cantidad=5)

        # Reduce stock to 3
        self.talla.stock = 3
        self.talla.save()

        # Validate cart
        messages = validate_and_clean_cart(self.carrito)

        item = self.carrito.zapatos.first()
        self.assertEqual(item.cantidad, 3)
        self.assertTrue(any("se ajustó" in msg["message"] for msg in messages))

    def test_validate_removes_nonexistent_size(self):
        """Should remove items when size is deleted"""
        # Add item to cart
        ZapatoCarrito.objects.create(carrito=self.carrito, zapato=self.zapato, talla=42, cantidad=2)

        # Delete the size
        self.talla.delete()

        # Validate cart
        messages = validate_and_clean_cart(self.carrito)

        self.assertEqual(self.carrito.zapatos.count(), 0)
        self.assertTrue(any("ya no está disponible" in msg["message"] for msg in messages))

    def test_validate_on_cart_view(self):
        """Cart view should automatically validate"""
        client = Client()

        # Add item to cart
        client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 5},
        )

        # Mark product unavailable
        self.zapato.estaDisponible = False
        self.zapato.save()

        # View cart (should trigger validation)
        response = client.get(reverse("carrito:view_carrito"))

        self.assertEqual(response.status_code, 200)
        # Cart should be empty after validation
        carrito = Carrito.objects.first()
        self.assertEqual(carrito.zapatos.count(), 0)


class ConcurrentCartAccessTests(TransactionTestCase):
    """Test concurrent access to cart"""

    def setUp(self):
        """Create test data"""
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(
            nombre="Test Zapato",
            precio=100,
            genero="Unisex",
            marca=self.marca,
            estaDisponible=True,
        )
        self.talla = TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=1)

    def test_concurrent_add_to_cart_last_item(self):
        """Two concurrent adds should handle last item correctly"""
        results = {"success": 0, "adjusted": 0}

        def add_to_cart():
            """Add item to cart"""
            try:
                connection.close()
                client = Client()
                response = client.post(
                    reverse("carrito:add_to_carrito", args=[self.zapato.id]),
                    {"talla": 42, "cantidad": 1},
                )
                if response.status_code == 302:
                    results["success"] += 1
            finally:
                connection.close()

        # Start two threads
        thread1 = threading.Thread(target=add_to_cart)
        thread2 = threading.Thread(target=add_to_cart)

        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        # Both should succeed in adding to cart (not yet checking out)
        # The stock check happens at checkout time
        self.assertEqual(results["success"], 2)

    def test_concurrent_quantity_increase(self):
        """Concurrent quantity increases should be safe"""
        client = Client()
        client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 1},
        )
        carrito = Carrito.objects.first()
        item = carrito.zapatos.first()

        # Set stock to 5 for testing
        self.talla.stock = 5
        self.talla.save()

        def increase_quantity():
            """Increase quantity"""
            try:
                connection.close()
                c = Client()
                c.post(reverse("carrito:update_quantity_carrito", args=[item.id]), {"action": "increase"})
            finally:
                connection.close()

        threads = [threading.Thread(target=increase_quantity) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        item.refresh_from_db()
        # Quantity should not exceed stock
        self.assertLessEqual(item.cantidad, 5)


class CheckoutIntegrationTests(TestCase):
    """Test full checkout flow from cart"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato1 = Zapato.objects.create(
            nombre="Zapato 1",
            precio=100,
            precioOferta=80,
            genero="Unisex",
            marca=self.marca,
            estaDisponible=True,
        )
        self.zapato2 = Zapato.objects.create(
            nombre="Zapato 2",
            precio=50,
            genero="Unisex",
            marca=self.marca,
            estaDisponible=True,
        )
        self.talla1 = TallaZapato.objects.create(zapato=self.zapato1, talla=42, stock=10)
        self.talla2 = TallaZapato.objects.create(zapato=self.zapato2, talla=40, stock=5)

    def test_checkout_from_cart_creates_order(self):
        """Checkout from cart should create order and reserve stock"""
        # Add items to cart
        self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato1.id]),
            {"talla": 42, "cantidad": 2},
        )
        self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato2.id]),
            {"talla": 40, "cantidad": 1},
        )

        initial_stock1 = self.talla1.stock
        initial_stock2 = self.talla2.stock

        # Checkout
        response = self.client.post(reverse("carrito:checkout_from_carrito"))

        # Should redirect to checkout contact
        self.assertEqual(response.status_code, 302)
        self.assertIn("checkout_contact", response.url)

        # Order should be created
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.items.count(), 2)

        # Stock should be reserved
        self.talla1.refresh_from_db()
        self.talla2.refresh_from_db()
        self.assertEqual(self.talla1.stock, initial_stock1 - 2)
        self.assertEqual(self.talla2.stock, initial_stock2 - 1)

        # Cart should be empty
        carrito = Carrito.objects.first()
        self.assertEqual(carrito.zapatos.count(), 0)

    def test_checkout_validates_before_creating_order(self):
        """Checkout should validate cart and fail if items unavailable"""
        # Add item to cart
        self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato1.id]),
            {"talla": 42, "cantidad": 2},
        )

        # Mark product unavailable
        self.zapato1.estaDisponible = False
        self.zapato1.save()

        # Try to checkout
        response = self.client.post(reverse("carrito:checkout_from_carrito"))

        # Should redirect back to cart
        self.assertEqual(response.status_code, 302)
        self.assertIn("view_carrito", response.url)

        # No order should be created
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_with_insufficient_stock(self):
        """Checkout should fail if stock is insufficient"""
        # Add item to cart
        self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato1.id]),
            {"talla": 42, "cantidad": 5},
        )

        # Reduce stock below cart quantity
        self.talla1.stock = 3
        self.talla1.save()

        # Try to checkout
        response = self.client.post(reverse("carrito:checkout_from_carrito"))

        # Should redirect back to cart with error
        self.assertEqual(response.status_code, 302)

        # No order should be created
        self.assertEqual(Order.objects.count(), 0)

    def test_empty_cart_checkout_fails(self):
        """Checkout with empty cart should fail"""
        response = self.client.post(reverse("carrito:checkout_from_carrito"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)


class BuyNowIntegrationTests(TestCase):
    """Test buy now flow"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(
            nombre="Test Zapato",
            precio=100,
            precioOferta=80,
            genero="Unisex",
            marca=self.marca,
            estaDisponible=True,
        )
        self.talla = TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=10)

    def test_buy_now_creates_order(self):
        """Buy now should create order and reserve stock"""
        initial_stock = self.talla.stock

        response = self.client.post(
            reverse("catalog:buy_now", args=[self.zapato.id]),
            {"talla": 42},
        )

        # Should redirect to checkout
        self.assertEqual(response.status_code, 302)
        self.assertIn("checkout_contact", response.url)

        # Order should be created
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.items.count(), 1)
        item = order.items.first()
        self.assertEqual(item.cantidad, 1)
        self.assertEqual(item.zapato, self.zapato)

        # Stock should be reserved
        self.talla.refresh_from_db()
        self.assertEqual(self.talla.stock, initial_stock - 1)

    def test_buy_now_with_out_of_stock(self):
        """Buy now should fail when out of stock"""
        self.talla.stock = 0
        self.talla.save()

        response = self.client.post(
            reverse("catalog:buy_now", args=[self.zapato.id]),
            {"talla": 42},
        )

        # Should redirect back to product page
        self.assertEqual(response.status_code, 302)
        self.assertIn("zapato_detail", response.url)

        # No order should be created
        self.assertEqual(Order.objects.count(), 0)

    def test_buy_now_same_result_as_cart_checkout(self):
        """Buy now and cart checkout should produce identical orders"""
        # Create two identical products
        zapato2 = Zapato.objects.create(
            nombre="Test Zapato 2",
            precio=100,
            precioOferta=80,
            genero="Unisex",
            marca=self.marca,
            estaDisponible=True,
        )
        TallaZapato.objects.create(zapato=zapato2, talla=42, stock=10)

        # Test buy now
        client1 = Client()
        client1.post(reverse("catalog:buy_now", args=[self.zapato.id]), {"talla": 42})
        order1 = Order.objects.first()

        # Test cart checkout
        client2 = Client()
        client2.post(
            reverse("carrito:add_to_carrito", args=[zapato2.id]),
            {"talla": 42, "cantidad": 1},
        )
        client2.post(reverse("carrito:checkout_from_carrito"))
        order2 = Order.objects.last()

        # Both should have same structure
        self.assertEqual(order1.items.count(), 1)
        self.assertEqual(order2.items.count(), 1)
        self.assertEqual(order1.subtotal, order2.subtotal)
        self.assertEqual(order1.total, order2.total)


class EdgeCaseTests(TestCase):
    """Test edge cases"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(
            nombre="Test Zapato",
            precio=100,
            genero="Unisex",
            marca=self.marca,
            estaDisponible=True,
        )
        self.talla = TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=10)

    def test_add_without_selecting_size(self):
        """Adding to cart without size should fail"""
        response = self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"cantidad": 1},  # No talla
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Carrito.objects.count(), 0)

    def test_cart_persists_across_page_views(self):
        """Cart should persist across multiple page views"""
        # Add item
        self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 2},
        )

        # View cart multiple times
        for _ in range(3):
            response = self.client.get(reverse("carrito:view_carrito"))
            self.assertEqual(response.status_code, 200)

        # Cart should still have the item
        carrito = Carrito.objects.first()
        self.assertEqual(carrito.zapatos.count(), 1)

    def test_multiple_sizes_same_product(self):
        """Cart should handle multiple sizes of same product"""
        TallaZapato.objects.create(zapato=self.zapato, talla=43, stock=5)

        # Add size 42
        self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 2},
        )

        # Add size 43
        self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 43, "cantidad": 1},
        )

        carrito = Carrito.objects.first()
        self.assertEqual(carrito.zapatos.count(), 2)

    def test_increase_quantity_at_max_stock(self):
        """Increasing quantity when at max stock should show warning"""
        self.talla.stock = 3
        self.talla.save()

        # Add item with max stock
        self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 3},
        )

        carrito = Carrito.objects.first()
        item = carrito.zapatos.first()

        # Try to increase (should fail)
        self.client.post(reverse("carrito:update_quantity_carrito", args=[item.id]), {"action": "increase"})

        item.refresh_from_db()
        self.assertEqual(item.cantidad, 3)  # Should not increase

    def test_product_deleted_while_in_cart(self):
        """Cart should handle product deletion gracefully"""
        # Add item to cart
        self.client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 2},
        )

        # Delete product
        self.zapato.delete()

        # Viewing cart should handle this gracefully
        response = self.client.get(reverse("carrito:view_carrito"))
        self.assertEqual(response.status_code, 200)


class AuthenticatedCartTests(TestCase):
    """Test cart behavior for authenticated users"""

    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(
            nombre="Test Zapato",
            precio=100,
            genero="Unisex",
            marca=self.marca,
            estaDisponible=True,
        )
        self.talla = TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=10)

    def test_authenticated_user_has_cart_tied_to_user(self):
        """Authenticated user's cart should be tied to user account"""
        client = Client()
        client.login(username="testuser", password="testpass")

        client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 2},
        )

        carrito = Carrito.objects.first()
        self.assertEqual(carrito.usuario, self.user)
        self.assertIsNone(carrito.sesion)

    def test_guest_cart_uses_session(self):
        """Guest user's cart should use session"""
        client = Client()

        client.post(
            reverse("carrito:add_to_carrito", args=[self.zapato.id]),
            {"talla": 42, "cantidad": 2},
        )

        carrito = Carrito.objects.first()
        self.assertIsNone(carrito.usuario)
        self.assertIsNotNone(carrito.sesion)
