"""
Customer seeder - creates sample data for users and customer profiles

This module is automatically discovered and executed by: python manage.py seed
"""

import random
import unicodedata

from django.contrib.auth.models import User

from customer.models import Customer


def remove_accents(text):
    """Remove accents from a string for use in email addresses"""
    nfd = unicodedata.normalize("NFD", text)
    return "".join(char for char in nfd if unicodedata.category(char) != "Mn")


def seed():
    """Main seeding function for the customer app"""

    # Set random seed for reproducibility
    random.seed(42)

    # Clear existing customer data (keeps superuser/staff)
    print("  Clearing existing customer data...")
    Customer.objects.filter(user__is_staff=False).delete()
    User.objects.filter(is_staff=False, is_superuser=False).delete()
    print("  Customer database cleared")

    # Configuration
    NUM_CUSTOMERS = 20

    # Spanish first names
    first_names_male = [
        "Carlos",
        "Javier",
        "Miguel",
        "David",
        "Antonio",
        "José",
        "Francisco",
        "Manuel",
        "Daniel",
        "Alejandro",
        "Pablo",
        "Pedro",
        "Luis",
        "Sergio",
        "Fernando",
    ]

    first_names_female = [
        "María",
        "Carmen",
        "Ana",
        "Isabel",
        "Laura",
        "Marta",
        "Elena",
        "Sara",
        "Lucía",
        "Paula",
        "Cristina",
        "Patricia",
        "Raquel",
        "Beatriz",
        "Silvia",
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
        "Álvarez",
        "Muñoz",
        "Romero",
        "Alonso",
        "Gutiérrez",
        "Navarro",
        "Torres",
        "Domínguez",
        "Vázquez",
        "Ramos",
    ]

    # Spanish cities with postal codes
    cities = [
        ("Madrid", "28"),
        ("Barcelona", "08"),
        ("Valencia", "46"),
        ("Sevilla", "41"),
        ("Zaragoza", "50"),
        ("Málaga", "29"),
        ("Murcia", "30"),
        ("Palma", "07"),
        ("Bilbao", "48"),
        ("Alicante", "03"),
        ("Córdoba", "14"),
        ("Valladolid", "47"),
        ("Granada", "18"),
        ("Salamanca", "37"),
        ("Toledo", "45"),
    ]

    # Street types for realistic addresses
    street_types = ["Calle", "Avenida", "Plaza", "Paseo", "Travesía"]
    street_names = [
        "Mayor",
        "Real",
        "Sol",
        "Libertad",
        "Constitución",
        "España",
        "Victoria",
        "Colón",
        "Paz",
        "San José",
        "Santa María",
        "del Carmen",
        "Gran Vía",
        "Reyes Católicos",
        "Cervantes",
    ]

    # Create customers
    print(f"  Creating {NUM_CUSTOMERS} customers...")
    customers = []

    for i in range(NUM_CUSTOMERS):
        # Alternate between male and female names
        if i % 2 == 0:
            first_name = random.choice(first_names_male)
        else:
            first_name = random.choice(first_names_female)

        last_name1 = random.choice(last_names)
        last_name2 = random.choice(last_names)
        last_name = f"{last_name1} {last_name2}"

        # Generate email (remove accents from name)
        email = f"{remove_accents(first_name).lower()}.{remove_accents(last_name1).lower()}{i + 1}@example.com"

        # Create user
        user = User.objects.create_user(
            username=email,
            email=email,
            password="example123*",
            first_name=first_name,
            last_name=last_name,
        )

        # Generate customer profile data
        city, postal_prefix = random.choice(cities)
        postal_code = f"{postal_prefix}{random.randint(100, 999):03d}"

        street_type = random.choice(street_types)
        street_name = random.choice(street_names)
        street_number = random.randint(1, 150)
        floor = random.randint(1, 8) if random.random() > 0.3 else None
        door = random.choice(["A", "B", "C", "D"]) if floor else None

        # Build address
        address = f"{street_type} {street_name}, {street_number}"
        if floor and door:
            address += f", {floor}º {door}"

        # Generate phone number (Spanish mobile)
        phone_number = f"6{random.randint(10000000, 99999999)}"

        # Create customer profile
        customer = Customer.objects.create(
            user=user,
            phone_number=phone_number,
            address=address,
            city=city,
            postal_code=postal_code,
        )
        customers.append(customer)

    print(f"  Created {len(customers)} customers with profiles")
    print("  Seeding complete!")
