"""
Tests for Stripe return flow and API failure handling.
"""

import os
from unittest.mock import Mock, patch

from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse

from catalog.models import Marca, TallaZapato, Zapato
from orders.models import Order, OrderItem
from orders.test_helpers.stripe_mocks import (
    create_expired_stripe_session_mock,
    create_stripe_checkout_session_mock,
    mock_stripe_api_error,
)


class StripeReturnViewTests(TestCase):
    """Test Stripe return view functionality"""

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
            codigo_pedido="RETURN123",
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
            pedido=self.order,
            zapato=zapato,
            talla=42,
            cantidad=1,
            precio_unitario=100,
            total=100,
        )

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.retrieve")
    def test_return_with_valid_session_id_marks_paid(self, mock_session_retrieve):
        """Valid session ID with paid status should mark order paid"""
        # Setup mock
        mock_session = create_stripe_checkout_session_mock(self.order, payment_status="paid")
        mock_session_retrieve.return_value = mock_session

        # Set session
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session.save()

        # Clear mail outbox
        mail.outbox = []

        # Send return request
        response = self.client.get(self.return_url + "?session_id=cs_test_mock123")

        # Should redirect to success page
        self.assertEqual(response.status_code, 302)
        self.assertIn("success", response.url)
        self.assertIn(self.order.codigo_pedido, response.url)

        # Order should be marked paid
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)

        # Email should be sent
        self.assertEqual(len(mail.outbox), 1)

        # Session should be cleared
        self.assertNotIn("checkout_order_id", self.client.session)

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.retrieve")
    def test_return_with_invalid_session_id_shows_validating(self, mock_session_retrieve):
        """Invalid session ID should show validating page"""
        # Mock Stripe API error
        mock_session_retrieve.side_effect = Exception("No such checkout session")

        # Set session
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session.save()

        # Send return request
        response = self.client.get(self.return_url + "?session_id=invalid_session")

        # Should show validating page (not crash)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/validating.html")

        # Order should NOT be marked paid
        self.order.refresh_from_db()
        self.assertFalse(self.order.pagado)

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.retrieve")
    def test_return_with_expired_session_shows_validating(self, mock_session_retrieve):
        """Expired session should show validating page"""
        # Setup mock for expired session
        mock_session = create_expired_stripe_session_mock(self.order)
        mock_session_retrieve.return_value = mock_session

        # Set session
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session.save()

        # Send return request
        response = self.client.get(self.return_url + "?session_id=cs_test_expired123")

        # Should show validating page (payment not completed)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/validating.html")

        # Order should NOT be marked paid
        self.order.refresh_from_db()
        self.assertFalse(self.order.pagado)

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.retrieve")
    def test_return_with_unpaid_session_shows_validating(self, mock_session_retrieve):
        """Unpaid session should show validating page"""
        # Setup mock for unpaid session
        mock_session = create_stripe_checkout_session_mock(self.order, payment_status="unpaid")
        mock_session_retrieve.return_value = mock_session

        # Set session
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session.save()

        # Send return request
        response = self.client.get(self.return_url + "?session_id=cs_test_mock123")

        # Should show validating page
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/validating.html")

        # Order should NOT be marked paid
        self.order.refresh_from_db()
        self.assertFalse(self.order.pagado)

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.retrieve")
    def test_return_clears_checkout_session_on_success(self, mock_session_retrieve):
        """Successful payment should clear checkout session"""
        # Setup mock
        mock_session = create_stripe_checkout_session_mock(self.order, payment_status="paid")
        mock_session_retrieve.return_value = mock_session

        # Set session
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session["checkout_descuento"] = "10.00"
        session.save()

        # Send return request
        response = self.client.get(self.return_url + "?session_id=cs_test_mock123")

        # Should redirect
        self.assertEqual(response.status_code, 302)

        # Session should be cleared
        self.assertNotIn("checkout_order_id", self.client.session)
        self.assertNotIn("checkout_descuento", self.client.session)

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    def test_return_with_no_session_shows_validating(self):
        """Return without order in session should show validating page"""
        # Send return request without session
        response = self.client.get(self.return_url + "?session_id=cs_test_mock123")

        # Should show validating page
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/validating.html")

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.retrieve")
    def test_return_already_paid_order_redirects_immediately(self, mock_session_retrieve):
        """Return for already paid order should redirect to success immediately"""
        # Mark order as paid
        self.order.pagado = True
        self.order.save()

        # Setup mock (even though it won't be called due to early return)
        mock_session = create_stripe_checkout_session_mock(self.order, payment_status="paid")
        mock_session_retrieve.return_value = mock_session

        # Set session
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session.save()

        # Clear mail outbox
        mail.outbox = []

        # Send return request
        response = self.client.get(self.return_url + "?session_id=cs_test_mock123")

        # Should redirect to success immediately
        self.assertEqual(response.status_code, 302)
        self.assertIn("success", response.url)

        # No duplicate email should be sent
        self.assertEqual(len(mail.outbox), 0)

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.retrieve")
    def test_return_with_codigo_in_querystring(self, mock_session_retrieve):
        """Return with codigo parameter should find order"""
        # Setup mock
        mock_session = create_stripe_checkout_session_mock(self.order, payment_status="paid")
        mock_session_retrieve.return_value = mock_session

        # Send return request with codigo (no session)
        response = self.client.get(self.return_url + f"?session_id=cs_test_mock123&codigo={self.order.codigo_pedido}")

        # Should redirect to success
        self.assertEqual(response.status_code, 302)
        self.assertIn("success", response.url)

        # Order should be marked paid
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)


