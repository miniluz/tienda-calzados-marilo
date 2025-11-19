from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from customer.models import Customer


class AdminDashboardTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username="admin@example.com", email="admin@example.com", password="AdminPass123!", is_staff=True
        )
        self.customer_user = User.objects.create_user(
            username="customer@example.com", email="customer@example.com", password="CustomerPass123!"
        )

    def test_dashboard_requires_staff(self):
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_customer_cannot_access_dashboard(self):
        self.client.login(username="customer@example.com", password="CustomerPass123!")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_access_dashboard(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panel de Administración")

    def test_dashboard_shows_counts(self):
        Customer.objects.create(
            user=self.customer_user, phone_number="612345678", address="Test", city="Madrid", postal_code="28001"
        )
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertContains(response, "Total de clientes:")
        self.assertContains(response, "Total de administradores:")


class CustomerManagementTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.admin_user = User.objects.create_user(
            username="admin@example.com", email="admin@example.com", password="AdminPass123!", is_staff=True
        )

        self.customer_user = User.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="CustomerPass123!",
            first_name="John",
            last_name="Doe",
        )
        self.customer = Customer.objects.create(
            user=self.customer_user,
            phone_number="612345678",
            address="Test Address 123",
            city="Madrid",
            postal_code="28001",
        )

    def test_customer_list_requires_staff(self):
        response = self.client.get(reverse("customer_list"))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_access_customer_list(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.get(reverse("customer_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "John Doe")

    def test_staff_can_view_customer_detail(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.get(reverse("customer_detail", args=[self.customer_user.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "customer@example.com")

    def test_staff_can_edit_customer(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.post(
            reverse("customer_edit", args=[self.customer_user.id]),
            {
                "email": "newemail@example.com",
                "first_name": "Jane",
                "last_name": "Smith",
                "phone_number": "987654321",
                "address": "New Address 456",
                "city": "Barcelona",
                "postal_code": "08001",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.customer_user.refresh_from_db()
        self.customer.refresh_from_db()

        self.assertEqual(self.customer_user.email, "newemail@example.com")
        self.assertEqual(self.customer_user.username, "newemail@example.com")
        self.assertEqual(self.customer_user.first_name, "Jane")
        self.assertEqual(self.customer.city, "Barcelona")

    def test_staff_can_delete_customer(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.post(reverse("customer_delete", args=[self.customer_user.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(email="customer@example.com").exists())


class AdminManagementTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.admin_user = User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="AdminPass123!",
            first_name="Admin",
            last_name="User",
            is_staff=True,
        )

        self.other_admin = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="OtherPass123!",
            first_name="Other",
            last_name="Admin",
            is_staff=True,
        )

    def test_admin_list_requires_staff(self):
        response = self.client.get(reverse("admin_list"))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_access_admin_list(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.get(reverse("admin_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin User")
        self.assertContains(response, "Other Admin")

    def test_staff_can_create_admin(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.post(
            reverse("admin_create"),
            {
                "email": "newadmin@example.com",
                "first_name": "New",
                "last_name": "Admin",
                "password1": "NewAdminPass123!",
                "password2": "NewAdminPass123!",
            },
        )
        self.assertEqual(response.status_code, 302)

        new_admin = User.objects.get(email="newadmin@example.com")
        self.assertTrue(new_admin.is_staff)
        self.assertEqual(new_admin.username, "newadmin@example.com")

    def test_staff_can_edit_admin(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.post(
            reverse("admin_edit", args=[self.other_admin.id]),
            {
                "email": "updated@example.com",
                "first_name": "Updated",
                "last_name": "Name",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.other_admin.refresh_from_db()
        self.assertEqual(self.other_admin.email, "updated@example.com")
        self.assertEqual(self.other_admin.username, "updated@example.com")
        self.assertEqual(self.other_admin.first_name, "Updated")

    def test_staff_can_delete_other_admin(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.post(reverse("admin_delete", args=[self.other_admin.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(email="other@example.com").exists())

    def test_staff_cannot_delete_self(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.post(reverse("admin_delete", args=[self.admin_user.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="admin@example.com").exists())


# ==================== ZAPATO MANAGEMENT TESTS ====================


class ZapatoManagementTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.admin_user = User.objects.create_user(
            username="admin@example.com", email="admin@example.com", password="AdminPass123!", is_staff=True
        )

        from catalog.models import Marca, Categoria, Zapato, TallaZapato

        self.marca = Marca.objects.create(nombre="Test Marca")
        self.categoria = Categoria.objects.create(nombre="Test Categoria")

        self.zapato = Zapato.objects.create(
            nombre="Test Zapato",
            descripcion="Test description",
            precio=100,
            genero="Unisex",
            marca=self.marca,
            categoria=self.categoria,
        )

        TallaZapato.objects.create(zapato=self.zapato, talla=40, stock=10)
        TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=5)

    def test_zapato_list_requires_staff(self):
        response = self.client.get(reverse("zapato_admin_list"))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_access_zapato_list(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.get(reverse("zapato_admin_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Zapato")

    def test_zapato_list_shows_stock_totals(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.get(reverse("zapato_admin_list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("zapatos", response.context)

    def test_staff_can_view_zapato_detail(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.get(reverse("zapato_admin_detail", args=[self.zapato.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Zapato")

    def test_staff_can_edit_zapato(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.post(
            reverse("zapato_admin_detail", args=[self.zapato.id]),
            {
                "nombre": "Updated Zapato",
                "descripcion": "Updated description",
                "marca": self.marca.id,
                "precio": 150,
                "genero": "Hombre",
                "estaDisponible": True,
                "estaDestacado": False,
            },
        )
        self.assertEqual(response.status_code, 302)

        self.zapato.refresh_from_db()
        self.assertEqual(self.zapato.nombre, "Updated Zapato")
        self.assertEqual(self.zapato.precio, 150)

    def test_staff_can_create_zapato(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")

        from catalog.models import Zapato

        initial_count = Zapato.objects.count()

        response = self.client.post(
            reverse("zapato_admin_create"),
            {
                "nombre": "New Zapato",
                "descripcion": "New description",
                "marca": self.marca.id,
                "precio": 200,
                "genero": "Mujer",
                "estaDisponible": True,
                "estaDestacado": False,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Zapato.objects.count(), initial_count + 1)

        new_zapato = Zapato.objects.get(nombre="New Zapato")
        self.assertEqual(new_zapato.tallas.count(), 16)

    def test_staff_can_delete_zapato(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")

        from catalog.models import Zapato

        zapato_id = self.zapato.id
        response = self.client.post(reverse("zapato_admin_delete", args=[zapato_id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Zapato.objects.filter(pk=zapato_id).exists())

    def test_stock_edit_requires_staff(self):
        response = self.client.get(reverse("zapato_stock_edit", args=[self.zapato.id]))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_access_stock_edit(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.get(reverse("zapato_stock_edit", args=[self.zapato.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Zapato")

    def test_stock_edit_add_action(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")

        talla = self.zapato.tallas.get(talla=40)
        original_stock = talla.stock

        response = self.client.post(
            reverse("zapato_stock_edit", args=[self.zapato.id]),
            {"action": "add", "talla_id": talla.id, "amount": 5},
        )

        self.assertEqual(response.status_code, 302)
        talla.refresh_from_db()
        self.assertEqual(talla.stock, original_stock + 5)

    def test_stock_edit_remove_action(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")

        talla = self.zapato.tallas.get(talla=40)
        original_stock = talla.stock

        response = self.client.post(
            reverse("zapato_stock_edit", args=[self.zapato.id]),
            {"action": "remove", "talla_id": talla.id, "amount": 3},
        )

        self.assertEqual(response.status_code, 302)
        talla.refresh_from_db()
        self.assertEqual(talla.stock, original_stock - 3)

    def test_stock_edit_prevent_negative_stock(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")

        talla = self.zapato.tallas.get(talla=40)
        original_stock = talla.stock

        response = self.client.post(
            reverse("zapato_stock_edit", args=[self.zapato.id]),
            {"action": "remove", "talla_id": talla.id, "amount": 999},
        )

        self.assertEqual(response.status_code, 302)
        talla.refresh_from_db()
        self.assertEqual(talla.stock, original_stock)

    def test_stock_edit_create_talla(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")

        from catalog.models import TallaZapato

        response = self.client.post(
            reverse("zapato_stock_edit", args=[self.zapato.id]),
            {"action": "create", "talla": 45, "stock_inicial": 20},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(TallaZapato.objects.filter(zapato=self.zapato, talla=45, stock=20).exists())

    def test_stock_edit_delete_talla(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")

        from catalog.models import TallaZapato

        talla = self.zapato.tallas.get(talla=40)
        talla_id = talla.id

        response = self.client.post(
            reverse("zapato_stock_edit", args=[self.zapato.id]), {"action": "delete", "talla_id": talla_id}
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(TallaZapato.objects.filter(pk=talla_id).exists())


# ==================== MARCA MANAGEMENT TESTS ====================


class MarcaManagementTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.admin_user = User.objects.create_user(
            username="admin@example.com", email="admin@example.com", password="AdminPass123!", is_staff=True
        )

        from catalog.models import Marca

        self.marca = Marca.objects.create(nombre="Test Marca")

    def test_marca_list_requires_staff(self):
        response = self.client.get(reverse("marca_list"))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_access_marca_list(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.get(reverse("marca_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Marca")

    def test_staff_can_create_marca(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")

        from catalog.models import Marca

        initial_count = Marca.objects.count()

        response = self.client.post(reverse("marca_create"), {"nombre": "New Marca"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Marca.objects.count(), initial_count + 1)
        self.assertTrue(Marca.objects.filter(nombre="New Marca").exists())

    def test_staff_can_edit_marca(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")

        response = self.client.post(reverse("marca_edit", args=[self.marca.id]), {"nombre": "Updated Marca"})

        self.assertEqual(response.status_code, 302)
        self.marca.refresh_from_db()
        self.assertEqual(self.marca.nombre, "Updated Marca")

    def test_staff_can_delete_marca_without_zapatos(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")

        from catalog.models import Marca

        marca_id = self.marca.id
        response = self.client.post(reverse("marca_delete", args=[marca_id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Marca.objects.filter(pk=marca_id).exists())

    def test_cannot_delete_marca_with_zapatos(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")

        from catalog.models import Marca, Zapato

        Zapato.objects.create(nombre="Test Zapato", marca=self.marca, precio=100, genero="Unisex")

        marca_id = self.marca.id
        response = self.client.post(reverse("marca_delete", args=[marca_id]))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Marca.objects.filter(pk=marca_id).exists())


# ==================== CATEGORIA MANAGEMENT TESTS ====================


class CategoriaManagementTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.admin_user = User.objects.create_user(
            username="admin@example.com", email="admin@example.com", password="AdminPass123!", is_staff=True
        )

        from catalog.models import Categoria

        self.categoria = Categoria.objects.create(nombre="Test Categoria")

    def test_categoria_list_requires_staff(self):
        response = self.client.get(reverse("categoria_list"))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_access_categoria_list(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")
        response = self.client.get(reverse("categoria_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Categoria")

    def test_staff_can_create_categoria(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")

        from catalog.models import Categoria

        initial_count = Categoria.objects.count()

        response = self.client.post(reverse("categoria_create"), {"nombre": "New Categoria"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Categoria.objects.count(), initial_count + 1)
        self.assertTrue(Categoria.objects.filter(nombre="New Categoria").exists())

    def test_staff_can_edit_categoria(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")

        response = self.client.post(
            reverse("categoria_edit", args=[self.categoria.id]), {"nombre": "Updated Categoria"}
        )

        self.assertEqual(response.status_code, 302)
        self.categoria.refresh_from_db()
        self.assertEqual(self.categoria.nombre, "Updated Categoria")

    def test_staff_can_delete_categoria_without_zapatos(self):
        self.client.login(username="admin@example.com", password="AdminPass123!")

        from catalog.models import Categoria

        categoria_id = self.categoria.id
        response = self.client.post(reverse("categoria_delete", args=[categoria_id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Categoria.objects.filter(pk=categoria_id).exists())

    def test_can_delete_categoria_with_zapatos_set_null(self):
        """Test that categoria can be deleted even with zapatos (SET_NULL behavior)"""
        self.client.login(username="admin@example.com", password="AdminPass123!")

        from catalog.models import Marca, Zapato, Categoria

        marca = Marca.objects.create(nombre="Test Marca")
        zapato = Zapato.objects.create(
            nombre="Test Zapato", marca=marca, precio=100, genero="Unisex", categoria=self.categoria
        )

        categoria_id = self.categoria.id
        response = self.client.post(reverse("categoria_delete", args=[categoria_id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Categoria.objects.filter(pk=categoria_id).exists())

        zapato.refresh_from_db()
        self.assertIsNone(zapato.categoria)


# ==================== CUSTOMER FILTERING TESTS ====================


class CustomerFilteringTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.admin_user = User.objects.create_user(
            username="admin@example.com", email="admin@example.com", password="AdminPass123!", is_staff=True
        )

        # Create test customers with different data
        self.customer1_user = User.objects.create_user(
            username="john.doe@example.com",
            email="john.doe@example.com",
            password="Pass123!",
            first_name="John",
            last_name="Doe",
        )
        self.customer1 = Customer.objects.create(
            user=self.customer1_user,
            phone_number="612345678",
            address="Calle Principal 123",
            city="Madrid",
            postal_code="28001",
        )

        self.customer2_user = User.objects.create_user(
            username="jane.smith@example.com",
            email="jane.smith@example.com",
            password="Pass123!",
            first_name="Jane",
            last_name="Smith",
        )
        self.customer2 = Customer.objects.create(
            user=self.customer2_user,
            phone_number="687654321",
            address="Avenida Secundaria 456",
            city="Barcelona",
            postal_code="08001",
        )

        self.customer3_user = User.objects.create_user(
            username="bob.garcia@test.com",
            email="bob.garcia@test.com",
            password="Pass123!",
            first_name="Bob",
            last_name="Garcia",
        )
        self.customer3 = Customer.objects.create(
            user=self.customer3_user,
            phone_number="611111111",
            address="Plaza Central 789",
            city="Madrid",
            postal_code="28002",
        )

        self.client.login(username="admin@example.com", password="AdminPass123!")

    def test_customer_filter_by_name(self):
        """Test filtering customers by first name"""
        response = self.client.get(reverse("customer_list"), {"nombre": "Jane"})
        self.assertEqual(response.status_code, 200)
        customers = response.context["customers"]
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0].user.first_name, "Jane")

    def test_customer_filter_by_last_name(self):
        """Test filtering customers by last name"""
        response = self.client.get(reverse("customer_list"), {"nombre": "Smith"})
        self.assertEqual(response.status_code, 200)
        customers = response.context["customers"]
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0].user.last_name, "Smith")

    def test_customer_filter_by_email(self):
        """Test filtering customers by email"""
        response = self.client.get(reverse("customer_list"), {"email": "john.doe"})
        self.assertEqual(response.status_code, 200)
        customers = response.context["customers"]
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0].user.email, "john.doe@example.com")

    def test_customer_filter_by_phone(self):
        """Test filtering customers by phone number"""
        response = self.client.get(reverse("customer_list"), {"telefono": "612345678"})
        self.assertEqual(response.status_code, 200)
        customers = response.context["customers"]
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0].phone_number, "612345678")

    def test_customer_filter_combined(self):
        """Test filtering customers with multiple filters"""
        response = self.client.get(reverse("customer_list"), {"nombre": "John", "email": "example.com"})
        self.assertEqual(response.status_code, 200)
        customers = response.context["customers"]
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0].user.first_name, "John")

    def test_customer_filter_empty_results(self):
        """Test filtering with no matching results"""
        response = self.client.get(reverse("customer_list"), {"nombre": "NonExistent"})
        self.assertEqual(response.status_code, 200)
        customers = response.context["customers"]
        self.assertEqual(len(customers), 0)

    def test_customer_filter_case_insensitive(self):
        """Test that filtering is case insensitive"""
        response = self.client.get(reverse("customer_list"), {"nombre": "jane"})
        self.assertEqual(response.status_code, 200)
        customers = response.context["customers"]
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0].user.first_name, "Jane")

        response = self.client.get(reverse("customer_list"), {"email": "JANE.SMITH"})
        self.assertEqual(response.status_code, 200)
        customers = response.context["customers"]
        self.assertEqual(len(customers), 1)

    def test_customer_filter_partial_match(self):
        """Test that filtering allows partial matches"""
        response = self.client.get(reverse("customer_list"), {"nombre": "o"})
        self.assertEqual(response.status_code, 200)
        customers = response.context["customers"]
        # Should match "John", "Bob", and "Doe"
        self.assertGreaterEqual(len(customers), 2)


# ==================== ORDER FILTERING TESTS ====================


class OrderFilteringTests(TestCase):
    """Test order filtering in management interface"""

    def setUp(self):
        self.client = Client()

        # Create staff user
        self.admin_user = User.objects.create_user(
            username="admin@example.com", email="admin@example.com", password="AdminPass123!", is_staff=True
        )

        # Create customer users
        self.user1 = User.objects.create_user(
            username="john.doe@example.com",
            email="john.doe@example.com",
            password="Pass123!",
            first_name="John",
            last_name="Doe",
        )

        self.user2 = User.objects.create_user(
            username="jane.smith@example.com",
            email="jane.smith@example.com",
            password="Pass123!",
            first_name="Jane",
            last_name="Smith",
        )

        # Create orders
        from orders.models import Order

        self.order1 = Order.objects.create(
            codigo_pedido="ORDER001",
            usuario=self.user1,
            metodo_pago="tarjeta",
            pagado=True,
            estado="por_enviar",
            subtotal=100,
            impuestos=21,
            coste_entrega=5,
            total=126,
            nombre="John",
            apellido="Doe",
            email="john.doe@example.com",
            telefono="123456789",
            direccion_envio="Test Address",
            ciudad_envio="Test City",
            codigo_postal_envio="12345",
            direccion_facturacion="Test Address",
            ciudad_facturacion="Test City",
            codigo_postal_facturacion="12345",
        )

        self.order2 = Order.objects.create(
            codigo_pedido="ORDER002",
            usuario=self.user2,
            metodo_pago="contrarembolso",
            pagado=True,
            estado="en_envio",
            subtotal=200,
            impuestos=42,
            coste_entrega=5,
            total=247,
            nombre="Jane",
            apellido="Smith",
            email="jane.smith@example.com",
            telefono="987654321",
            direccion_envio="Test Address 2",
            ciudad_envio="Test City 2",
            codigo_postal_envio="54321",
            direccion_facturacion="Test Address 2",
            ciudad_facturacion="Test City 2",
            codigo_postal_facturacion="54321",
        )

        # Anonymous order
        self.order3 = Order.objects.create(
            codigo_pedido="ORDER003",
            usuario=None,
            metodo_pago="tarjeta",
            pagado=True,
            estado="recibido",
            subtotal=150,
            impuestos=31.5,
            coste_entrega=5,
            total=186.5,
            nombre="Anonymous",
            apellido="User",
            email="anon@test.com",
            telefono="555555555",
            direccion_envio="Test Address 3",
            ciudad_envio="Test City 3",
            codigo_postal_envio="11111",
            direccion_facturacion="Test Address 3",
            ciudad_facturacion="Test City 3",
            codigo_postal_facturacion="11111",
        )

        self.client.login(username="admin@example.com", password="AdminPass123!")

    def test_order_filter_by_email_registered_user(self):
        """Test filtering orders by registered user email"""
        response = self.client.get(reverse("order_management_list"), {"email": "john.doe@example.com"})
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].codigo_pedido, "ORDER001")

    def test_order_filter_by_email_anonymous_order(self):
        """Test filtering orders by anonymous order email"""
        response = self.client.get(reverse("order_management_list"), {"email": "anon@test.com"})
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].codigo_pedido, "ORDER003")

    def test_order_filter_by_email_partial_match(self):
        """Test filtering orders by partial email match"""
        response = self.client.get(reverse("order_management_list"), {"email": "example.com"})
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 2)  # Should match ORDER001 and ORDER002

    def test_order_filter_by_name(self):
        """Test filtering orders by user name"""
        response = self.client.get(reverse("order_management_list"), {"nombre": "Jane"})
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].codigo_pedido, "ORDER002")

    def test_order_filter_by_last_name(self):
        """Test filtering orders by last name"""
        response = self.client.get(reverse("order_management_list"), {"nombre": "Doe"})
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].codigo_pedido, "ORDER001")

    def test_order_filter_by_anonymous_name(self):
        """Test filtering orders by anonymous user's name"""
        response = self.client.get(reverse("order_management_list"), {"nombre": "Anonymous"})
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].codigo_pedido, "ORDER003")

    def test_order_filter_by_estado(self):
        """Test filtering orders by status"""
        response = self.client.get(reverse("order_management_list"), {"estado": "en_envio"})
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].codigo_pedido, "ORDER002")

    def test_order_filter_combined(self):
        """Test filtering orders with multiple filters"""
        response = self.client.get(
            reverse("order_management_list"), {"email": "john.doe@example.com", "estado": "por_enviar"}
        )
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].codigo_pedido, "ORDER001")

    def test_order_filter_combined_no_match(self):
        """Test filtering orders with conflicting filters"""
        response = self.client.get(
            reverse("order_management_list"), {"email": "john.doe@example.com", "estado": "en_envio"}
        )
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 0)  # John's order is not in "en_envio" status

    def test_order_filter_case_insensitive(self):
        """Test that order filtering is case insensitive"""
        response = self.client.get(reverse("order_management_list"), {"nombre": "jane"})
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 1)

        response = self.client.get(reverse("order_management_list"), {"email": "JOHN.DOE"})
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 1)

    def test_order_filter_by_codigo_pedido_exact(self):
        """Test filtering orders by exact order code"""
        response = self.client.get(reverse("order_management_list"), {"codigo_pedido": "ORDER001"})
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].codigo_pedido, "ORDER001")

    def test_order_filter_by_codigo_pedido_partial(self):
        """Test filtering orders by partial order code"""
        response = self.client.get(reverse("order_management_list"), {"codigo_pedido": "ORDER"})
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 3)  # Should match all three orders

        response = self.client.get(reverse("order_management_list"), {"codigo_pedido": "001"})
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].codigo_pedido, "ORDER001")

    def test_order_filter_by_codigo_pedido_case_insensitive(self):
        """Test that order code filtering is case insensitive"""
        response = self.client.get(reverse("order_management_list"), {"codigo_pedido": "order002"})
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].codigo_pedido, "ORDER002")

    def test_order_filter_by_codigo_pedido_combined(self):
        """Test filtering orders by order code combined with other filters"""
        response = self.client.get(
            reverse("order_management_list"), {"codigo_pedido": "ORDER001", "estado": "por_enviar"}
        )
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].codigo_pedido, "ORDER001")

        # Test with conflicting filters
        response = self.client.get(
            reverse("order_management_list"), {"codigo_pedido": "ORDER001", "estado": "en_envio"}
        )
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 0)  # ORDER001 is not in "en_envio" status

    def test_order_filter_by_codigo_pedido_no_match(self):
        """Test filtering orders by non-existent order code"""
        response = self.client.get(reverse("order_management_list"), {"codigo_pedido": "NONEXISTENT"})
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 0)

    def test_order_list_shows_all_without_filter(self):
        """Test that order list shows all orders when no filter is applied"""
        response = self.client.get(reverse("order_management_list"))
        self.assertEqual(response.status_code, 200)
        orders = response.context["orders"]
        self.assertEqual(len(orders), 3)  # All 3 orders
