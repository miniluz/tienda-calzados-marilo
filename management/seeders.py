"""
Management seeder - creates sample data for admin users

This module is automatically discovered and executed by: python manage.py seed
"""

import random

from django.contrib.auth.models import User


def seed():
    """Main seeding function for the management app"""

    # Clear existing admin data (keeps superuser)
    print("  Clearing existing admin data...")
    User.objects.filter(is_staff=True, is_superuser=False).delete()
    print("  Admin database cleared")

    # Configuration
    NUM_ADMINS = 10

    # Spanish first names for admins
    first_names_male = [
        "Alberto",
        "Roberto",
        "Ricardo",
        "Emilio",
        "Marcos",
        "Jorge",
        "Ángel",
        "Raúl",
        "Víctor",
        "Andrés",
    ]

    first_names_female = [
        "Sonia",
        "Mónica",
        "Pilar",
        "Rosa",
        "Teresa",
        "Inés",
        "Nuria",
        "Gloria",
        "Dolores",
        "Mercedes",
    ]

    # Spanish surnames
    last_names = [
        "García",
        "Fernández",
        "González",
        "Rodríguez",
        "López",
        "Martínez",
        "Sánchez",
        "Pérez",
        "Gómez",
        "Martín",
        "Jiménez",
        "Ruiz",
        "Hernández",
        "Díaz",
        "Moreno",
    ]

    # Admin roles (for variety in names)
    roles = ["admin", "gerente", "staff", "empleado", "supervisor"]

    # Create admins
    print(f"  Creating {NUM_ADMINS} admin users...")
    admins = []

    for i in range(NUM_ADMINS):
        # Alternate between male and female names
        if i % 2 == 0:
            first_name = random.choice(first_names_male)
        else:
            first_name = random.choice(first_names_female)

        last_name1 = random.choice(last_names)
        last_name2 = random.choice(last_names)
        last_name = f"{last_name1} {last_name2}"

        # Generate email with role variety
        role = roles[i % len(roles)]
        email = f"{role}.{first_name.lower()}{i + 1}@calzmarilo.es"

        # Create admin user
        user = User.objects.create_user(
            username=email,
            email=email,
            password="example123*",
            first_name=first_name,
            last_name=last_name,
            is_staff=True,
        )

        admins.append(user)

    print(f"  Created {len(admins)} admin users")
    print("  Seeding complete!")