class StripeAPIFailureTests(TestCase):
    """Test handling of Stripe API failures"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.payment_url = reverse("orders:checkout_payment")

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
            codigo_pedido="FAILURE123",
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
            pedido=self.order,
            zapato=zapato,
            talla=42,
            cantidad=1,
            precio_unitario=100,
            total=100,
        )

        # Set session
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session.save()

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.create")
    def test_checkout_session_create_api_error(self, mock_session_create):
        """Stripe API error during session creation should show error message"""
        # Mock API error
        mock_session_create.side_effect = mock_stripe_api_error(error_type="api_error", message="Service unavailable")

        # Send payment request
        response = self.client.post(self.payment_url, {"metodo_pago": "tarjeta"})

        # Should stay on payment page with error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Error al iniciar el pago")

        # Order should NOT be marked paid
        self.order.refresh_from_db()
        self.assertFalse(self.order.pagado)

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.create")
    def test_checkout_session_create_network_error(self, mock_session_create):
        """Network error during session creation should show error message"""
        # Mock network error
        mock_session_create.side_effect = ConnectionError("Failed to connect to Stripe")

        # Send payment request
        response = self.client.post(self.payment_url, {"metodo_pago": "tarjeta"})

        # Should stay on payment page with error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Error al iniciar el pago")

        # Order should NOT be marked paid
        self.order.refresh_from_db()
        self.assertFalse(self.order.pagado)

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.create")
    def test_checkout_session_create_timeout(self, mock_session_create):
        """Timeout during session creation should show error message"""
        # Mock timeout
        import socket

        mock_session_create.side_effect = socket.timeout("Request timed out")

        # Send payment request
        response = self.client.post(self.payment_url, {"metodo_pago": "tarjeta"})

        # Should stay on payment page with error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Error al iniciar el pago")

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.retrieve")
    def test_return_session_retrieve_api_error(self, mock_session_retrieve):
        """Stripe API error during session retrieval should show validating page"""
        # Mock API error
        mock_session_retrieve.side_effect = mock_stripe_api_error(error_type="api_error")

        # Set session
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session.save()

        # Send return request
        response = self.client.get(reverse("orders:stripe_return") + "?session_id=cs_test_mock123")

        # Should show validating page (graceful degradation)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/validating.html")

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.retrieve")
    def test_return_session_retrieve_network_error(self, mock_session_retrieve):
        """Network error during session retrieval should show validating page"""
        # Mock network error
        mock_session_retrieve.side_effect = ConnectionError("Network error")

        # Set session
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session.save()

        # Send return request
        response = self.client.get(reverse("orders:stripe_return") + "?session_id=cs_test_mock123")

        # Should show validating page
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/validating.html")

    @patch.dict(os.environ, {}, clear=True)
    def test_checkout_without_stripe_key_shows_error(self):
        """Checkout without Stripe key configured should show error"""
        # Send payment request
        response = self.client.post(self.payment_url, {"metodo_pago": "tarjeta"})

        # Should show error
        self.assertContains(response, "Configuración de Stripe incompleta")

        # Order should NOT be marked paid
        self.order.refresh_from_db()
        self.assertFalse(self.order.pagado)


class StripeDataIntegrityTests(TestCase):
    """Test data integrity between Stripe and orders"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.payment_url = reverse("orders:checkout_payment")

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
            codigo_pedido="INTEGRITY123",
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
    def test_checkout_session_amount_matches_order_total(self, mock_session_create):
        """Checkout session amount should match order total"""
        # Capture session creation call
        created_session = Mock()
        created_session.id = "cs_test_123"
        created_session.url = "https://checkout.stripe.com/test"
        mock_session_create.return_value = created_session

        # Send payment request
        response = self.client.post(self.payment_url, {"metodo_pago": "tarjeta"})

        # Should redirect to Stripe
        self.assertEqual(response.status_code, 302)

        # Verify session was created with correct amount
        mock_session_create.assert_called_once()
        call_kwargs = mock_session_create.call_args[1]

        # Amount should be in cents
        expected_amount = int(self.order.total * 100)
        self.assertEqual(call_kwargs["line_items"][0]["price_data"]["unit_amount"], expected_amount)

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.create")
    def test_checkout_session_metadata_contains_order_id(self, mock_session_create):
        """Checkout session metadata should contain order ID and code"""
        # Setup mock
        created_session = Mock()
        created_session.id = "cs_test_123"
        created_session.url = "https://checkout.stripe.com/test"
        mock_session_create.return_value = created_session

        # Send payment request
        response = self.client.post(self.payment_url, {"metodo_pago": "tarjeta"})

        # Should redirect
        self.assertEqual(response.status_code, 302)

        # Verify metadata
        call_kwargs = mock_session_create.call_args[1]
        self.assertEqual(call_kwargs["metadata"]["order_id"], str(self.order.id))
        self.assertEqual(call_kwargs["metadata"]["codigo_pedido"], self.order.codigo_pedido)

    @patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key"})
    @patch("stripe.checkout.Session.create")
    def test_checkout_session_currency_is_eur(self, mock_session_create):
        """Checkout session should use EUR currency"""
        # Setup mock
        created_session = Mock()
        created_session.id = "cs_test_123"
        created_session.url = "https://checkout.stripe.com/test"
        mock_session_create.return_value = created_session

        # Send payment request
        response = self.client.post(self.payment_url, {"metodo_pago": "tarjeta"})

        # Should redirect
        self.assertEqual(response.status_code, 302)

        # Verify currency
        call_kwargs = mock_session_create.call_args[1]
        self.assertEqual(call_kwargs["line_items"][0]["price_data"]["currency"], "eur")
