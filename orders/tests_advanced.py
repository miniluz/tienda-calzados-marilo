"""
Advanced tests for orders app: edge cases, concurrency, cleanup, and integration tests.
"""

import threading
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.db import connection, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Marca, TallaZapato, Zapato
from customer.models import Customer
from orders.models import Order, OrderItem
from orders.utils import (
    calculate_order_prices,
    cleanup_expired_orders,
    generate_order_code,
    reserve_stock,
    restore_stock,
)


class EdgeCaseStockTests(TestCase):
    """Test edge cases for stock management"""

    def setUp(self):
        """Create test data"""
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(
            nombre="Test Zapato",
            precio=100,
            genero="Unisex",
            marca=self.marca,
        )
        self.talla = TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=5)

    def test_buy_exact_available_stock(self):
        """Should successfully reserve when buying exactly all available stock"""
        cart_items = [{"zapato": self.zapato, "talla": 42, "cantidad": 5}]

        result = reserve_stock(cart_items)

        self.assertTrue(result)
        self.talla.refresh_from_db()
        self.assertEqual(self.talla.stock, 0)

    def test_buy_with_zero_initial_stock(self):
        """Should raise error when trying to buy from zero stock"""
        self.talla.stock = 0
        self.talla.save()

        cart_items = [{"zapato": self.zapato, "talla": 42, "cantidad": 1}]

        with self.assertRaises(ValueError) as cm:
            reserve_stock(cart_items)

        self.assertIn("Stock insuficiente", str(cm.exception))
        self.talla.refresh_from_db()
        self.assertEqual(self.talla.stock, 0)

    def test_atomicity_multiple_items_one_fails(self):
        """Should rollback all reservations if one item fails"""
        zapato2 = Zapato.objects.create(
            nombre="Test Zapato 2",
            precio=50,
            genero="Unisex",
            marca=self.marca,
        )
        talla2 = TallaZapato.objects.create(zapato=zapato2, talla=40, stock=2)

        # First item has enough stock, second doesn't
        cart_items = [
            {"zapato": self.zapato, "talla": 42, "cantidad": 2},
            {"zapato": zapato2, "talla": 40, "cantidad": 5},  # Insufficient!
        ]

        with self.assertRaises(ValueError):
            reserve_stock(cart_items)

        # Verify first item's stock was NOT deducted (atomicity)
        self.talla.refresh_from_db()
        self.assertEqual(self.talla.stock, 5)
        talla2.refresh_from_db()
        self.assertEqual(talla2.stock, 2)

    def test_nonexistent_size(self):
        """Should raise error when size doesn't exist"""
        cart_items = [{"zapato": self.zapato, "talla": 99, "cantidad": 1}]

        with self.assertRaises(ValueError) as cm:
            reserve_stock(cart_items)

        self.assertIn("no disponible", str(cm.exception))

    def test_multiple_sizes_same_shoe(self):
        """Should handle multiple sizes of same shoe in cart"""
        talla2 = TallaZapato.objects.create(zapato=self.zapato, talla=43, stock=3)

        cart_items = [
            {"zapato": self.zapato, "talla": 42, "cantidad": 2},
            {"zapato": self.zapato, "talla": 43, "cantidad": 1},
        ]

        result = reserve_stock(cart_items)

        self.assertTrue(result)
        self.talla.refresh_from_db()
        talla2.refresh_from_db()
        self.assertEqual(self.talla.stock, 3)
        self.assertEqual(talla2.stock, 2)

    def test_stock_never_goes_negative(self):
        """Verify stock cannot go negative through race conditions"""
        cart_items = [{"zapato": self.zapato, "talla": 42, "cantidad": 10}]

        with self.assertRaises(ValueError):
            reserve_stock(cart_items)

        self.talla.refresh_from_db()
        self.assertGreaterEqual(self.talla.stock, 0)

    def test_restore_when_size_deleted(self):
        """Should handle gracefully when size is deleted before restoration"""
        order = Order.objects.create(
            codigo_pedido="TEST123",
            metodo_pago="tarjeta",
            pagado=False,
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Test",
            apellido="User",
            email="test@test.com",
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )

        OrderItem.objects.create(
            pedido=order,
            zapato=self.zapato,
            talla=42,
            cantidad=3,
            precio_unitario=100,
            total=300,
        )

        # Delete the size
        self.talla.delete()

        # Restoration should not crash
        restored = restore_stock(order)
        self.assertEqual(restored, [])


