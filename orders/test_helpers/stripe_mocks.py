"""
Stripe mock utilities for testing webhook handling, race conditions, and edge cases.
"""

import hashlib
import hmac
import json
import time
from unittest.mock import Mock


def generate_stripe_webhook_signature(payload, secret, timestamp=None):
    """
    Generate a valid Stripe webhook signature for testing.

    Args:
        payload: The webhook payload (bytes or str)
        secret: Webhook secret key
        timestamp: Unix timestamp (default: current time)

    Returns:
        String in format "t=timestamp,v1=signature"
    """
    if timestamp is None:
        timestamp = int(time.time())

    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
    signature = hmac.new(secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()

    return f"t={timestamp},v1={signature}"


def generate_invalid_stripe_webhook_signature(payload):
    """
    Generate an invalid Stripe webhook signature for testing rejection.

    Returns:
        String with invalid signature format
    """
    timestamp = int(time.time())
    return f"t={timestamp},v1=invalid_signature_12345"


def create_stripe_checkout_session_mock(
    order, session_id="cs_test_mock123", status="complete", payment_status="paid", amount=None
):
    """
    Create a mock Stripe Checkout Session object.

    Args:
        order: Order instance
        session_id: Session ID to use
        status: Session status ('complete', 'expired', 'open')
        payment_status: Payment status ('paid', 'unpaid', 'no_payment_required')
        amount: Amount in cents (default: order.total * 100)

    Returns:
        Mock object with Stripe session structure
    """
    if amount is None:
        amount = int(order.total * 100)

    mock_session = Mock()
    mock_session.id = session_id
    mock_session.status = status
    mock_session.payment_status = payment_status
    mock_session.amount_total = amount
    mock_session.currency = "eur"
    mock_session.metadata = {"order_id": str(order.id), "codigo_pedido": order.codigo_pedido}
    mock_session.url = f"https://checkout.stripe.com/{session_id}"
    mock_session.success_url = "http://testserver/orders/checkout/stripe/return/?session_id={CHECKOUT_SESSION_ID}"
    mock_session.cancel_url = "http://testserver/orders/checkout/stripe/cancel/"

    # Add payment_intent if paid
    if payment_status == "paid":
        mock_payment_intent = Mock()
        mock_payment_intent.id = f"pi_{session_id}"
        mock_payment_intent.status = "succeeded"
        mock_session.payment_intent = mock_payment_intent
    else:
        mock_session.payment_intent = None

    # Make mock behave like a dict for .get() method (views.py uses checkout_session.get("payment_status"))
    def mock_get(key, default=None):
        """Implement dict-like .get() method for Mock"""
        attrs = {
            "id": mock_session.id,
            "status": mock_session.status,
            "payment_status": mock_session.payment_status,
            "amount_total": mock_session.amount_total,
            "currency": mock_session.currency,
            "metadata": mock_session.metadata,
            "url": mock_session.url,
            "success_url": mock_session.success_url,
            "cancel_url": mock_session.cancel_url,
            "payment_intent": mock_session.payment_intent,
        }
        return attrs.get(key, default)

    mock_session.get = mock_get

    return mock_session


def create_stripe_webhook_event(event_type, order, session_id="cs_test_mock123", payment_intent_id=None):
    """
    Create a mock Stripe webhook event.

    Args:
        event_type: Event type (e.g., 'checkout.session.completed', 'payment_intent.succeeded')
        order: Order instance
        session_id: Checkout session ID
        payment_intent_id: Payment intent ID (optional)

    Returns:
        Dict representing a Stripe event
    """
    if payment_intent_id is None:
        payment_intent_id = f"pi_{session_id}"

    event = {
        "id": f"evt_test_{int(time.time())}",
        "object": "event",
        "api_version": "2023-10-16",
        "created": int(time.time()),
        "type": event_type,
        "livemode": False,
    }

    if event_type == "checkout.session.completed":
        event["data"] = {
            "object": {
                "id": session_id,
                "object": "checkout.session",
                "amount_total": int(order.total * 100),
                "currency": "eur",
                "customer": None,
                "metadata": {"order_id": str(order.id), "codigo_pedido": order.codigo_pedido},
                "payment_intent": payment_intent_id,
                "payment_status": "paid",
                "status": "complete",
            }
        }
    elif event_type == "payment_intent.succeeded":
        event["data"] = {
            "object": {
                "id": payment_intent_id,
                "object": "payment_intent",
                "amount": int(order.total * 100),
                "currency": "eur",
                "metadata": {"order_id": str(order.id), "codigo_pedido": order.codigo_pedido},
                "status": "succeeded",
            }
        }
    elif event_type == "charge.succeeded":
        event["data"] = {
            "object": {
                "id": f"ch_{session_id}",
                "object": "charge",
                "amount": int(order.total * 100),
                "currency": "eur",
                "metadata": {"order_id": str(order.id), "codigo_pedido": order.codigo_pedido},
                "status": "succeeded",
                "payment_intent": payment_intent_id,
            }
        }

    return event


def create_stripe_webhook_payload(event):
    """
    Create a JSON webhook payload from an event dict.

    Args:
        event: Event dict from create_stripe_webhook_event

    Returns:
        JSON string (bytes)
    """
    return json.dumps(event).encode("utf-8")


def mock_stripe_api_error(error_type="card_error", message="Your card was declined", code="card_declined"):
    """
    Create a mock Stripe API error for testing error handling.

    Args:
        error_type: Type of error ('card_error', 'api_error', 'invalid_request_error')
        message: Error message
        code: Error code

    Returns:
        Exception with error attributes
    """
    # Note: stripe.error classes are not directly accessible in newer versions
    # Use generic Exception with attributes instead
    error = Exception(message)
    error.user_message = message
    error.code = code
    error.error_type = error_type
    return error


def create_expired_stripe_session_mock(order, session_id="cs_test_expired123"):
    """
    Create a mock for an expired Stripe Checkout Session.

    Args:
        order: Order instance
        session_id: Session ID to use

    Returns:
        Mock object representing expired session
    """
    mock_session = create_stripe_checkout_session_mock(
        order, session_id=session_id, status="expired", payment_status="unpaid"
    )
    return mock_session
