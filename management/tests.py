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
