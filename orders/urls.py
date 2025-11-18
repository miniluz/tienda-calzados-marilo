from django.urls import path

from orders import views

app_name = "orders"

urlpatterns = [
    # Checkout flow
    path("checkout/", views.CheckoutStartView.as_view(), name="checkout_start"),
    path(
        "checkout/contact/",
        views.CheckoutContactView.as_view(),
        name="checkout_contact",
    ),
    path(
        "checkout/shipping/",
        views.CheckoutShippingView.as_view(),
        name="checkout_shipping",
    ),
    path(
        "checkout/billing/",
        views.CheckoutBillingView.as_view(),
        name="checkout_billing",
    ),
    path(
        "checkout/payment/",
        views.CheckoutPaymentView.as_view(),
        name="checkout_payment",
    ),
    # Stripe integration endpoints
    path("checkout/stripe/return/", views.StripeReturnView.as_view(), name="stripe_return"),
    path("checkout/stripe/cancel/", views.StripeCancelView.as_view(), name="stripe_cancel"),
    path("checkout/stripe/webhook/", views.StripeWebhookView.as_view(), name="stripe_webhook"),
    # Order views
    path("success/<str:codigo>/", views.OrderSuccessView.as_view(), name="order_success"),
    path("", views.OrderListView.as_view(), name="order_list"),
    path("lookup/", views.OrderLookupView.as_view(), name="order_lookup"),
    path("<str:codigo>/", views.OrderDetailView.as_view(), name="order_detail"),
]