class ConcurrentPurchaseTests(TransactionTestCase):
    """Test concurrent purchase scenarios - requires TransactionTestCase for threading"""

    def setUp(self):
        """Create test data"""
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(
            nombre="Test Zapato",
            precio=100,
            genero="Unisex",
            marca=self.marca,
        )
        self.talla = TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=1)

    def test_concurrent_last_item_purchase(self):
        """Two users try to buy the last item - only one should succeed"""
        results = {"success": 0, "failed": 0}
        errors = []

        def attempt_purchase():
            """Attempt to reserve the last item"""
            try:
                # Close old connection and get fresh one for this thread
                connection.close()
                cart_items = [{"zapato": self.zapato, "talla": 42, "cantidad": 1}]
                reserve_stock(cart_items)
                results["success"] += 1
            except ValueError as e:
                results["failed"] += 1
                errors.append(str(e))
            finally:
                # Ensure connection is closed when thread completes
                connection.close()

        # Start two threads simultaneously
        thread1 = threading.Thread(target=attempt_purchase)
        thread2 = threading.Thread(target=attempt_purchase)

        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        # Exactly one should succeed, one should fail
        self.assertEqual(results["success"], 1)
        self.assertEqual(results["failed"], 1)

        # Verify stock is zero
        self.talla.refresh_from_db()
        self.assertEqual(self.talla.stock, 0)

    def test_concurrent_stock_depletion(self):
        """Multiple concurrent purchases should properly deplete stock"""
        # Set stock to 10
        self.talla.stock = 10
        self.talla.save()

        results = {"success": 0, "failed": 0}

        def attempt_purchase(cantidad):
            """Attempt to reserve items"""
            try:
                connection.close()
                cart_items = [{"zapato": self.zapato, "talla": 42, "cantidad": cantidad}]
                reserve_stock(cart_items)
                results["success"] += 1
            except ValueError:
                results["failed"] += 1
            finally:
                # Ensure connection is closed when thread completes
                connection.close()

        # 5 threads each trying to buy 3 items (total 15 > 10 available)
        threads = [threading.Thread(target=attempt_purchase, args=(3,)) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Some should succeed, some should fail, total shouldn't exceed 10
        self.talla.refresh_from_db()
        self.assertGreaterEqual(self.talla.stock, 0)
        self.assertLessEqual(10 - self.talla.stock, 10)

    def test_select_for_update_prevents_double_booking(self):
        """Verify select_for_update prevents double booking"""
        self.talla.stock = 5
        self.talla.save()

        def reserve_with_delay():
            """Reserve stock with artificial delay"""
            try:
                connection.close()
                with transaction.atomic():
                    cart_items = [{"zapato": self.zapato, "talla": 42, "cantidad": 5}]
                    # This will use select_for_update internally
                    reserve_stock(cart_items)
            except ValueError:
                # Expected - one thread will fail when stock is depleted
                # Silently catch to avoid printing exception to stderr
                pass
            finally:
                # Ensure connection is closed when thread completes
                connection.close()

        thread1 = threading.Thread(target=reserve_with_delay)
        thread2 = threading.Thread(target=reserve_with_delay)

        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        # One transaction should wait for the other
        self.talla.refresh_from_db()
        # Stock should be exactly 0 or 5 (one succeeded, one failed cleanly)
        self.assertIn(self.talla.stock, [0, 5])

    def test_concurrent_cleanup_prevents_double_stock_restoration(self):
        """Two simultaneous cleanups should not double-restore stock"""
        # Set stock to 10
        self.talla.stock = 10
        self.talla.save()

        # Create an expired order with 3 items
        order = Order.objects.create(
            codigo_pedido="CONCURRENT_TEST",
            metodo_pago="tarjeta",
            pagado=False,
            subtotal=300,
            impuestos=63,
            coste_entrega=5,
            total=368,
            nombre="Test",
            apellido="User",
            email="test@test.com",
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )

        OrderItem.objects.create(
            pedido=order,
            zapato=self.zapato,
            talla=42,
            cantidad=3,
            precio_unitario=100,
            total=300,
        )

        # Make order expired (25 minutes old)
        order.fecha_creacion = timezone.now() - timezone.timedelta(minutes=25)
        order.save()

        # Deduct stock to simulate reservation
        self.talla.stock -= 3
        self.talla.save()
        self.assertEqual(self.talla.stock, 7)

        cleanup_results = []

        def run_cleanup():
            """Run cleanup_expired_orders in a thread"""
            try:
                connection.close()
                result = cleanup_expired_orders()
                cleanup_results.append(result)
            finally:
                connection.close()

        # Run cleanup in two threads simultaneously
        thread1 = threading.Thread(target=run_cleanup)
        thread2 = threading.Thread(target=run_cleanup)

        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        # Verify stock is restored exactly once (not doubled)
        self.talla.refresh_from_db()
        self.assertEqual(self.talla.stock, 10, "Stock should be restored to original value, not doubled")

        # Verify order is deleted
        self.assertFalse(Order.objects.filter(codigo_pedido="CONCURRENT_TEST").exists())

        # At least one cleanup should have processed the order
        total_deleted = sum(r["deleted_count"] for r in cleanup_results)
        self.assertEqual(total_deleted, 1, "Order should be deleted exactly once")


class CleanupTests(TestCase):
    """Test cleanup of expired orders"""

    def setUp(self):
        """Create test data"""
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(
            nombre="Test Zapato",
            precio=100,
            genero="Unisex",
            marca=self.marca,
        )
        self.talla = TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=10)

    def _create_order(self, codigo, pagado=False, minutes_old=25):
        """Helper to create an order"""
        order = Order.objects.create(
            codigo_pedido=codigo,
            metodo_pago="tarjeta",
            pagado=pagado,
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Test",
            apellido="User",
            email="test@test.com",
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )
        order.fecha_creacion = timezone.now() - timezone.timedelta(minutes=minutes_old)
        order.save()
        return order

    def test_cleanup_at_exact_boundary(self):
        """Test cleanup at exact 20-minute boundary"""
        # Order at exactly 20 minutes old
        order = self._create_order("EXACT20", pagado=False, minutes_old=20)
        OrderItem.objects.create(
            pedido=order,
            zapato=self.zapato,
            talla=42,
            cantidad=2,
            precio_unitario=100,
            total=200,
        )

        result = cleanup_expired_orders()

        # Should be cleaned up (>= 20 minutes)
        self.assertEqual(result["deleted_count"], 1)

    def test_cleanup_just_before_boundary(self):
        """Test cleanup doesn't affect orders just under 20 minutes"""
        # Order at 19 minutes 59 seconds old
        order = Order.objects.create(
            codigo_pedido="UNDER20",
            metodo_pago="tarjeta",
            pagado=False,
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Test",
            apellido="User",
            email="test@test.com",
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )
        order.fecha_creacion = timezone.now() - timezone.timedelta(seconds=1199)
        order.save()

        OrderItem.objects.create(
            pedido=order,
            zapato=self.zapato,
            talla=42,
            cantidad=2,
            precio_unitario=100,
            total=200,
        )

        result = cleanup_expired_orders()

        # Should NOT be cleaned up
        self.assertEqual(result["deleted_count"], 0)
        self.assertTrue(Order.objects.filter(codigo_pedido="UNDER20").exists())

    def test_cleanup_multiple_expired_orders(self):
        """Should clean up multiple expired orders in batch"""
        initial_stock = self.talla.stock

        for i in range(5):
            order = self._create_order(f"EXPIRED{i}", pagado=False, minutes_old=25)
            OrderItem.objects.create(
                pedido=order,
                zapato=self.zapato,
                talla=42,
                cantidad=2,
                precio_unitario=100,
                total=200,
            )

        # Deduct stock
        self.talla.stock = initial_stock - 10
        self.talla.save()

        result = cleanup_expired_orders()

        self.assertEqual(result["deleted_count"], 5)
        self.assertEqual(result["restored_items"], 5)

        # Stock should be restored
        self.talla.refresh_from_db()
        self.assertEqual(self.talla.stock, initial_stock)

    def test_cleanup_doesnt_affect_paid_orders(self):
        """Paid orders should never be cleaned up"""
        self._create_order("PAID123", pagado=True, minutes_old=100)

        result = cleanup_expired_orders()

        self.assertEqual(result["deleted_count"], 0)
        self.assertTrue(Order.objects.filter(codigo_pedido="PAID123").exists())

    def test_cleanup_with_mixed_orders(self):
        """Should only clean up expired unpaid orders"""
        self._create_order("RECENT", pagado=False, minutes_old=5)
        self._create_order("PAID", pagado=True, minutes_old=30)
        expired = self._create_order("EXPIRED", pagado=False, minutes_old=25)
        OrderItem.objects.create(
            pedido=expired,
            zapato=self.zapato,
            talla=42,
            cantidad=1,
            precio_unitario=100,
            total=100,
        )

        result = cleanup_expired_orders()

        self.assertEqual(result["deleted_count"], 1)
        self.assertTrue(Order.objects.filter(codigo_pedido="RECENT").exists())
        self.assertTrue(Order.objects.filter(codigo_pedido="PAID").exists())
        self.assertFalse(Order.objects.filter(codigo_pedido="EXPIRED").exists())

    def test_cleanup_performance_many_orders(self):
        """Should handle many expired orders efficiently"""
        # Create 100 expired orders
        for i in range(100):
            order = self._create_order(f"EXP{i:03d}", pagado=False, minutes_old=25)
            OrderItem.objects.create(
                pedido=order,
                zapato=self.zapato,
                talla=42,
                cantidad=1,
                precio_unitario=100,
                total=100,
            )

        result = cleanup_expired_orders()

        self.assertEqual(result["deleted_count"], 100)
        self.assertEqual(result["restored_items"], 100)

    def test_concurrent_cleanup_idempotency(self):
        """Concurrent cleanups should not cause errors"""
        order = self._create_order("EXPIRED", pagado=False, minutes_old=25)
        OrderItem.objects.create(
            pedido=order,
            zapato=self.zapato,
            talla=42,
            cantidad=2,
            precio_unitario=100,
            total=200,
        )

        # First cleanup
        result1 = cleanup_expired_orders()
        # Second cleanup (should find nothing)
        result2 = cleanup_expired_orders()

        self.assertEqual(result1["deleted_count"], 1)
        self.assertEqual(result2["deleted_count"], 0)


