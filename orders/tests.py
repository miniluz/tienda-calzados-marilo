from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Marca, TallaZapato, Zapato
from django.contrib.auth.models import User

from orders.forms import (
    BillingAddressForm,
    ContactInfoForm,
    ShippingAddressForm,
)
from orders.models import Order, OrderItem
from orders.utils import (
    calculate_order_prices,
    cleanup_expired_orders,
    generate_order_code,
    process_payment,
    reserve_stock,
    restore_stock,
)


class OrderCodeGenerationTest(TestCase):
    """Test order code generation"""

    def test_generate_order_code_length(self):
        """Order code should be at least 10 characters"""
        code = generate_order_code()
        self.assertGreaterEqual(len(code), 10)

    def test_generate_order_code_uniqueness(self):
        """Multiple calls should generate different codes"""
        codes = [generate_order_code() for _ in range(100)]
        self.assertEqual(len(codes), len(set(codes)))

    def test_generate_order_code_alphanumeric(self):
        """Order code should be alphanumeric"""
        code = generate_order_code()
        self.assertTrue(code.isalnum())


class PriceCalculationTest(TestCase):
    """Test price calculations"""

    def setUp(self):
        """Create test data"""
        marca = Marca.objects.create(nombre="Test Marca")
        self.zapato1 = Zapato.objects.create(
            nombre="Test Zapato 1",
            precio=100,
            precioOferta=80,
            genero="Unisex",
            marca=marca,
        )
        self.zapato2 = Zapato.objects.create(nombre="Test Zapato 2", precio=50, genero="Unisex", marca=marca)

    def test_calculate_prices_with_discount(self):
        """Should calculate prices correctly with discount"""
        cart_items = [{"zapato": self.zapato1, "talla": 42, "cantidad": 2}]

        result = calculate_order_prices(cart_items, delivery_cost=5.0, tax_rate=21.0)

        # Subtotal: 80 * 2 = 160
        # Delivery: 5
        # Tax base: 160 + 5 = 165
        # Tax: 165 * 0.21 = 34.65
        # Total: 160 + 5 + 34.65 = 199.65
        # Discount: (100 - 80) * 2 = 40

        self.assertEqual(result["subtotal"], Decimal("160.00"))
        self.assertEqual(result["coste_entrega"], Decimal("5.00"))
        self.assertEqual(result["impuestos"], Decimal("34.65"))
        self.assertEqual(result["total"], Decimal("199.65"))
        self.assertEqual(result["descuento"], Decimal("40.00"))

    def test_calculate_prices_without_discount(self):
        """Should calculate prices correctly without discount"""
        cart_items = [{"zapato": self.zapato2, "talla": 42, "cantidad": 1}]

        result = calculate_order_prices(cart_items, delivery_cost=5.0, tax_rate=21.0)

        # Subtotal: 50 * 1 = 50
        # Delivery: 5
        # Tax base: 50 + 5 = 55
        # Tax: 55 * 0.21 = 11.55
        # Total: 50 + 5 + 11.55 = 66.55
        # Discount: 0

        self.assertEqual(result["subtotal"], Decimal("50.00"))
        self.assertEqual(result["descuento"], Decimal("0.00"))
        self.assertEqual(result["total"], Decimal("66.55"))


class StockManagementTest(TestCase):
    """Test stock reservation and restoration"""

    def setUp(self):
        """Create test data"""
        marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(nombre="Test Zapato", precio=100, genero="Unisex", marca=marca)
        self.talla = TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=10)

    def test_reserve_stock(self):
        """Should reserve stock correctly"""
        cart_items = [{"zapato": self.zapato, "talla": 42, "cantidad": 3}]

        result = reserve_stock(cart_items)

        self.assertTrue(result)
        self.talla.refresh_from_db()
        self.assertEqual(self.talla.stock, 7)

    def test_reserve_stock_insufficient(self):
        """Should raise error when insufficient stock"""
        cart_items = [{"zapato": self.zapato, "talla": 42, "cantidad": 15}]

        with self.assertRaises(ValueError):
            reserve_stock(cart_items)

        self.talla.refresh_from_db()
        self.assertEqual(self.talla.stock, 10)  # Stock unchanged

    def test_restore_stock(self):
        """Should restore stock correctly"""
        # Create order with items
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

        # Deduct stock first
        self.talla.stock -= 3
        self.talla.save()
        self.assertEqual(self.talla.stock, 7)

        # Restore stock
        restored_items = restore_stock(order)

        # Should return list with one item
        self.assertEqual(len(restored_items), 1)
        self.assertEqual(restored_items[0]["zapato_nombre"], "Test Zapato")
        self.assertEqual(restored_items[0]["talla"], 42)
        self.assertEqual(restored_items[0]["cantidad"], 3)

        # Stock should be restored
        self.talla.refresh_from_db()
        self.assertEqual(self.talla.stock, 10)


