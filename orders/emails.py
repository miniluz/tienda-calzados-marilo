"""Email sending functions for order-related notifications."""

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from tienda_calzados_marilo.env import getEnvConfig


def get_tracking_url(order_code: str) -> str:
    """Generate the absolute tracking URL for an order."""
    env_config = getEnvConfig()
    base_url = env_config.WEBSITE_URL.rstrip("/")
    return f"{base_url}/orders/{order_code}/"


def send_order_confirmation_email(order) -> None:
    """
    Send order confirmation email after successful payment.

    Sends to:
    - Contact email (always)
    - User email (if user is authenticated and email differs from contact)
    """
    env_config = getEnvConfig()
    tracking_url = get_tracking_url(order.codigo_pedido)

    context = {
        "order": order,
        "tracking_url": tracking_url,
        "tax_rate": env_config.TAX_RATE,
    }

    html_message = render_to_string(
        "orders/emails/order_confirmation.html",
        context,
    )
    plain_message = strip_tags(html_message)

    subject = f"Confirmación de Pedido #{order.codigo_pedido} - Calzados Marilo"

    recipients = [order.email]

    if order.usuario and order.usuario.email and order.usuario.email != order.email:
        recipients.append(order.usuario.email)

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        html_message=html_message,
        fail_silently=False,
    )


def send_order_status_update_email(order) -> None:
    """
    Send email notification when order status is updated by admin.

    Only sends to contact email (not user email).
    """
    tracking_url = get_tracking_url(order.codigo_pedido)

    context = {
        "order": order,
        "tracking_url": tracking_url,
    }

    html_message = render_to_string(
        "orders/emails/order_status_update.html",
        context,
    )
    plain_message = strip_tags(html_message)

    subject = f"Actualización de Pedido #{order.codigo_pedido} - Calzados Marilo"

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.email],
        html_message=html_message,
        fail_silently=False,
    )