class IntegrationCheckoutTests(TestCase):
    """Integration tests for full checkout flow"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato1 = Zapato.objects.create(
            nombre="Test Zapato 1",
            precio=100,
            precioOferta=80,
            genero="Unisex",
            marca=self.marca,
            estaDisponible=True,
        )
        self.zapato2 = Zapato.objects.create(
            nombre="Test Zapato 2",
            precio=50,
            genero="Unisex",
            marca=self.marca,
            estaDisponible=True,
        )
        self.talla1 = TallaZapato.objects.create(zapato=self.zapato1, talla=42, stock=10)
        self.talla2 = TallaZapato.objects.create(zapato=self.zapato2, talla=40, stock=5)

        # Create a user for authenticated tests
        self.user = User.objects.create_user(
            username="testuser@example.com",
            email="testuser@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        self.customer = Customer.objects.create(
            user=self.user,
            phone_number="123456789",
            address="Test Address",
            city="Test City",
            postal_code="12345",
        )

    @patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.create")
    def test_full_checkout_flow_guest(self, mock_stripe_create):
        """Test complete checkout flow as guest user"""
        # Mock successful Stripe Checkout Session response
        mock_session = Mock()
        mock_session.id = "cs_test_integration_123"
        mock_session.url = "https://checkout.stripe.com/test"
        mock_stripe_create.return_value = mock_session

        # Step 1: Start checkout
        response = self.client.get(reverse("orders:checkout_start"))
        self.assertEqual(response.status_code, 302)

        # Verify order was created and session set
        self.assertIn("checkout_order_id", self.client.session)
        order_id = self.client.session["checkout_order_id"]
        order = Order.objects.get(id=order_id)
        self.assertFalse(order.pagado)

        # Step 2: Contact info
        response = self.client.post(
            reverse("orders:checkout_contact"),
            {
                "nombre": "John",
                "apellido": "Doe",
                "email": "john@example.com",
                "telefono": "987654321",
            },
        )
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.nombre, "John")

        # Step 3: Both shipping and billing addresses (unified page)
        response = self.client.post(
            reverse("orders:checkout_address"),
            {
                "direccion_envio": "123 Main St",
                "ciudad_envio": "Madrid",
                "codigo_postal_envio": "28001",
                "direccion_facturacion": "123 Main St",
                "ciudad_facturacion": "Madrid",
                "codigo_postal_facturacion": "28001",
            },
        )
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.ciudad_envio, "Madrid")
        self.assertEqual(order.direccion_facturacion, "123 Main St")

        # Step 4: Payment
        response = self.client.post(
            reverse("orders:checkout_payment"),
            {"metodo_pago": "tarjeta"},
        )
        # Should redirect to Stripe Checkout
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://checkout.stripe.com/test")

        # Order should NOT be marked as paid yet (waiting for webhook)
        order.refresh_from_db()
        self.assertFalse(order.pagado)

        # Session should still have the order (cleared after successful payment)
        self.assertIn("checkout_order_id", self.client.session)

    def test_authenticated_user_data_prepopulation(self):
        """Test that authenticated users get data pre-populated"""
        self.client.login(username="testuser@example.com", password="testpass123")

        # Start checkout
        self.client.get(reverse("orders:checkout_start"))

        # Check contact page has pre-populated data
        response = self.client.get(reverse("orders:checkout_contact"))
        self.assertContains(response, self.user.first_name)
        self.assertContains(response, self.user.email)

    def test_checkout_with_expired_order(self):
        """Test handling of expired order during checkout"""
        # Start checkout
        self.client.get(reverse("orders:checkout_start"))
        order_id = self.client.session["checkout_order_id"]

        # Manually expire the order (25 minutes = beyond 20-minute reservation)
        order = Order.objects.get(id=order_id)
        order.fecha_creacion = timezone.now() - timezone.timedelta(minutes=25)
        order.save()

        # Delete the expired order (simulate cleanup)
        order.delete()

        # Try to continue checkout
        response = self.client.get(reverse("orders:checkout_contact"))

        # Should redirect to start
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("orders:checkout_start"), response.url)

    def test_session_persistence_across_steps(self):
        """Verify session persists throughout checkout"""
        # Start checkout
        self.client.get(reverse("orders:checkout_start"))
        order_id = self.client.session["checkout_order_id"]

        # Navigate through steps
        self.client.post(
            reverse("orders:checkout_contact"),
            {
                "nombre": "Test",
                "apellido": "User",
                "email": "test@test.com",
                "telefono": "123",
            },
        )

        # Session should still have same order
        self.assertEqual(self.client.session["checkout_order_id"], order_id)

    def test_billing_different_from_shipping(self):
        """Test billing address different from shipping"""
        self.client.get(reverse("orders:checkout_start"))
        order_id = self.client.session["checkout_order_id"]

        # Fill contact
        self.client.post(
            reverse("orders:checkout_contact"),
            {
                "nombre": "Test",
                "apellido": "User",
                "email": "test@test.com",
                "telefono": "123",
            },
        )

        # Fill both shipping and billing with different addresses
        self.client.post(
            reverse("orders:checkout_address"),
            {
                "direccion_envio": "Shipping St",
                "ciudad_envio": "ShipCity",
                "codigo_postal_envio": "11111",
                "direccion_facturacion": "Billing Ave",
                "ciudad_facturacion": "BillCity",
                "codigo_postal_facturacion": "22222",
            },
        )

        order = Order.objects.get(id=order_id)
        self.assertEqual(order.direccion_facturacion, "Billing Ave")
        self.assertEqual(order.ciudad_facturacion, "BillCity")
        self.assertNotEqual(order.direccion_facturacion, order.direccion_envio)


class InputValidationTests(TestCase):
    """Test input validation for utility functions"""

    def setUp(self):
        """Create test data"""
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(
            nombre="Test Zapato",
            precio=100,
            genero="Unisex",
            marca=self.marca,
        )
        self.talla = TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=10)

    def test_reserve_stock_missing_zapato_key(self):
        """Should raise error when 'zapato' key is missing"""
        cart_items = [{"talla": 42, "cantidad": 1}]

        with self.assertRaises((KeyError, ValueError)):
            reserve_stock(cart_items)

    def test_reserve_stock_missing_talla_key(self):
        """Should raise error when 'talla' key is missing"""
        cart_items = [{"zapato": self.zapato, "cantidad": 1}]

        with self.assertRaises((KeyError, ValueError)):
            reserve_stock(cart_items)

    def test_reserve_stock_missing_cantidad_key(self):
        """Should raise error when 'cantidad' key is missing"""
        cart_items = [{"zapato": self.zapato, "talla": 42}]

        with self.assertRaises((KeyError, ValueError)):
            reserve_stock(cart_items)

    def test_reserve_stock_zero_quantity(self):
        """Should raise error for zero quantity"""
        cart_items = [{"zapato": self.zapato, "talla": 42, "cantidad": 0}]

        with self.assertRaises(ValueError):
            reserve_stock(cart_items)

    def test_reserve_stock_negative_quantity(self):
        """Should raise error for negative quantity"""
        cart_items = [{"zapato": self.zapato, "talla": 42, "cantidad": -5}]

        with self.assertRaises(ValueError):
            reserve_stock(cart_items)

    def test_reserve_stock_invalid_type(self):
        """Should raise error for invalid types"""
        cart_items = [{"zapato": self.zapato, "talla": "invalid", "cantidad": 1}]

        with self.assertRaises((TypeError, ValueError)):
            reserve_stock(cart_items)

    def test_reserve_stock_empty_list(self):
        """Should handle empty cart gracefully"""
        cart_items = []

        with self.assertRaises(ValueError):
            reserve_stock(cart_items)

    def test_calculate_prices_missing_keys(self):
        """Should raise error when cart items have missing keys"""
        cart_items = [{"zapato": self.zapato}]  # Missing talla, cantidad

        with self.assertRaises((KeyError, ValueError)):
            calculate_order_prices(cart_items)

    def test_calculate_prices_empty_cart(self):
        """Should raise error for empty cart"""
        cart_items = []

        with self.assertRaises(ValueError):
            calculate_order_prices(cart_items)


class AdditionalEdgeCaseTests(TestCase):
    """Additional edge case tests"""

    def setUp(self):
        """Create test data"""
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(
            nombre="Test Zapato",
            precio=100,
            precioOferta=80,
            genero="Unisex",
            marca=self.marca,
        )
        self.talla = TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=1000000)

    def test_very_large_quantity(self):
        """Test ordering very large quantities"""
        cart_items = [{"zapato": self.zapato, "talla": 42, "cantidad": 999999}]

        with self.assertRaises(ValueError):
            reserve_stock(cart_items)

    def test_decimal_precision_in_calculations(self):
        """Test that decimal precision is maintained"""
        # Price with repeating decimal
        self.zapato.precio = Decimal("99.99")
        self.zapato.precioOferta = Decimal("66.66")
        self.zapato.save()

        cart_items = [{"zapato": self.zapato, "talla": 42, "cantidad": 3}]

        result = calculate_order_prices(cart_items, delivery_cost=4.99, tax_rate=21.0)

        # Check proper rounding
        self.assertIsInstance(result["subtotal"], Decimal)
        self.assertEqual(result["subtotal"].as_tuple().exponent, -2)  # 2 decimal places

    def test_order_code_collision_handling(self):
        """Test that order code collisions are handled"""
        # Create order with a specific code
        Order.objects.create(
            codigo_pedido="TESTCODE123",
            metodo_pago="tarjeta",
            pagado=False,
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Test",
            apellido="User",
            email="test@test.com",
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )

        # Generate many codes to check uniqueness
        codes = [generate_order_code() for _ in range(1000)]
        self.assertNotIn("TESTCODE123", codes)  # Should be extremely unlikely

    def test_mixed_offer_and_regular_prices(self):
        """Test cart with both offer and regular priced items"""
        zapato2 = Zapato.objects.create(
            nombre="Regular Price Shoe",
            precio=50,
            genero="Unisex",
            marca=self.marca,
        )

        TallaZapato.objects.create(zapato=zapato2, talla=40, stock=10)

        cart_items = [
            {"zapato": self.zapato, "talla": 42, "cantidad": 2},  # Has offer
            {"zapato": zapato2, "talla": 40, "cantidad": 1},  # No offer
        ]

        result = calculate_order_prices(cart_items, delivery_cost=5.0, tax_rate=21.0)

        # Subtotal: (80 * 2) + (50 * 1) = 210
        # Discount: (100 - 80) * 2 = 40
        self.assertEqual(result["subtotal"], Decimal("210.00"))
        self.assertEqual(result["descuento"], Decimal("40.00"))

    def test_zero_price_items(self):
        """Test handling of zero-price items (promotional items)"""
        free_shoe = Zapato.objects.create(
            nombre="Free Promo Shoe",
            precio=0,
            genero="Unisex",
            marca=self.marca,
        )
        TallaZapato.objects.create(zapato=free_shoe, talla=42, stock=10)

        cart_items = [{"zapato": free_shoe, "talla": 42, "cantidad": 1}]

        result = calculate_order_prices(cart_items, delivery_cost=5.0, tax_rate=21.0)

        self.assertEqual(result["subtotal"], Decimal("0.00"))
        # Tax should still apply to delivery
        self.assertGreater(result["total"], Decimal("5.00"))


class OrderOwnershipTests(TestCase):
    """Test order ownership validation during checkout"""

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
        TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=10)

        # Create two users
        self.user1 = User.objects.create_user(
            username="user1@example.com",
            email="user1@example.com",
            password="pass123",
        )
        self.user2 = User.objects.create_user(
            username="user2@example.com",
            email="user2@example.com",
            password="pass123",
        )

    def test_authenticated_user_can_access_own_order(self):
        """Authenticated user should be able to access their own order"""
        self.client.login(username="user1@example.com", password="pass123")

        # Start checkout as user1
        response = self.client.get(reverse("orders:checkout_start"))
        self.assertEqual(response.status_code, 302)

        # Get the order
        order_id = self.client.session.get("checkout_order_id")
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.usuario, self.user1)

        # User1 should be able to access contact page
        response = self.client.get(reverse("orders:checkout_contact"))
        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_cannot_hijack_another_users_order(self):
        """Authenticated user should NOT be able to access another user's order"""
        # User1 starts checkout
        self.client.login(username="user1@example.com", password="pass123")
        self.client.get(reverse("orders:checkout_start"))
        order_id = self.client.session.get("checkout_order_id")

        # User1 logs out, User2 logs in
        self.client.logout()
        self.client.login(username="user2@example.com", password="pass123")

        # User2 tries to access user1's order by setting session
        session = self.client.session
        session["checkout_order_id"] = order_id
        session.save()

        # Should redirect to checkout start (order not accessible)
        response = self.client.get(reverse("orders:checkout_contact"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("orders:checkout_start"), response.url)

    def test_guest_order_remains_accessible_to_session(self):
        """Guest order should be accessible via session without user validation"""
        # Start checkout as guest
        response = self.client.get(reverse("orders:checkout_start"))
        self.assertEqual(response.status_code, 302)

        order_id = self.client.session.get("checkout_order_id")
        order = Order.objects.get(id=order_id)
        self.assertIsNone(order.usuario)

        # Guest should be able to continue checkout
        response = self.client.get(reverse("orders:checkout_contact"))
        self.assertEqual(response.status_code, 200)


class PaymentTimingTests(TestCase):
    """Test payment timing windows (10min forms + 5min payment)"""

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
        TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=10)

    def test_payment_page_accessible_before_10_minutes(self):
        """Payment page should be accessible if order is less than 10 minutes old"""
        # Start checkout
        self.client.get(reverse("orders:checkout_start"))

        # Fill in required forms
        self.client.post(
            reverse("orders:checkout_contact"),
            {
                "nombre": "Test",
                "apellido": "User",
                "email": "test@test.com",
                "telefono": "123456789",
            },
        )
        self.client.post(
            reverse("orders:checkout_address"),
            {
                "direccion_envio": "Test St",
                "ciudad_envio": "Test City",
                "codigo_postal_envio": "12345",
                "direccion_facturacion": "Test St",
                "ciudad_facturacion": "Test City",
                "codigo_postal_facturacion": "12345",
            },
        )

        # Access payment page (should work)
        response = self.client.get(reverse("orders:checkout_payment"))
        self.assertEqual(response.status_code, 200)

    def test_payment_page_blocked_after_10_minutes(self):
        """Payment page should be blocked if order is more than 10 minutes old"""
        from tienda_calzados_marilo.env import getEnvConfig

        # Start checkout
        self.client.get(reverse("orders:checkout_start"))
        order_id = self.client.session.get("checkout_order_id")

        # Age the order beyond checkout window (11 minutes)
        order = Order.objects.get(id=order_id)
        env_config = getEnvConfig()
        order.fecha_creacion = timezone.now() - timezone.timedelta(minutes=env_config.CHECKOUT_FORM_WINDOW_MINUTES + 1)
        order.save()

        # Try to access payment page
        response = self.client.get(reverse("orders:checkout_payment"))

        # Should redirect to start
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("orders:checkout_start"), response.url)

    def test_payment_fails_if_exceeds_total_window(self):
        """Payment should fail if order exceeds total window (15 minutes)"""
        from tienda_calzados_marilo.env import getEnvConfig

        # Start checkout
        self.client.get(reverse("orders:checkout_start"))
        order_id = self.client.session.get("checkout_order_id")

        # Fill forms
        order = Order.objects.get(id=order_id)
        order.nombre = "Test"
        order.apellido = "User"
        order.email = "test@test.com"
        order.telefono = "123"
        order.direccion_envio = "St"
        order.ciudad_envio = "City"
        order.codigo_postal_envio = "12345"
        order.direccion_facturacion = "St"
        order.ciudad_facturacion = "City"
        order.codigo_postal_facturacion = "12345"

        # Age the order beyond total window (16 minutes)
        env_config = getEnvConfig()
        total_window = env_config.CHECKOUT_FORM_WINDOW_MINUTES + env_config.PAYMENT_WINDOW_MINUTES
        order.fecha_creacion = timezone.now() - timezone.timedelta(minutes=total_window + 1)
        order.save()

        # Try to submit payment
        response = self.client.post(
            reverse("orders:checkout_payment"),
            {"metodo_pago": "tarjeta"},
        )

        # Should redirect to start
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("orders:checkout_start"), response.url)


