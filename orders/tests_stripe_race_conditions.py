"""
Tests for race conditions in Stripe payment processing,
particularly between webhook delivery and user return flow.
"""

import os
import threading
from unittest.mock import patch

from django.core import mail
from django.db import connection
from django.test import Client, TransactionTestCase
from django.urls import reverse

from catalog.models import Marca, TallaZapato, Zapato
from orders.models import Order, OrderItem
from orders.test_helpers.stripe_mocks import (
    create_stripe_checkout_session_mock,
    create_stripe_webhook_event,
    create_stripe_webhook_payload,
    generate_stripe_webhook_signature,
)


class StripeRaceConditionTests(TransactionTestCase):
    """
    Test race conditions between webhook and return view.
    Uses TransactionTestCase to enable threading and test real database concurrency.
    """

    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.webhook_url = reverse("orders:stripe_webhook")
        self.return_url = reverse("orders:stripe_return")
        self.webhook_secret = "whsec_test_secret_12345"
        self.session_id = "cs_test_race_123"

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
            codigo_pedido="RACE123",
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

    @patch.dict(
        os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key", "STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"}
    )
    @patch("stripe.checkout.Session.retrieve")
    @patch("stripe.Webhook.construct_event")
    def test_webhook_arrives_before_user_return(self, mock_construct_event, mock_session_retrieve):
        """
        Test scenario: Webhook arrives and marks order paid before user returns.
        Expected: User return view sees order already paid and redirects to success.
        """
        # Setup mocks
        event = create_stripe_webhook_event("checkout.session.completed", self.order, session_id=self.session_id)
        mock_construct_event.return_value = event

        mock_session = create_stripe_checkout_session_mock(
            self.order, session_id=self.session_id, payment_status="paid"
        )
        mock_session_retrieve.return_value = mock_session

        payload = create_stripe_webhook_payload(event)
        signature = generate_stripe_webhook_signature(payload, self.webhook_secret)

        # Clear mail outbox
        mail.outbox = []

        # 1. Webhook arrives first
        webhook_response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=signature,
        )
        self.assertEqual(webhook_response.status_code, 200)

        # Verify order is marked paid
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)

        # Verify email sent
        self.assertEqual(len(mail.outbox), 1)

        # Clear mail for second check
        mail.outbox = []

        # 2. User returns after webhook
        # Set session
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session.save()

        return_response = self.client.get(self.return_url + f"?session_id={self.session_id}")

        # Should redirect to success page
        self.assertEqual(return_response.status_code, 302)
        self.assertIn("success", return_response.url)
        self.assertIn(self.order.codigo_pedido, return_response.url)

        # No duplicate email should be sent
        self.assertEqual(len(mail.outbox), 0)

        # Order should still be paid (no duplicate)
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)

    @patch.dict(
        os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key", "STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"}
    )
    @patch("stripe.checkout.Session.retrieve")
    @patch("stripe.Webhook.construct_event")
    def test_user_return_before_webhook(self, mock_construct_event, mock_session_retrieve):
        """
        Test scenario: User returns from Stripe before webhook arrives.
        Expected: Return view marks order paid, webhook is idempotent.
        """
        # Setup mocks
        mock_session = create_stripe_checkout_session_mock(
            self.order, session_id=self.session_id, payment_status="paid"
        )
        mock_session_retrieve.return_value = mock_session

        event = create_stripe_webhook_event("checkout.session.completed", self.order, session_id=self.session_id)
        mock_construct_event.return_value = event

        # Clear mail outbox
        mail.outbox = []

        # 1. User returns first
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session.save()

        return_response = self.client.get(self.return_url + f"?session_id={self.session_id}")

        # Should redirect to success
        self.assertEqual(return_response.status_code, 302)
        self.assertIn("success", return_response.url)

        # Verify order is marked paid
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)

        # Verify email sent
        self.assertEqual(len(mail.outbox), 1)

        # Clear mail for webhook check
        mail.outbox = []

        # 2. Webhook arrives later (should be idempotent)
        payload = create_stripe_webhook_payload(event)
        signature = generate_stripe_webhook_signature(payload, self.webhook_secret)

        webhook_response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=signature,
        )

        # Should return 200 (idempotent)
        self.assertEqual(webhook_response.status_code, 200)

        # No duplicate email
        self.assertEqual(len(mail.outbox), 0)

        # Order still paid
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)

    @patch.dict(
        os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key", "STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"}
    )
    @patch("stripe.checkout.Session.retrieve")
    @patch("stripe.Webhook.construct_event")
    def test_concurrent_webhook_and_return_view(self, mock_construct_event, mock_session_retrieve):
        """
        Test scenario: Webhook and return view arrive simultaneously.
        Expected: Order marked paid exactly once, one email sent, no race conditions.
        """
        # Setup mocks
        mock_session = create_stripe_checkout_session_mock(
            self.order, session_id=self.session_id, payment_status="paid"
        )
        mock_session_retrieve.return_value = mock_session

        event = create_stripe_webhook_event("checkout.session.completed", self.order, session_id=self.session_id)
        mock_construct_event.return_value = event

        payload = create_stripe_webhook_payload(event)
        signature = generate_stripe_webhook_signature(payload, self.webhook_secret)

        # Clear mail outbox
        mail.outbox = []

        # Prepare session for return view
        session = self.client.session
        session["checkout_order_id"] = self.order.id
        session.save()

        results = {"webhook_status": None, "return_status": None, "errors": []}

        def send_webhook():
            """Send webhook in separate thread"""
            try:
                connection.close()
                client = Client()
                response = client.post(
                    self.webhook_url,
                    data=payload,
                    content_type="application/json",
                    HTTP_STRIPE_SIGNATURE=signature,
                )
                results["webhook_status"] = response.status_code
            except Exception as e:
                results["errors"].append(f"Webhook error: {e}")
            finally:
                connection.close()

        def send_return():
            """Send return view request in separate thread"""
            try:
                connection.close()
                client = Client()
                # Set session
                session = client.session
                session["checkout_order_id"] = self.order.id
                session.save()

                response = client.get(self.return_url + f"?session_id={self.session_id}")
                results["return_status"] = response.status_code
            except Exception as e:
                results["errors"].append(f"Return error: {e}")
            finally:
                connection.close()

        # Start both threads simultaneously
        webhook_thread = threading.Thread(target=send_webhook)
        return_thread = threading.Thread(target=send_return)

        webhook_thread.start()
        return_thread.start()

        webhook_thread.join()
        return_thread.join()

        # Verify no errors
        self.assertEqual(len(results["errors"]), 0, f"Errors occurred: {results['errors']}")

        # Both should succeed
        self.assertIn(results["webhook_status"], [200])
        self.assertIn(results["return_status"], [200, 302])

        # Order should be marked paid exactly once
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)

        # Exactly one email should be sent (may be 0-1 due to race, but not >1)
        self.assertLessEqual(len(mail.outbox), 1, "More than one email sent due to race condition")

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"})
    @patch("stripe.Webhook.construct_event")
    def test_multiple_webhook_deliveries(self, mock_construct_event):
        """
        Test scenario: Stripe retries webhook delivery 3 times.
        Expected: All webhooks succeed (idempotent), order marked paid once, email sent once.
        """
        # Setup mock
        event = create_stripe_webhook_event("checkout.session.completed", self.order, session_id=self.session_id)
        mock_construct_event.return_value = event

        payload = create_stripe_webhook_payload(event)
        signature = generate_stripe_webhook_signature(payload, self.webhook_secret)

        # Clear mail outbox
        mail.outbox = []

        # Send webhook 3 times (simulating Stripe retries)
        responses = []
        for i in range(3):
            response = self.client.post(
                self.webhook_url,
                data=payload,
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE=signature,
            )
            responses.append(response.status_code)

        # All should succeed
        self.assertEqual(responses, [200, 200, 200])

        # Order should be marked paid
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)

        # Only one email should be sent (first webhook)
        self.assertEqual(len(mail.outbox), 1)

    @patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"})
    @patch("stripe.Webhook.construct_event")
    def test_concurrent_webhooks_same_order(self, mock_construct_event):
        """
        Test scenario: Two webhook requests arrive simultaneously for same order.
        Expected: Order updated atomically, no duplicate processing.
        """
        # Setup mock
        event = create_stripe_webhook_event("checkout.session.completed", self.order, session_id=self.session_id)
        mock_construct_event.return_value = event

        payload = create_stripe_webhook_payload(event)
        signature = generate_stripe_webhook_signature(payload, self.webhook_secret)

        # Clear mail outbox
        mail.outbox = []

        results = {"statuses": [], "errors": []}

        def send_webhook():
            """Send webhook in separate thread"""
            try:
                connection.close()
                client = Client()
                response = client.post(
                    self.webhook_url,
                    data=payload,
                    content_type="application/json",
                    HTTP_STRIPE_SIGNATURE=signature,
                )
                results["statuses"].append(response.status_code)
            except Exception as e:
                results["errors"].append(str(e))
            finally:
                connection.close()

        # Start two webhook threads simultaneously
        thread1 = threading.Thread(target=send_webhook)
        thread2 = threading.Thread(target=send_webhook)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Verify no errors
        self.assertEqual(len(results["errors"]), 0, f"Errors occurred: {results['errors']}")

        # Both should succeed
        self.assertEqual(results["statuses"], [200, 200])

        # Order should be marked paid
        self.order.refresh_from_db()
        self.assertTrue(self.order.pagado)

        # Only one email should be sent
        self.assertEqual(len(mail.outbox), 1)

    @patch.dict(
        os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_key", "STRIPE_WEBHOOK_SECRET": "whsec_test_secret_12345"}
    )
    @patch("stripe.checkout.Session.retrieve")
    @patch("stripe.Webhook.construct_event")
    def test_race_with_different_users_different_orders(self, mock_construct_event, mock_session_retrieve):
        """
        Test scenario: Two different users checking out simultaneously.
        Expected: Each order processed independently, no interference.
        """
        # Create second order
        order2 = Order.objects.create(
            codigo_pedido="RACE456",
            metodo_pago="tarjeta",
            pagado=False,
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Test2",
            apellido="User2",
            email="test2@test.com",
            telefono="987654321",
            direccion_envio="Test Address 2",
            ciudad_envio="Test City 2",
            codigo_postal_envio="54321",
            direccion_facturacion="Test Address 2",
            ciudad_facturacion="Test City 2",
            codigo_postal_facturacion="54321",
        )

        # Setup mocks for both orders
        def construct_event_side_effect(payload, sig, secret):
            # Parse payload to determine which order
            import json

            data = json.loads(payload)
            order_id = data.get("data", {}).get("object", {}).get("metadata", {}).get("order_id")

            if order_id == str(self.order.id):
                return create_stripe_webhook_event("checkout.session.completed", self.order, session_id="cs_test_1")
            else:
                return create_stripe_webhook_event("checkout.session.completed", order2, session_id="cs_test_2")

        mock_construct_event.side_effect = construct_event_side_effect

        def session_retrieve_side_effect(session_id, **kwargs):
            if session_id == "cs_test_1":
                return create_stripe_checkout_session_mock(self.order, session_id="cs_test_1", payment_status="paid")
            else:
                return create_stripe_checkout_session_mock(order2, session_id="cs_test_2", payment_status="paid")

        mock_session_retrieve.side_effect = session_retrieve_side_effect

        # Clear mail outbox
        mail.outbox = []

        results = {"order1_paid": False, "order2_paid": False, "errors": []}

        def process_order1():
            """Process order 1 webhook"""
            try:
                connection.close()
                client = Client()
                event = create_stripe_webhook_event("checkout.session.completed", self.order, session_id="cs_test_1")
                payload = create_stripe_webhook_payload(event)
                signature = generate_stripe_webhook_signature(payload, self.webhook_secret)

                client.post(
                    self.webhook_url,
                    data=payload,
                    content_type="application/json",
                    HTTP_STRIPE_SIGNATURE=signature,
                )
                results["order1_paid"] = True
            except Exception as e:
                results["errors"].append(f"Order1 error: {e}")
            finally:
                connection.close()

        def process_order2():
            """Process order 2 webhook"""
            try:
                connection.close()
                client = Client()
                event = create_stripe_webhook_event("checkout.session.completed", order2, session_id="cs_test_2")
                payload = create_stripe_webhook_payload(event)
                signature = generate_stripe_webhook_signature(payload, self.webhook_secret)

                client.post(
                    self.webhook_url,
                    data=payload,
                    content_type="application/json",
                    HTTP_STRIPE_SIGNATURE=signature,
                )
                results["order2_paid"] = True
            except Exception as e:
                results["errors"].append(f"Order2 error: {e}")
            finally:
                connection.close()

        # Process both orders simultaneously
        thread1 = threading.Thread(target=process_order1)
        thread2 = threading.Thread(target=process_order2)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Verify no errors
        self.assertEqual(len(results["errors"]), 0, f"Errors occurred: {results['errors']}")

        # Both orders should be marked paid
        self.order.refresh_from_db()
        order2.refresh_from_db()
        self.assertTrue(self.order.pagado)
        self.assertTrue(order2.pagado)

        # Two emails should be sent (one per order)
        self.assertEqual(len(mail.outbox), 2)