class PaymentProcessingTest(TestCase):
    """Test payment processing"""

    def setUp(self):
        """Create test data"""
        marca = Marca.objects.create(nombre="Test Marca")
        Zapato.objects.create(nombre="Test Zapato", precio=100, genero="Unisex", marca=marca)

        self.order = Order.objects.create(
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

    def test_payment_tarjeta(self):
        """Mock payment with tarjeta should succeed"""
        result = process_payment(self.order, "tarjeta")

        self.assertTrue(result["success"])
        self.assertIn("transaction_id", result)

    def test_payment_contrarembolso(self):
        """Payment with contrarembolso should succeed"""
        result = process_payment(self.order, "contrarembolso")

        self.assertTrue(result["success"])
        self.assertIn("COD", result["transaction_id"])


class CleanupExpiredOrdersTest(TestCase):
    """Test cleanup of expired orders"""

    def setUp(self):
        """Create test data"""
        marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(nombre="Test Zapato", precio=100, genero="Unisex", marca=marca)
        self.talla = TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=5)

    def test_cleanup_expired_orders(self):
        """Should clean up expired unpaid orders"""
        # Create an expired unpaid order
        expired_order = Order.objects.create(
            codigo_pedido="EXPIRED123",
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
            pedido=expired_order,
            zapato=self.zapato,
            talla=42,
            cantidad=2,
            precio_unitario=100,
            total=200,
        )

        # Make order old (25 minutes = beyond 20-minute reservation window)
        expired_order.fecha_creacion = timezone.now() - timezone.timedelta(minutes=25)
        expired_order.save()

        # Run cleanup
        result = cleanup_expired_orders()

        self.assertEqual(result["deleted_count"], 1)
        self.assertEqual(result["restored_items"], 1)

        # Check stock details - hierarchical structure
        self.assertEqual(len(result["stock_details"]), 1)
        shoe = result["stock_details"][0]
        self.assertEqual(shoe["zapato_nombre"], "Test Zapato")
        self.assertEqual(shoe["zapato_id"], self.zapato.id)
        self.assertEqual(len(shoe["tallas"]), 1)
        self.assertEqual(shoe["tallas"][0]["talla"], 42)
        self.assertEqual(shoe["tallas"][0]["cantidad"], 2)

        # Check stock was restored
        self.talla.refresh_from_db()
        self.assertEqual(self.talla.stock, 7)

        # Check order was deleted
        self.assertFalse(Order.objects.filter(codigo_pedido="EXPIRED123").exists())

    def test_cleanup_keeps_paid_orders(self):
        """Should not clean up paid orders"""
        # Create a paid order
        paid_order = Order.objects.create(
            codigo_pedido="PAID123",
            metodo_pago="tarjeta",
            pagado=True,
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

        # Make order old (25 minutes = beyond reservation window, but paid)
        paid_order.fecha_creacion = timezone.now() - timezone.timedelta(minutes=25)
        paid_order.save()

        # Run cleanup
        result = cleanup_expired_orders()

        self.assertEqual(result["deleted_count"], 0)

        # Check order still exists
        self.assertTrue(Order.objects.filter(codigo_pedido="PAID123").exists())


class FormValidationTest(TestCase):
    """Test form validation for contact, shipping and billing forms"""

    def test_contact_form_phone_validation_valid(self):
        """Phone number with 9 digits should be valid"""
        form_data = {
            "nombre": "Test",
            "apellido": "User",
            "email": "test@test.com",
            "telefono": "612345678",
        }
        form = ContactInfoForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_contact_form_phone_validation_invalid_length(self):
        """Phone number without 9 digits should be invalid"""
        form_data = {
            "nombre": "Test",
            "apellido": "User",
            "email": "test@test.com",
            "telefono": "12345",  # Too short
        }
        form = ContactInfoForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("telefono", form.errors)
        self.assertIn("9 dígitos", str(form.errors["telefono"]))

    def test_contact_form_phone_validation_invalid_non_numeric(self):
        """Phone number with non-numeric characters should be invalid"""
        form_data = {
            "nombre": "Test",
            "apellido": "User",
            "email": "test@test.com",
            "telefono": "61234567a",  # Has letter
        }
        form = ContactInfoForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("telefono", form.errors)

    def test_shipping_form_postal_code_validation_valid(self):
        """Postal code with 5 digits should be valid"""
        form_data = {
            "direccion_envio": "Calle Test 123",
            "ciudad_envio": "Sevilla",
            "codigo_postal_envio": "41001",
        }
        form = ShippingAddressForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_shipping_form_postal_code_validation_invalid_length(self):
        """Postal code without 5 digits should be invalid"""
        form_data = {
            "direccion_envio": "Calle Test 123",
            "ciudad_envio": "Sevilla",
            "codigo_postal_envio": "123",  # Too short
        }
        form = ShippingAddressForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("codigo_postal_envio", form.errors)
        self.assertIn("5 dígitos", str(form.errors["codigo_postal_envio"]))

    def test_shipping_form_postal_code_validation_invalid_non_numeric(self):
        """Postal code with non-numeric characters should be invalid"""
        form_data = {
            "direccion_envio": "Calle Test 123",
            "ciudad_envio": "Sevilla",
            "codigo_postal_envio": "4100A",  # Has letter
        }
        form = ShippingAddressForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("codigo_postal_envio", form.errors)

    def test_billing_form_always_requires_fields(self):
        """Billing form should always require all fields"""
        form_data = {
            "direccion_facturacion": "",
            "ciudad_facturacion": "",
            "codigo_postal_facturacion": "",
        }
        form = BillingAddressForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("direccion_facturacion", form.errors)
        self.assertIn("ciudad_facturacion", form.errors)
        self.assertIn("codigo_postal_facturacion", form.errors)

    def test_billing_form_postal_code_validation_valid(self):
        """Billing postal code with 5 digits should be valid"""
        form_data = {
            "direccion_facturacion": "Calle Test 123",
            "ciudad_facturacion": "Sevilla",
            "codigo_postal_facturacion": "41001",
        }
        form = BillingAddressForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_billing_form_postal_code_validation_invalid(self):
        """Billing postal code without 5 digits should be invalid"""
        form_data = {
            "direccion_facturacion": "Calle Test 123",
            "ciudad_facturacion": "Sevilla",
            "codigo_postal_facturacion": "123",
        }
        form = BillingAddressForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("codigo_postal_facturacion", form.errors)
        self.assertIn("5 dígitos", str(form.errors["codigo_postal_facturacion"]))


class OrderDetailAccessControlTest(TestCase):
    """Test access control for OrderDetailView - anyone with code can view"""

    def setUp(self):
        """Create test data"""
        # Create users
        self.user1 = User.objects.create_user(username="user1@test.com", email="user1@test.com", password="pass123")
        self.user2 = User.objects.create_user(username="user2@test.com", email="user2@test.com", password="pass123")
        self.staff_user = User.objects.create_user(
            username="staff@test.com", email="staff@test.com", password="pass123", is_staff=True
        )

        # Create anonymous order
        self.anonymous_order = Order.objects.create(
            codigo_pedido="ANON123",
            usuario=None,  # Anonymous order
            metodo_pago="tarjeta",
            pagado=True,
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Test",
            apellido="User",
            email="anon@test.com",
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )

        # Create registered user's order
        self.user1_order = Order.objects.create(
            codigo_pedido="USER1ORDER",
            usuario=self.user1,
            metodo_pago="tarjeta",
            pagado=True,
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Test",
            apellido="User",
            email="user1@test.com",
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )

    def test_anonymous_user_can_view_anonymous_order(self):
        """Anonymous user should be able to view anonymous order with code"""
        from django.test import Client

        client = Client()
        response = client.get(reverse("orders:order_detail", kwargs={"codigo": "ANON123"}))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_user_can_view_registered_user_order(self):
        """Anyone with the code can view any order (for email tracking)"""
        from django.test import Client

        client = Client()
        response = client.get(reverse("orders:order_detail", kwargs={"codigo": "USER1ORDER"}))
        self.assertEqual(response.status_code, 200)

    def test_registered_user_can_view_own_order(self):
        """Registered user should be able to view their own order"""
        from django.test import Client

        client = Client()
        client.login(username="user1@test.com", password="pass123")
        response = client.get(reverse("orders:order_detail", kwargs={"codigo": "USER1ORDER"}))
        self.assertEqual(response.status_code, 200)

    def test_registered_user_can_view_another_user_order(self):
        """Anyone with the code can view any order (for email tracking)"""
        from django.test import Client

        client = Client()
        client.login(username="user2@test.com", password="pass123")
        response = client.get(reverse("orders:order_detail", kwargs={"codigo": "USER1ORDER"}))
        self.assertEqual(response.status_code, 200)

    def test_staff_can_view_any_order(self):
        """Staff user should be able to view any order"""
        from django.test import Client

        client = Client()
        client.login(username="staff@test.com", password="pass123")

        # Can view anonymous order
        response = client.get(reverse("orders:order_detail", kwargs={"codigo": "ANON123"}))
        self.assertEqual(response.status_code, 200)

        # Can view registered user's order
        response = client.get(reverse("orders:order_detail", kwargs={"codigo": "USER1ORDER"}))
        self.assertEqual(response.status_code, 200)

    def test_registered_user_can_view_anonymous_order(self):
        """Registered user should be able to view anonymous order"""
        from django.test import Client

        client = Client()
        client.login(username="user1@test.com", password="pass123")
        response = client.get(reverse("orders:order_detail", kwargs={"codigo": "ANON123"}))
        self.assertEqual(response.status_code, 200)


class OrderCodeCollisionTest(TestCase):
    """Test order code generation collision handling"""

    @patch("orders.views.generate_order_code")
    def test_order_code_generation_handles_collisions(self, mock_generate):
        """Should retry when order code collision occurs"""
        from django.test import Client

        # Create existing order with a specific code
        Order.objects.create(
            codigo_pedido="COLLISION123",
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

        # Mock generate_order_code to return collision on first call, unique on second
        mock_generate.side_effect = ["COLLISION123", "UNIQUE123"]

        # Create test data
        marca = Marca.objects.create(nombre="Test Marca")
        zapato = Zapato.objects.create(
            nombre="Test Zapato",
            precio=100,
            genero="Unisex",
            marca=marca,
            estaDisponible=True,
        )
        TallaZapato.objects.create(zapato=zapato, talla=42, stock=10)

        # Attempt to create order via checkout (this should trigger the collision handling)
        client = Client()
        response = client.get(reverse("orders:checkout_start"))

        # Should succeed (status 302 redirect)
        self.assertEqual(response.status_code, 302)

        # Should have called generate_order_code twice (once for collision, once for success)
        self.assertEqual(mock_generate.call_count, 2)

        # New order should exist with unique code
        self.assertTrue(Order.objects.filter(codigo_pedido="UNIQUE123").exists())

        # Old order should still exist
        self.assertTrue(Order.objects.filter(codigo_pedido="COLLISION123").exists())


class OrderLookupFormTest(TestCase):
    """Test OrderLookupForm validation"""

    def test_form_valid_with_alphanumeric_code(self):
        """Form should be valid with alphanumeric code"""
        from orders.forms import OrderLookupForm

        form_data = {"codigo_pedido": "ABC123DEF456"}
        form = OrderLookupForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_converts_to_uppercase(self):
        """Form should convert code to uppercase"""
        from orders.forms import OrderLookupForm

        form_data = {"codigo_pedido": "abc123def456"}
        form = OrderLookupForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["codigo_pedido"], "ABC123DEF456")

    def test_form_strips_whitespace(self):
        """Form should strip leading/trailing whitespace"""
        from orders.forms import OrderLookupForm

        form_data = {"codigo_pedido": "  ABC123  "}
        form = OrderLookupForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["codigo_pedido"], "ABC123")

    def test_form_invalid_with_special_characters(self):
        """Form should be invalid with special characters"""
        from orders.forms import OrderLookupForm

        form_data = {"codigo_pedido": "ABC-123-DEF"}
        form = OrderLookupForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("codigo_pedido", form.errors)
        self.assertIn("alfanumérico", str(form.errors["codigo_pedido"]).lower())

    def test_form_invalid_with_too_short_code(self):
        """Form should be invalid with code shorter than 5 characters"""
        from orders.forms import OrderLookupForm

        form_data = {"codigo_pedido": "ABC1"}
        form = OrderLookupForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("codigo_pedido", form.errors)
        self.assertIn("5 caracteres", str(form.errors["codigo_pedido"]).lower())

    def test_form_invalid_with_empty_code(self):
        """Form should be invalid with empty code"""
        from orders.forms import OrderLookupForm

        form_data = {"codigo_pedido": ""}
        form = OrderLookupForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("codigo_pedido", form.errors)