class OrderItemDiscountStorageTests(TestCase):
    """Test that discount is stored correctly in OrderItem"""

    def setUp(self):
        """Create test data"""
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato_with_offer = Zapato.objects.create(
            nombre="Offer Shoe",
            precio=100,
            precioOferta=75,
            genero="Unisex",
            marca=self.marca,
            estaDisponible=True,
        )
        self.zapato_no_offer = Zapato.objects.create(
            nombre="Regular Shoe",
            precio=50,
            genero="Unisex",
            marca=self.marca,
            estaDisponible=True,
        )
        TallaZapato.objects.create(zapato=self.zapato_with_offer, talla=42, stock=10)
        TallaZapato.objects.create(zapato=self.zapato_no_offer, talla=42, stock=10)

    def test_discount_stored_correctly_with_offer_price(self):
        """Discount should be stored when item has offer price"""
        order = Order.objects.create(
            codigo_pedido="TEST123",
            metodo_pago="tarjeta",
            pagado=False,
            subtotal=150,
            impuestos=31.5,
            coste_entrega=5,
            total=186.5,
            nombre="Test",
            apellido="User",
            email="test@test.com",
            telefono="123",
            direccion_envio="St",
            ciudad_envio="City",
            codigo_postal_envio="12345",
            direccion_facturacion="St",
            ciudad_facturacion="City",
            codigo_postal_facturacion="12345",
        )

        # Create item with offer price
        item = OrderItem.objects.create(
            pedido=order,
            zapato=self.zapato_with_offer,
            talla=42,
            cantidad=2,
            precio_unitario=Decimal("75.00"),
            total=Decimal("150.00"),
            descuento=Decimal("50.00"),  # (100 - 75) * 2
        )

        # Discount should be stored
        self.assertEqual(item.descuento, Decimal("50.00"))

    def test_discount_zero_when_no_offer(self):
        """Discount should be zero when item has no offer"""
        order = Order.objects.create(
            codigo_pedido="TEST124",
            metodo_pago="tarjeta",
            pagado=False,
            subtotal=50,
            impuestos=11.55,
            coste_entrega=5,
            total=66.55,
            nombre="Test",
            apellido="User",
            email="test@test.com",
            telefono="123",
            direccion_envio="St",
            ciudad_envio="City",
            codigo_postal_envio="12345",
            direccion_facturacion="St",
            ciudad_facturacion="City",
            codigo_postal_facturacion="12345",
        )

        # Create item without offer
        item = OrderItem.objects.create(
            pedido=order,
            zapato=self.zapato_no_offer,
            talla=42,
            cantidad=1,
            precio_unitario=Decimal("50.00"),
            total=Decimal("50.00"),
            descuento=Decimal("0.00"),
        )

        # Discount should be zero
        self.assertEqual(item.descuento, Decimal("0.00"))

    def test_discount_persists_after_offer_changes(self):
        """Stored discount should not change when offer price changes"""
        order = Order.objects.create(
            codigo_pedido="TEST125",
            metodo_pago="tarjeta",
            pagado=True,
            subtotal=75,
            impuestos=16.8,
            coste_entrega=5,
            total=96.8,
            nombre="Test",
            apellido="User",
            email="test@test.com",
            telefono="123",
            direccion_envio="St",
            ciudad_envio="City",
            codigo_postal_envio="12345",
            direccion_facturacion="St",
            ciudad_facturacion="City",
            codigo_postal_facturacion="12345",
        )

        # Create item with original offer (100 -> 75, discount = 25)
        item = OrderItem.objects.create(
            pedido=order,
            zapato=self.zapato_with_offer,
            talla=42,
            cantidad=1,
            precio_unitario=Decimal("75.00"),
            total=Decimal("75.00"),
            descuento=Decimal("25.00"),
        )

        # Change the offer price on the zapato
        self.zapato_with_offer.precioOferta = Decimal("85.00")
        self.zapato_with_offer.save()

        # Refresh item from database
        item.refresh_from_db()

        # Stored discount should remain unchanged
        self.assertEqual(item.descuento, Decimal("25.00"))

        # Order's total discount should also remain unchanged
        self.assertEqual(order.descuento_total, Decimal("25.00"))
