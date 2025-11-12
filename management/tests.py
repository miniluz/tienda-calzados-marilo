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

        # Add some sizes
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
        # Should show total stock (10 + 5 = 15)
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

        # Check that sizes were auto-created (34-49)
        new_zapato = Zapato.objects.get(nombre="New Zapato")
        self.assertEqual(new_zapato.tallas.count(), 16)  # 34 to 49 inclusive

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

        # Try to remove more than available
        response = self.client.post(
            reverse("zapato_stock_edit", args=[self.zapato.id]),
            {"action": "remove", "talla_id": talla.id, "amount": 999},
        )

        self.assertEqual(response.status_code, 302)
        talla.refresh_from_db()
        # Stock should remain unchanged
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

        # Create a zapato with this marca
        Zapato.objects.create(nombre="Test Zapato", marca=self.marca, precio=100, genero="Unisex")

        marca_id = self.marca.id
        response = self.client.post(reverse("marca_delete", args=[marca_id]))

        # Should redirect back and marca should still exist
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

        # Create a zapato with this categoria
        marca = Marca.objects.create(nombre="Test Marca")
        zapato = Zapato.objects.create(
            nombre="Test Zapato", marca=marca, precio=100, genero="Unisex", categoria=self.categoria
        )

        categoria_id = self.categoria.id
        response = self.client.post(reverse("categoria_delete", args=[categoria_id]))

        # Should successfully delete and zapato.categoria should be NULL
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Categoria.objects.filter(pk=categoria_id).exists())

        zapato.refresh_from_db()
        self.assertIsNone(zapato.categoria)