class OrderLookupViewTest(TestCase):
    """Test OrderLookupView functionality - anyone with code can lookup"""

    def setUp(self):
        """Create test data"""
        # Create users
        self.user1 = User.objects.create_user(username="user1@test.com", email="user1@test.com", password="pass123")
        self.user2 = User.objects.create_user(username="user2@test.com", email="user2@test.com", password="pass123")
        self.staff_user = User.objects.create_user(
            username="staff@test.com", email="staff@test.com", password="pass123", is_staff=True
        )

        # Create anonymous order
        self.anonymous_order = Order.objects.create(
            codigo_pedido="ANON123",
            usuario=None,
            metodo_pago="tarjeta",
            pagado=True,
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Test",
            apellido="User",
            email="anon@test.com",
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )

        # Create user1's order
        self.user1_order = Order.objects.create(
            codigo_pedido="USER1ORDER",
            usuario=self.user1,
            metodo_pago="tarjeta",
            pagado=True,
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Test",
            apellido="User",
            email="user1@test.com",
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )

    def test_view_renders_on_get(self):
        """View should render the lookup form on GET request"""
        from django.test import Client

        client = Client()
        response = client.get(reverse("orders:order_lookup"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/order_lookup.html")
        self.assertIn("form", response.context)

    def test_valid_anonymous_order_redirects_for_anonymous_user(self):
        """Anonymous user should be able to lookup anonymous order"""
        from django.test import Client

        client = Client()
        response = client.post(reverse("orders:order_lookup"), {"codigo_pedido": "ANON123"})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("orders:order_detail", kwargs={"codigo": "ANON123"}))

    def test_valid_anonymous_order_redirects_for_authenticated_user(self):
        """Authenticated user should be able to lookup anonymous order"""
        from django.test import Client

        client = Client()
        client.login(username="user1@test.com", password="pass123")
        response = client.post(reverse("orders:order_lookup"), {"codigo_pedido": "ANON123"})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("orders:order_detail", kwargs={"codigo": "ANON123"}))

    def test_valid_own_order_redirects_for_owner(self):
        """User should be able to lookup their own order"""
        from django.test import Client

        client = Client()
        client.login(username="user1@test.com", password="pass123")
        response = client.post(reverse("orders:order_lookup"), {"codigo_pedido": "USER1ORDER"})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("orders:order_detail", kwargs={"codigo": "USER1ORDER"}))

    def test_anonymous_user_can_lookup_registered_user_order(self):
        """Anyone with the code can lookup any order (for email tracking)"""
        from django.test import Client

        client = Client()
        response = client.post(reverse("orders:order_lookup"), {"codigo_pedido": "USER1ORDER"})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("orders:order_detail", kwargs={"codigo": "USER1ORDER"}))

    def test_different_user_can_lookup_another_users_order(self):
        """Anyone with the code can lookup any order (for email tracking)"""
        from django.test import Client

        client = Client()
        client.login(username="user2@test.com", password="pass123")
        response = client.post(reverse("orders:order_lookup"), {"codigo_pedido": "USER1ORDER"})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("orders:order_detail", kwargs={"codigo": "USER1ORDER"}))

    def test_staff_can_lookup_any_order(self):
        """Staff user should be able to lookup any order"""
        from django.test import Client

        client = Client()
        client.login(username="staff@test.com", password="pass123")

        # Can lookup anonymous order
        response = client.post(reverse("orders:order_lookup"), {"codigo_pedido": "ANON123"})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("orders:order_detail", kwargs={"codigo": "ANON123"}))

        # Can lookup registered user's order
        response = client.post(reverse("orders:order_lookup"), {"codigo_pedido": "USER1ORDER"})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("orders:order_detail", kwargs={"codigo": "USER1ORDER"}))

    def test_nonexistent_order_shows_error(self):
        """Non-existent order code should show error message"""
        from django.test import Client

        client = Client()
        response = client.post(reverse("orders:order_lookup"), {"codigo_pedido": "NOTEXIST123"})
        self.assertEqual(response.status_code, 200)  # Stays on lookup page
        self.assertTemplateUsed(response, "orders/order_lookup.html")
        # Check error message
        messages_list = list(response.context["messages"])
        self.assertEqual(len(messages_list), 1)
        self.assertIn("No se encontró", str(messages_list[0]))

    def test_invalid_form_shows_validation_errors(self):
        """Invalid form data should show validation errors"""
        from django.test import Client

        client = Client()
        # Submit invalid code with special characters
        response = client.post(reverse("orders:order_lookup"), {"codigo_pedido": "ABC-123"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/order_lookup.html")
        self.assertIn("form", response.context)
        self.assertFalse(response.context["form"].is_valid())


class OrderLookupNavbarLinkTest(TestCase):
    """Test that Seguimiento de pedidos link appears in main navbar for all user types"""

    def setUp(self):
        """Create test users"""
        self.regular_user = User.objects.create_user(
            username="regular@test.com", email="regular@test.com", password="pass123"
        )
        self.staff_user = User.objects.create_user(
            username="staff@test.com", email="staff@test.com", password="pass123", is_staff=True
        )

    def test_navbar_link_appears_for_anonymous_user(self):
        """Seguimiento de pedidos link should appear in main navbar for anonymous users"""
        from django.test import Client

        client = Client()
        response = client.get(reverse("catalog:zapato_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("orders:order_lookup"))
        self.assertContains(response, "Seguimiento de pedidos")

    def test_navbar_link_appears_for_authenticated_user(self):
        """Seguimiento de pedidos link should appear in main navbar for authenticated non-staff users"""
        from django.test import Client

        client = Client()
        client.login(username="regular@test.com", password="pass123")
        response = client.get(reverse("catalog:zapato_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("orders:order_lookup"))
        self.assertContains(response, "Seguimiento de pedidos")

    def test_navbar_link_appears_for_staff_user(self):
        """Seguimiento de pedidos link should appear in main navbar for staff users"""
        from django.test import Client

        client = Client()
        client.login(username="staff@test.com", password="pass123")
        response = client.get(reverse("catalog:zapato_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("orders:order_lookup"))
        self.assertContains(response, "Seguimiento de pedidos")


class OrderEmailTest(TestCase):
    """Test email sending functionality for orders"""

    def setUp(self):
        """Create test data"""
        # Create users
        self.user_with_same_email = User.objects.create_user(
            username="user@test.com", email="user@test.com", password="pass123"
        )
        self.user_with_different_email = User.objects.create_user(
            username="user2@test.com", email="user2account@test.com", password="pass123"  # Different from order email
        )

        # Create marca for zapato
        self.marca = Marca.objects.create(nombre="Test Marca")

        # Create zapato with stock
        self.zapato = Zapato.objects.create(
            nombre="Test Shoe",
            descripcion="Test description",
            precio=Decimal("100.00"),
            marca=self.marca,
            estaDisponible=True,
        )
        TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=10)

    def test_confirmation_email_sent_after_payment(self):
        """Test that confirmation email is sent after successful payment"""
        from orders.emails import send_order_confirmation_email

        # Create paid order
        order = Order.objects.create(
            codigo_pedido="TEST123",
            usuario=None,
            metodo_pago="tarjeta",
            pagado=True,
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Test",
            apellido="User",
            email="customer@test.com",
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )

        # Clear mail outbox
        mail.outbox = []

        # Send confirmation email
        send_order_confirmation_email(order)

        # Test that one email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Verify email details
        sent_email = mail.outbox[0]
        self.assertIn("Confirmación de Pedido", sent_email.subject)
        self.assertIn("TEST123", sent_email.subject)
        self.assertEqual(sent_email.to, ["customer@test.com"])
        self.assertIn("TEST123", sent_email.body)
        # Check HTML version contains tracking link
        html_body = sent_email.alternatives[0][0]
        self.assertIn("/orders/TEST123/", html_body)

    def test_confirmation_email_sent_to_both_emails_when_different(self):
        """Test that confirmation email is sent to both contact and user email when different"""
        from orders.emails import send_order_confirmation_email

        # Create order with user that has different email
        order = Order.objects.create(
            codigo_pedido="TEST456",
            usuario=self.user_with_different_email,
            metodo_pago="tarjeta",
            pagado=True,
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Test",
            apellido="User",
            email="contact@test.com",  # Different from user's account email
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )

        # Clear mail outbox
        mail.outbox = []

        # Send confirmation email
        send_order_confirmation_email(order)

        # Test that one email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Verify it was sent to both emails
        sent_email = mail.outbox[0]
        self.assertIn("contact@test.com", sent_email.to)
        self.assertIn("user2account@test.com", sent_email.to)
        self.assertEqual(len(sent_email.to), 2)

    def test_confirmation_email_sent_once_when_same_email(self):
        """Test that confirmation email is sent only once when contact and user email are the same"""
        from orders.emails import send_order_confirmation_email

        # Create order with user that has same email
        order = Order.objects.create(
            codigo_pedido="TEST789",
            usuario=self.user_with_same_email,
            metodo_pago="tarjeta",
            pagado=True,
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Test",
            apellido="User",
            email="user@test.com",  # Same as user's account email
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )

        # Clear mail outbox
        mail.outbox = []

        # Send confirmation email
        send_order_confirmation_email(order)

        # Test that one email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Verify it was sent only to one email address
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.to, ["user@test.com"])
        self.assertEqual(len(sent_email.to), 1)

    def test_confirmation_email_sent_only_to_contact_for_anonymous_order(self):
        """Test that confirmation email is sent only to contact email for anonymous orders"""
        from orders.emails import send_order_confirmation_email

        # Create anonymous order
        order = Order.objects.create(
            codigo_pedido="ANON123",
            usuario=None,  # Anonymous
            metodo_pago="contrarembolso",
            pagado=True,
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Anonymous",
            apellido="User",
            email="anon@test.com",
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )

        # Clear mail outbox
        mail.outbox = []

        # Send confirmation email
        send_order_confirmation_email(order)

        # Test that one email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Verify it was sent only to contact email
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.to, ["anon@test.com"])
        self.assertEqual(len(sent_email.to), 1)

    def test_status_update_email_sent_when_admin_updates_status(self):
        """Test that status update email is sent when admin changes order status"""
        from orders.emails import send_order_status_update_email

        # Create order
        order = Order.objects.create(
            codigo_pedido="STATUS123",
            usuario=self.user_with_different_email,
            metodo_pago="tarjeta",
            pagado=True,
            estado="por_enviar",
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Test",
            apellido="User",
            email="contact@test.com",
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )

        # Clear mail outbox
        mail.outbox = []

        # Update status
        order.estado = "en_envio"
        order.save()

        # Send status update email
        send_order_status_update_email(order)

        # Test that one email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Verify email details
        sent_email = mail.outbox[0]
        self.assertIn("Actualización de Pedido", sent_email.subject)
        self.assertIn("STATUS123", sent_email.subject)
        self.assertIn("STATUS123", sent_email.body)
        # Check HTML version contains tracking link
        html_body = sent_email.alternatives[0][0]
        self.assertIn("/orders/STATUS123/", html_body)

    def test_status_update_email_sent_only_to_contact_email(self):
        """Test that status update email is sent ONLY to contact email, not user email"""
        from orders.emails import send_order_status_update_email

        # Create order with user that has different email
        order = Order.objects.create(
            codigo_pedido="STATUS456",
            usuario=self.user_with_different_email,
            metodo_pago="tarjeta",
            pagado=True,
            estado="por_enviar",
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Test",
            apellido="User",
            email="contact@test.com",  # Different from user's account email
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )

        # Clear mail outbox
        mail.outbox = []

        # Update status
        order.estado = "recibido"
        order.save()

        # Send status update email
        send_order_status_update_email(order)

        # Test that one email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Verify it was sent ONLY to contact email, not user email
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.to, ["contact@test.com"])
        self.assertNotIn("user2account@test.com", sent_email.to)
        self.assertEqual(len(sent_email.to), 1)

    def test_email_contains_spanish_content(self):
        """Test that emails are in Spanish"""
        from orders.emails import send_order_confirmation_email, send_order_status_update_email

        # Create order
        order = Order.objects.create(
            codigo_pedido="SPANISH123",
            usuario=None,
            metodo_pago="tarjeta",
            pagado=True,
            estado="por_enviar",
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

        # Clear mail outbox
        mail.outbox = []

        # Send confirmation email
        send_order_confirmation_email(order)

        # Check Spanish content in confirmation
        conf_email = mail.outbox[0]
        self.assertIn("Confirmación", conf_email.subject)
        self.assertIn("Calzados Marilo", conf_email.subject)

        # Clear and send status update
        mail.outbox = []
        order.estado = "en_envio"
        order.save()
        send_order_status_update_email(order)

        # Check Spanish content in status update
        status_email = mail.outbox[0]
        self.assertIn("Actualización", status_email.subject)
        self.assertIn("Calzados Marilo", status_email.subject)


class CleanupExpiredOrdersViewTest(TestCase):
    """Test CleanupExpiredOrdersView - admin-only cleanup endpoint"""

    def setUp(self):
        """Create test data"""
        # Create users
        self.regular_user = User.objects.create_user(
            username="regular@test.com", email="regular@test.com", password="pass123"
        )
        self.staff_user = User.objects.create_user(
            username="staff@test.com", email="staff@test.com", password="pass123", is_staff=True
        )

        # Create test shoe
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato1 = Zapato.objects.create(nombre="Nike Air Max", precio=100, genero="Unisex", marca=self.marca)
        self.zapato2 = Zapato.objects.create(nombre="Adidas Superstar", precio=80, genero="Unisex", marca=self.marca)
        self.talla1 = TallaZapato.objects.create(zapato=self.zapato1, talla=42, stock=10)
        self.talla2 = TallaZapato.objects.create(zapato=self.zapato2, talla=38, stock=5)

    def test_post_endpoint_works_for_staff(self):
        """Staff user should be able to POST to cleanup endpoint without 404"""
        from django.test import Client

        client = Client()
        client.login(username="staff@test.com", password="pass123")

        response = client.post(reverse("cleanup_expired_orders"))

        # Should redirect to dashboard (not 404)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("admin_dashboard"))

    def test_non_staff_user_redirected(self):
        """Non-staff user should be redirected to login"""
        from django.test import Client

        client = Client()
        client.login(username="regular@test.com", password="pass123")

        response = client.post(reverse("cleanup_expired_orders"))

        # Should redirect to login page (not allowed)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_anonymous_user_redirected(self):
        """Anonymous user should be redirected to login"""
        from django.test import Client

        client = Client()
        response = client.post(reverse("cleanup_expired_orders"))

        # Should redirect to login page
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_detailed_feedback_with_single_order(self):
        """Should display detailed stock restoration feedback"""
        from django.test import Client

        # Create expired order
        expired_order = Order.objects.create(
            codigo_pedido="EXPIRED123",
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
            pedido=expired_order, zapato=self.zapato1, talla=42, cantidad=3, precio_unitario=100, total=300
        )

        # Make order expired
        expired_order.fecha_creacion = timezone.now() - timezone.timedelta(minutes=25)
        expired_order.save()

        # Login as staff and trigger cleanup
        client = Client()
        client.login(username="staff@test.com", password="pass123")
        response = client.post(reverse("cleanup_expired_orders"), follow=True)

        # Check message contains details
        messages_list = list(response.context["messages"])
        self.assertEqual(len(messages_list), 1)
        message_text = str(messages_list[0])

        self.assertIn("1 pedido(s) eliminado(s)", message_text)
        self.assertIn("Nike Air Max", message_text)
        self.assertIn("Talla 42", message_text)
        self.assertIn("+3 unidad(es)", message_text)

    def test_detailed_feedback_with_multiple_orders(self):
        """Should aggregate stock restoration from multiple orders"""
        from django.test import Client

        # Create first expired order
        order1 = Order.objects.create(
            codigo_pedido="EXPIRED1",
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
        order1.fecha_creacion = timezone.now() - timezone.timedelta(minutes=25)
        order1.save()

        OrderItem.objects.create(
            pedido=order1, zapato=self.zapato1, talla=42, cantidad=2, precio_unitario=100, total=200
        )
        OrderItem.objects.create(pedido=order1, zapato=self.zapato2, talla=38, cantidad=1, precio_unitario=80, total=80)

        # Create second expired order with same shoe+size
        order2 = Order.objects.create(
            codigo_pedido="EXPIRED2",
            metodo_pago="tarjeta",
            pagado=False,
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="Test",
            apellido="User2",
            email="test2@test.com",
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )
        order2.fecha_creacion = timezone.now() - timezone.timedelta(minutes=25)
        order2.save()

        OrderItem.objects.create(
            pedido=order2, zapato=self.zapato1, talla=42, cantidad=3, precio_unitario=100, total=300
        )

        # Login as staff and trigger cleanup
        client = Client()
        client.login(username="staff@test.com", password="pass123")
        response = client.post(reverse("cleanup_expired_orders"), follow=True)

        # Check message contains aggregated details
        messages_list = list(response.context["messages"])
        self.assertEqual(len(messages_list), 1)
        message_text = str(messages_list[0])

        self.assertIn("2 pedido(s) eliminado(s)", message_text)
        # Nike Air Max should show aggregated quantity (2 + 3 = 5)
        self.assertIn("Nike Air Max", message_text)
        self.assertIn("Talla 42", message_text)
        self.assertIn("+5 unidad(es)", message_text)
        # Adidas should show its quantity
        self.assertIn("Adidas Superstar", message_text)
        self.assertIn("Talla 38", message_text)
        self.assertIn("+1 unidad(es)", message_text)

    def test_no_expired_orders_shows_info_message(self):
        """Should show info message when no orders to clean up"""
        from django.test import Client

        client = Client()
        client.login(username="staff@test.com", password="pass123")
        response = client.post(reverse("cleanup_expired_orders"), follow=True)

        # Check info message
        messages_list = list(response.context["messages"])
        self.assertEqual(len(messages_list), 1)
        message_text = str(messages_list[0])

        self.assertIn("No hay pedidos expirados", message_text)
