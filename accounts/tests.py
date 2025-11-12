from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from customer.models import Customer


class EmailAsUsernameTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse("register")
        self.login_url = reverse("login")

    def test_registration_sets_username_to_email(self):
        response = self.client.post(
            self.register_url,
            {
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "password1": "TestPass123!",
                "password2": "TestPass123!",
                "phone_number": "612345678",
                "address": "Test Address 123",
                "city": "Madrid",
                "postal_code": "28001",
            },
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="test@example.com")
        self.assertEqual(user.username, "test@example.com")
        self.assertEqual(user.first_name, "Test")
        self.assertEqual(user.last_name, "User")

    def test_login_with_email_works(self):
        User.objects.create_user(username="user@example.com", email="user@example.com", password="TestPass123!")

        response = self.client.post(self.login_url, {"username": "user@example.com", "password": "TestPass123!"})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_email_uniqueness_enforced(self):
        User.objects.create_user(username="existing@example.com", email="existing@example.com", password="TestPass123!")

        response = self.client.post(
            self.register_url,
            {
                "email": "existing@example.com",
                "first_name": "Test",
                "last_name": "User",
                "password1": "TestPass123!",
                "password2": "TestPass123!",
                "phone_number": "612345678",
                "address": "Test Address 123",
                "city": "Madrid",
                "postal_code": "28001",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe una cuenta con este correo electrónico")

    def test_phone_number_validation(self):
        response = self.client.post(
            self.register_url,
            {
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "password1": "TestPass123!",
                "password2": "TestPass123!",
                "phone_number": "12345",
                "address": "Test Address 123",
                "city": "Madrid",
                "postal_code": "28001",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El teléfono debe tener 9 dígitos")

    def test_postal_code_validation(self):
        response = self.client.post(
            self.register_url,
            {
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "password1": "TestPass123!",
                "password2": "TestPass123!",
                "phone_number": "612345678",
                "address": "Test Address 123",
                "city": "Madrid",
                "postal_code": "123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El código postal debe tener 5 dígitos")

    def test_password_hashing(self):
        self.client.post(
            self.register_url,
            {
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "password1": "TestPass123!",
                "password2": "TestPass123!",
                "phone_number": "612345678",
                "address": "Test Address 123",
                "city": "Madrid",
                "postal_code": "28001",
            },
        )

        user = User.objects.get(email="test@example.com")
        self.assertNotEqual(user.password, "TestPass123!")
        self.assertTrue(user.password.startswith("pbkdf2_sha256"))
        self.assertTrue(user.check_password("TestPass123!"))


class ProfileTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            password="TestPass123!",
            first_name="Test",
            last_name="User",
        )
        self.customer = Customer.objects.create(
            user=self.user, phone_number="612345678", address="Test Address 123", city="Madrid", postal_code="28001"
        )
        self.profile_url = reverse("profile")
        self.profile_edit_url = reverse("profile_edit")

    def test_profile_view_requires_authentication(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_authenticated_customer_can_view_profile(self):
        self.client.login(username="test@example.com", password="TestPass123!")
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test User")
        self.assertContains(response, "test@example.com")
        self.assertContains(response, "612345678")

    def test_authenticated_customer_can_edit_profile(self):
        self.client.login(username="test@example.com", password="TestPass123!")
        response = self.client.post(
            self.profile_edit_url,
            {
                "first_name": "Updated",
                "last_name": "Name",
                "phone_number": "987654321",
                "address": "New Address 456",
                "city": "Barcelona",
                "postal_code": "08001",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.user.refresh_from_db()
        self.customer.refresh_from_db()

        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(self.user.last_name, "Name")
        self.assertEqual(self.customer.phone_number, "987654321")
        self.assertEqual(self.customer.city, "Barcelona")

    def test_email_not_editable_in_profile(self):
        self.client.login(username="test@example.com", password="TestPass123!")
        response = self.client.get(self.profile_edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test@example.com")
        self.assertContains(response, "disabled")

    def test_profile_edit_requires_authentication(self):
        response = self.client.post(
            self.profile_edit_url,
            {
                "first_name": "Updated",
                "last_name": "Name",
                "phone_number": "987654321",
                "address": "New Address 456",
                "city": "Barcelona",
                "postal_code": "08001",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
