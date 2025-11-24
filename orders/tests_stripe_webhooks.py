"""
Tests for Stripe webhook handling, including signature verification,
idempotency, and various event types.
"""

import os
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse

from catalog.models import Marca, TallaZapato, Zapato
from orders.models import Order, OrderItem
from orders.test_helpers.stripe_mocks import (
    create_stripe_webhook_event,
    create_stripe_webhook_payload,
    generate_invalid_stripe_webhook_signature,
    generate_stripe_webhook_signature,
)


class StripeWebhookTests(TestCase):
    """Test basic Stripe webhook functionality"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.webhook_url = reverse("orders:stripe_webhook")
        self.webhook_secret = "whsec_test_secret_12345"

        # Create test product
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(
            nombre="Test Shoe",
            precio=100,
            genero="Unisex",
            marca=self.marca,
            estaDisponible=True,
        )
        TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=10)

        # Create test order
        self.order = Order.objects.create(
            codigo_pedido="WEBHOOK123",
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
            zapato=self.zapato,
            talla=42,
            cantidad=1,
            precio_unitario=100,
            total=100,
        )

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"})
    @patch("stripe.Webhook.construct_event")
    def test_webhook_valid_signature_marks_order_paid(self, mock_construct_event):
        """Valid webhook should mark order as paid"""
        # Create webhook event
        event = create_stripe_webhook_event("checkout.session.completed", self.order)
        mock_construct_event.return_value = event

        # Create payload and signature
        payload = create_stripe_webhook_payload(event)
        signature = generate_stripe_webhook_signature(payload, self.webhook_secret)

        # Send webhook
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=signature,
        )

        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"received": True})

        # Verify order is marked as paid
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"})
    @patch("stripe.Webhook.construct_event")
    def test_webhook_invalid_signature_returns_400(self, mock_construct_event):
        """Invalid webhook signature should return 400"""
        # Mock signature verification failure
        mock_construct_event.side_effect = Exception("Invalid signature")

        # Create payload
        event = create_stripe_webhook_event("checkout.session.completed", self.order)
        payload = create_stripe_webhook_payload(event)
        invalid_signature = generate_invalid_stripe_webhook_signature(payload)

        # Send webhook with invalid signature
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=invalid_signature,
        )

        # Verify response
        self.assertEqual(response.status_code, 400)

        # Verify order is NOT marked as paid
        self.order.refresh_from_db()
        self.assertFalse(self.order.pagado)

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"})
    def test_webhook_missing_signature_returns_400(self):
        """Webhook without signature should return 400"""
        event = create_stripe_webhook_event("checkout.session.completed", self.order)
        payload = create_stripe_webhook_payload(event)

        # Send webhook without signature header
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
        )

        # Verify response
        self.assertEqual(response.status_code, 400)

        # Verify order is NOT marked as paid
        self.order.refresh_from_db()
        self.assertFalse(self.order.pagado)

    @patch.dict(os.environ, {}, clear=True)
    def test_webhook_missing_secret_returns_400(self):
        """Webhook when secret not configured should return 400"""
        event = create_stripe_webhook_event("checkout.session.completed", self.order)
        payload = create_stripe_webhook_payload(event)
        signature = "t=123,v1=abc"

        # Send webhook
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=signature,
        )

        # Verify response
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "secret not configured", status_code=400)

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"})
    @patch("stripe.Webhook.construct_event")
    def test_webhook_for_nonexistent_order_returns_200(self, mock_construct_event):
        """Webhook for non-existent order should be idempotent (return 200)"""
        # Create event with non-existent order ID
        event = create_stripe_webhook_event("checkout.session.completed", self.order)
        event["data"]["object"]["metadata"]["order_id"] = "99999"
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

        # Should return 200 (idempotent)
        self.assertEqual(response.status_code, 200)

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"})
    @patch("stripe.Webhook.construct_event")
    def test_webhook_for_already_paid_order_is_idempotent(self, mock_construct_event):
        """Webhook for already paid order should be idempotent"""
        # Mark order as paid
        self.order.pagado = True
        self.order.save()

        # Create webhook event
        event = create_stripe_webhook_event("checkout.session.completed", self.order)
        mock_construct_event.return_value = event

        payload = create_stripe_webhook_payload(event)
        signature = generate_stripe_webhook_signature(payload, self.webhook_secret)

        # Clear mail outbox
        mail.outbox = []

        # Send webhook
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=signature,
        )

        # Verify response
        self.assertEqual(response.status_code, 200)

        # Verify order is still paid (no changes)
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)

        # Verify no duplicate email was sent
        self.assertEqual(len(mail.outbox), 0)

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"})
    @patch("stripe.Webhook.construct_event")
    def test_webhook_sends_confirmation_email(self, mock_construct_event):
        """Webhook should send confirmation email when marking order paid"""
        # Create webhook event
        event = create_stripe_webhook_event("checkout.session.completed", self.order)
        mock_construct_event.return_value = event

        payload = create_stripe_webhook_payload(event)
        signature = generate_stripe_webhook_signature(payload, self.webhook_secret)

        # Clear mail outbox
        mail.outbox = []

        # Send webhook
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=signature,
        )

        # Verify response
        self.assertEqual(response.status_code, 200)

        # Verify confirmation email was sent
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn("Confirmación de Pedido", sent_email.subject)
        self.assertIn(self.order.codigo_pedido, sent_email.subject)
        self.assertEqual(sent_email.to, [self.order.email])

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"})
    @patch("stripe.Webhook.construct_event")
    def test_webhook_payment_intent_succeeded_event(self, mock_construct_event):
        """Webhook should handle payment_intent.succeeded event"""
        # Create payment_intent.succeeded event
        event = create_stripe_webhook_event("payment_intent.succeeded", self.order)
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

        # Verify response
        self.assertEqual(response.status_code, 200)

        # Verify order is marked as paid
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"})
    @patch("stripe.Webhook.construct_event")
    def test_webhook_charge_succeeded_event(self, mock_construct_event):
        """Webhook should handle charge.succeeded event"""
        # Create charge.succeeded event
        event = create_stripe_webhook_event("charge.succeeded", self.order)
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

        # Verify response
        self.assertEqual(response.status_code, 200)

        # Verify order is marked as paid
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"})
    @patch("stripe.Webhook.construct_event")
    def test_webhook_without_order_id_in_metadata(self, mock_construct_event):
        """Webhook without order_id in metadata should return 200 (graceful handling)"""
        # Create event without order_id in metadata
        event = create_stripe_webhook_event("checkout.session.completed", self.order)
        event["data"]["object"]["metadata"] = {}
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
    def test_webhook_with_different_user_order(self, mock_construct_event):
        """Webhook should work for orders from authenticated users"""
        # Create user and associate order
        user = User.objects.create_user(
            username="testuser@example.com",
            email="testuser@example.com",
            password="pass123",
        )
        self.order.usuario = user
        self.order.save()

        # Create webhook event
        event = create_stripe_webhook_event("checkout.session.completed", self.order)
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

        # Verify response
        self.assertEqual(response.status_code, 200)

        # Verify order is marked as paid
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)


class StripeWebhookSecurityTests(TestCase):
    """Test Stripe webhook security features"""

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.webhook_url = reverse("orders:stripe_webhook")
        self.webhook_secret = "whsec_test_secret_12345"

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
            codigo_pedido="SECURITY123",
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
    def test_webhook_tampered_payload_rejected(self, mock_construct_event):
        """Webhook with tampered payload should be rejected"""
        # Create original event and signature
        event = create_stripe_webhook_event("checkout.session.completed", self.order)
        original_payload = create_stripe_webhook_payload(event)
        valid_signature = generate_stripe_webhook_signature(original_payload, self.webhook_secret)

        # Tamper with the payload
        tampered_event = event.copy()
        tampered_event["data"]["object"]["metadata"]["order_id"] = "99999"
        tampered_payload = create_stripe_webhook_payload(tampered_event)

        # Mock signature verification to detect tampering
        mock_construct_event.side_effect = Exception("Signature mismatch")

        # Send tampered webhook with original signature
        response = self.client.post(
            self.webhook_url,
            data=tampered_payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=valid_signature,
        )

        # Verify rejection
        self.assertEqual(response.status_code, 400)

        # Verify order is NOT marked as paid
        self.order.refresh_from_db()
        self.assertFalse(self.order.pagado)

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"})
    @patch("stripe.Webhook.construct_event")
    def test_webhook_replay_attack_handled(self, mock_construct_event):
        """Replayed webhook should be idempotent (not cause issues)"""
        # Create webhook event
        event = create_stripe_webhook_event("checkout.session.completed", self.order)
        mock_construct_event.return_value = event

        payload = create_stripe_webhook_payload(event)
        signature = generate_stripe_webhook_signature(payload, self.webhook_secret)

        # Send webhook first time
        response1 = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=signature,
        )
        self.assertEqual(response1.status_code, 200)
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)

        # Clear mail outbox
        mail.outbox = []

        # Replay the same webhook (replay attack)
        response2 = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=signature,
        )

        # Should still return 200 (idempotent)
        self.assertEqual(response2.status_code, 200)

        # Order should still be paid
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)

        # Should not send duplicate email
        self.assertEqual(len(mail.outbox), 0)

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"})
    @patch("stripe.Webhook.construct_event")
    def test_webhook_with_invalid_order_id_type(self, mock_construct_event):
        """Webhook with non-numeric order_id should be handled gracefully"""
        # Create event with invalid order_id
        event = create_stripe_webhook_event("checkout.session.completed", self.order)
        event["data"]["object"]["metadata"]["order_id"] = "not_a_number"
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
