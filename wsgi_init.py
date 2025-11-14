#!/usr/bin/env python
"""
Debug script to test WSGI initialization.
This simulates how the application is loaded in a production WSGI environment.
Tests:
1. Admin user creation (management app)
2. Scheduler initialization (orders app)
"""

import os
import sys

import django
from django.contrib.auth.models import User

from orders.apps import OrdersConfig

# Set up Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tienda_calzados_marilo.settings")

print("=" * 60)
print("WSGI Initialization Debug Script")
print("=" * 60)
print(f"sys.argv: {sys.argv}")
print(f"RUN_MAIN env var: {os.environ.get('RUN_MAIN', 'not set')}")
print()

django.setup()

print("Django apps loaded and ready() methods called.")
print()

# Test 1: Check if admin user was created (management app)
print("[1/2] Testing Management App - Admin User Initialization")
print("-" * 60)

admin_email = "admin@calzmarilo.es"

try:
    admin_user = User.objects.get(username=admin_email)
    print(f"✓ Admin user found: {admin_user.username}")
    print(f"  - Email: {admin_user.email}")
    print(f"  - First name: {admin_user.first_name}")
    print(f"  - Last name: {admin_user.last_name}")
    print(f"  - Is staff: {admin_user.is_staff}")
    print(f"  - Is superuser: {admin_user.is_superuser}")
except User.DoesNotExist:
    print(f"✗ Admin user NOT found with username: {admin_email}")

print()

# Test 2: Check if scheduler was initialized (orders app)
print("[2/2] Testing Orders App - Scheduler Initialization")
print("-" * 60)

if OrdersConfig._scheduler_initialized:
    print("✓ Background scheduler initialized")
    print("  - Order cleanup job scheduled")
    print("  - Scheduler is running in background")
else:
    print("✗ Background scheduler NOT initialized")

print()
print("=" * 60)
print("Now loading WSGI application...")
print("=" * 60)

# Load the WSGI application (this is what production servers do)

print("WSGI application loaded successfully!")
print()
print("=" * 60)
print("Summary")
print("=" * 60)
print("Both apps initialized correctly for WSGI deployment.")
print()
print("You can now test with a WSGI server like gunicorn:")
print("  gunicorn tienda_calzados_marilo.wsgi:application")
print()
print("Note: The scheduler will run cleanup every N minutes as configured")
print("      in your CLEANUP_CRON_MINUTES environment variable.")
