"""
Tests for edge cases in Stripe integration:
- Session expiration
- Multiple payment attempts
- Cancel and restart flows
- Payment after order cleanup
"""

import os
from unittest.mock import Mock, patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Marca, TallaZapato, Zapato
from orders.models import Order, OrderItem
from orders.test_helpers.stripe_mocks import (
    create_expired_stripe_session_mock,
    create_stripe_checkout_session_mock,
)
from tienda_calzados_marilo.env import getEnvConfig


class StripeSessionExpirationTests(TestCase):
    """Test Stripe session expiration scenarios"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.return_url = reverse("orders:stripe_return")

        # Create test product
        marca = Marca.objects.create(nombre="Test Marca")
        zapato = Zapato.objects.create(
            nombre="Test Shoe",
            precio=100,
            genero="Unisex",
            marca=marca,
            estaDisponible=True,
        )
        TallaZapato.objects.create(zapato=zapato, talla=42, stock=10)

        # Create test order
        self.order = Order.objects.create(
            codigo_pedido="EXPIRE123",
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

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.retrieve")
    def test_return_to_expired_session_shows_validating(self, mock_session_retrieve):
        """Returning to expired session should show validating page"""
        # Setup mock for expired session
        mock_session = create_expired_stripe_session_mock(self.order)
        mock_session_retrieve.return_value = mock_session

        # Set session
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session.save()

        # Send return request
        response = self.client.get(self.return_url + "?session_id=cs_test_expired123")

        # Should show validating page
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/validating.html")

        # Order should NOT be marked paid
        self.order.refresh_from_db()
        self.assertFalse(self.order.pagado)

    def test_expired_order_cleaned_up_properly(self):
        """Expired unpaid orders should be cleaned up by cleanup job"""
        from orders.utils import cleanup_expired_orders

        # Create items for the order
        marca = Marca.objects.create(nombre="Test Marca")
        zapato = Zapato.objects.create(
            nombre="Test Shoe",
            precio=100,
            genero="Unisex",
            marca=marca,
            estaDisponible=True,
        )
        talla = TallaZapato.objects.create(zapato=zapato, talla=42, stock=5)

        OrderItem.objects.create(
            pedido=self.order,
            zapato=zapato,
            talla=42,
            cantidad=2,
            precio_unitario=100,
            total=200,
        )

        # Age the order beyond expiration
        env_config = getEnvConfig()
        expiration_minutes = env_config.get_order_reservation_minutes()
        self.order.fecha_creacion = timezone.now() - timezone.timedelta(minutes=expiration_minutes + 5)
        self.order.save()

        # Deduct stock (simulating reservation)
        talla.stock = 3
        talla.save()

        # Run cleanup
        result = cleanup_expired_orders()

        # Order should be deleted
        self.assertFalse(Order.objects.filter(codigo_pedido="EXPIRE123").exists())

        # Stock should be restored
        talla.refresh_from_db()
        self.assertEqual(talla.stock, 5)

        # Cleanup should report results
        self.assertEqual(result["deleted_count"], 1)
        self.assertEqual(result["restored_items"], 1)


class MultiplePaymentAttemptTests(TestCase):
    """Test multiple payment attempt scenarios"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.payment_url = reverse("orders:checkout_payment")
        self.cancel_url = reverse("orders:stripe_cancel")

        # Create test product
        marca = Marca.objects.create(nombre="Test Marca")
        zapato = Zapato.objects.create(
            nombre="Test Shoe",
            precio=100,
            genero="Unisex",
            marca=marca,
            estaDisponible=True,
        )
        TallaZapato.objects.create(zapato=zapato, talla=42, stock=10)

        # Create test order
        self.order = Order.objects.create(
            codigo_pedido="MULTI123",
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

        # Set session
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session.save()

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.create")
    def test_user_starts_payment_cancels_restarts(self, mock_session_create):
        """User should be able to cancel and restart payment"""
        # Setup mock
        mock_session = Mock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/test"
        mock_session_create.return_value = mock_session

        # First payment attempt
        response1 = self.client.post(self.payment_url, {"metodo_pago": "tarjeta"})
        self.assertEqual(response1.status_code, 302)
        self.assertIn("checkout.stripe.com", response1.url)

        # User cancels (visits cancel page)
        cancel_response = self.client.get(self.cancel_url)
        self.assertEqual(cancel_response.status_code, 200)

        # Order should still be unpaid
        self.order.refresh_from_db()
        self.assertFalse(self.order.pagado)

        # Session should still exist
        self.assertIn("checkout_order_id", self.client.session)

        # Second payment attempt (should work)
        response2 = self.client.post(self.payment_url, {"metodo_pago": "tarjeta"})
        self.assertEqual(response2.status_code, 302)
        self.assertIn("checkout.stripe.com", response2.url)

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.create")
    def test_user_creates_multiple_checkout_sessions(self, mock_session_create):
        """Creating multiple checkout sessions should work (Stripe allows this)"""

        # Setup mock to return different session IDs
        def create_session(**kwargs):
            session = Mock()
            session.id = f"cs_test_{mock_session_create.call_count}"
            session.url = f"https://checkout.stripe.com/test_{session.id}"
            return session

        mock_session_create.side_effect = create_session

        # Create first session
        response1 = self.client.post(self.payment_url, {"metodo_pago": "tarjeta"})
        self.assertEqual(response1.status_code, 302)
        first_session_id = "cs_test_1"
        self.assertIn(first_session_id, response1.url)

        # Create second session (without completing first)
        response2 = self.client.post(self.payment_url, {"metodo_pago": "tarjeta"})
        self.assertEqual(response2.status_code, 302)
        second_session_id = "cs_test_2"
        self.assertIn(second_session_id, response2.url)

        # Both sessions should be created
        self.assertEqual(mock_session_create.call_count, 2)

    def test_second_payment_attempt_after_timeout(self):
        """Payment attempt after form timeout should redirect to start"""
        # Age the order beyond checkout window
        env_config = getEnvConfig()
        self.order.fecha_creacion = timezone.now() - timezone.timedelta(
            minutes=env_config.CHECKOUT_FORM_WINDOW_MINUTES + 1
        )
        self.order.save()

        # Try to access payment page
        response = self.client.get(self.payment_url)

        # Should redirect to checkout start
        self.assertEqual(response.status_code, 302)
        self.assertIn("checkout", response.url)

    def test_payment_after_order_cleanup_fails(self):
        """Payment attempt after order cleanup should fail gracefully"""
        # Delete the order (simulating cleanup)
        self.order.id
        self.order.delete()

        # Try to access payment page
        response = self.client.get(self.payment_url)

        # Should redirect to checkout start
        self.assertEqual(response.status_code, 302)
        self.assertIn("checkout", response.url)


class StripeCancelFlowTests(TestCase):
    """Test Stripe cancel flow"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.cancel_url = reverse("orders:stripe_cancel")

        # Create test order
        marca = Marca.objects.create(nombre="Test Marca")
        Zapato.objects.create(
            nombre="Test Shoe",
            precio=100,
            genero="Unisex",
            marca=marca,
            estaDisponible=True,
        )

        self.order = Order.objects.create(
            codigo_pedido="CANCEL123",
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

    def test_cancel_page_renders_correctly(self):
        """Cancel page should render properly"""
        response = self.client.get(self.cancel_url)

        # Should render cancel template
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/payment_cancel.html")

    def test_cancel_does_not_mark_order_paid(self):
        """Canceling payment should not mark order as paid"""
        # Set session
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session.save()

        # Visit cancel page
        response = self.client.get(self.cancel_url)
        self.assertEqual(response.status_code, 200)

        # Order should still be unpaid
        self.order.refresh_from_db()
        self.assertFalse(self.order.pagado)

        # Session should still exist (user can retry)
        self.assertIn("checkout_order_id", self.client.session)


class StripeMetadataEdgeCasesTests(TestCase):
    """Test edge cases with Stripe metadata"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.webhook_url = reverse("orders:stripe_webhook")
        self.webhook_secret = "whsec_test_secret_12345"

        # Create test order
        Marca.objects.create(nombre="Test Marca")
        self.order = Order.objects.create(
            codigo_pedido="META123",
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

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"})
    @patch("stripe.Webhook.construct_event")
    def test_webhook_with_empty_metadata(self, mock_construct_event):
        """Webhook with empty metadata should be handled gracefully"""
        from orders.test_helpers.stripe_mocks import (
            create_stripe_webhook_payload,
            generate_stripe_webhook_signature,
        )

        # Create event with empty metadata
        event = {
            "id": "evt_test_123",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "metadata": {},
                }
            },
        }
        mock_construct_event.return_value = event

        payload = create_stripe_webhook_payload(event)
        signature = generate_stripe_webhook_signature(payload, self.webhook_secret)

        # Send webhook
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=signature,
        )

        # Should return 200 (graceful handling)
        self.assertEqual(response.status_code, 200)

        # Order should not be affected
        self.order.refresh_from_db()
        self.assertFalse(self.order.pagado)

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"})
    @patch("stripe.Webhook.construct_event")
    def test_webhook_with_null_metadata(self, mock_construct_event):
        """Webhook with null metadata should be handled gracefully"""
        from orders.test_helpers.stripe_mocks import (
            create_stripe_webhook_payload,
            generate_stripe_webhook_signature,
        )

        # Create event with null metadata
        event = {
            "id": "evt_test_123",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "metadata": None,
                }
            },
        }
        mock_construct_event.return_value = event

        payload = create_stripe_webhook_payload(event)
        signature = generate_stripe_webhook_signature(payload, self.webhook_secret)

        # Send webhook
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=signature,
        )

        # Should return 200 (graceful handling)
        self.assertEqual(response.status_code, 200)

        # Order should not be affected
        self.order.refresh_from_db()
        self.assertFalse(self.order.pagado)


class StripeAmountMismatchTests(TestCase):
    """Test handling of amount mismatches"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.return_url = reverse("orders:stripe_return")

        # Create test order
        Marca.objects.create(nombre="Test Marca")
        self.order = Order.objects.create(
            codigo_pedido="AMOUNT123",
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

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.retrieve")
    def test_return_with_amount_mismatch_still_processes(self, mock_session_retrieve):
        """
        Amount mismatch should still process payment (trust Stripe).
        Note: In production, you might want to flag this for review.
        """
        # Setup mock with different amount
        mock_session = create_stripe_checkout_session_mock(
            self.order,
            payment_status="paid",
            amount=10000,  # 100 EUR instead of 126 EUR
        )
        mock_session_retrieve.return_value = mock_session

        # Set session
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session.save()

        # Send return request
        response = self.client.get(self.return_url + "?session_id=cs_test_mock123")

        # Should still redirect to success (trust Stripe)
        self.assertEqual(response.status_code, 302)
        self.assertIn("success", response.url)

        # Order should be marked paid
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)
