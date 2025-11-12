from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError
from customer.models import Customer


class CustomerModelTests(TestCase):
    def test_customer_creation(self):
        user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            password="TestPass123!",
            first_name="Test",
            last_name="User",
        )
        customer = Customer.objects.create(
            user=user, phone_number="612345678", address="Test Address 123", city="Madrid", postal_code="28001"
        )

        self.assertEqual(customer.user.email, "test@example.com")
        self.assertEqual(customer.phone_number, "612345678")
        self.assertEqual(customer.city, "Madrid")
        self.assertIsNotNone(customer.created_at)
        self.assertIsNotNone(customer.updated_at)

    def test_customer_one_to_one_relationship(self):
        user = User.objects.create_user(username="test@example.com", email="test@example.com", password="TestPass123!")
        customer = Customer.objects.create(
            user=user, phone_number="612345678", address="Test Address", city="Madrid", postal_code="28001"
        )

        self.assertEqual(user.customer, customer)
        self.assertEqual(customer.user, user)

    def test_customer_deletion_cascades(self):
        user = User.objects.create_user(username="test@example.com", email="test@example.com", password="TestPass123!")
        Customer.objects.create(
            user=user, phone_number="612345678", address="Test Address", city="Madrid", postal_code="28001"
        )

        user.delete()
        self.assertFalse(Customer.objects.filter(user_id=user.id).exists())

    def test_cannot_create_duplicate_customer_for_user(self):
        user = User.objects.create_user(username="test@example.com", email="test@example.com", password="TestPass123!")
        Customer.objects.create(
            user=user, phone_number="612345678", address="Test Address", city="Madrid", postal_code="28001"
        )

        with self.assertRaises(IntegrityError):
            Customer.objects.create(
                user=user, phone_number="987654321", address="Another Address", city="Barcelona", postal_code="08001"
            )

    def test_customer_updated_at_changes(self):
        user = User.objects.create_user(username="test@example.com", email="test@example.com", password="TestPass123!")
        customer = Customer.objects.create(
            user=user, phone_number="612345678", address="Test Address", city="Madrid", postal_code="28001"
        )

        original_updated_at = customer.updated_at
        customer.city = "Barcelona"
        customer.save()

        self.assertGreater(customer.updated_at, original_updated_at)
