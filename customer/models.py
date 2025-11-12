from django.contrib.auth.models import User
from django.db import models


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)

    # Contact info
    # Names and email are in the base User model.
    phone_number = models.CharField(max_length=9)

    # Delivery information
    address = models.TextField()
    city = models.TextField()
    postal_code = models.CharField(max_length=5)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
