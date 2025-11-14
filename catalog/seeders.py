"""
Catalog seeder - creates sample data for shoes, brands, categories, sizes, and images

This module is automatically discovered and executed by: python manage.py seed
"""

import os
import random

from django.conf import settings
from django.core.files import File

from catalog.models import Categoria, Marca, TallaZapato, Zapato

# Seeder priority (lower = runs first)
PRIORITY = 10


def seed():
    """Main seeding function for the catalog app"""

    # Set random seed for reproducibility
    random.seed(42)

    # Clear existing data
    print("  Clearing existing catalog data...")

    # Delete orders first (OrderItem has PROTECT FK to Zapato)
    from orders.models import Order, OrderItem

    OrderItem.objects.all().delete()
    Order.objects.all().delete()

    # Now safe to delete catalog data
    TallaZapato.objects.all().delete()
    Zapato.objects.all().delete()
    Marca.objects.all().delete()
    Categoria.objects.all().delete()
    print("  Database cleared")

    # Configuration
    NUM_SHOES = 100

    # Load image file for brands and categories
    image_path = os.path.join(settings.BASE_DIR, "seed-data", "shoes-image.jpeg")
    image_file = None
    if os.path.exists(image_path):
        with open(image_path, "rb") as f:
            image_file = File(f, name="brand_category.jpeg")
            image_file.read()  # Load into memory

    # Seed brands
    print("  Creating brands...")
    brand_names = [
        "Nike",
        "Adidas",
        "Puma",
        "Reebok",
        "New Balance",
        "Converse",
        "Vans",
        "Fila",
    ]
    marcas = []
    for name in brand_names:
        if image_file and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                marca = Marca.objects.create(nombre=name, imagen=File(f, name=f"brand_{name.lower()}.jpeg"))
        else:
            marca = Marca.objects.create(nombre=name)
        marcas.append(marca)
    print(f"  Created {len(marcas)} brands")

    # Seed categories
    print("  Creating categories...")
    category_names = [
        "Deportivos",
        "Casuales",
        "Formales",
        "Botas",
        "Sandalias",
        "Zapatillas Running",
    ]
    categorias = []
    for name in category_names:
        if image_file and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                categoria = Categoria.objects.create(nombre=name, imagen=File(f, name=f"category_{name.lower()}.jpeg"))
        else:
            categoria = Categoria.objects.create(nombre=name)
        categorias.append(categoria)
    print(f"  Created {len(categorias)} categories")

    # Seed shoes
    print(f"  Creating {NUM_SHOES} shoes...")
    shoe_templates = [
        ("Air Max Runner", "Zapatilla deportiva con tecnología Air Max"),
        ("Ultraboost 22", "Zapatilla de running con amortiguación Boost"),
        ("Suede Classic", "Zapatilla casual icónica de gamuza"),
        ("Classic Leather", "Zapatilla clásica de cuero"),
        ("574 Core", "Zapatilla retro con comodidad moderna"),
        ("Chuck Taylor All Star", "Zapatilla clásica de lona alta"),
        ("Old Skool", "Zapatilla skate clásica con franja lateral"),
        ("Disruptor II", "Zapatilla chunky con estilo retro"),
        ("Court Vision Low", "Zapatilla de baloncesto inspirada en los 80s"),
        ("Stan Smith", "Zapatilla de tenis icónica minimalista"),
    ]

    colors = [
        "Negro",
        "Blanco",
        "Azul",
        "Rojo",
        "Verde",
        "Gris",
        "Marrón",
        "Rosa",
        "Amarillo",
        "Naranja",
    ]
    materials = ["Cuero", "Sintético", "Lona", "Gamuza", "Malla", "Textil"]
    genders = ["Hombre", "Mujer", "Niño", "Niña", "Unisex"]

    zapatos = []
    for i in range(NUM_SHOES):
        template = shoe_templates[i % len(shoe_templates)]
        nombre = f"{template[0]} {i + 1}"
        descripcion = f"{template[1]} - Modelo {i + 1}"

        precio = random.randint(40, 200)
        precio_oferta = random.choice([None, random.randint(30, precio - 10)]) if precio > 50 else None

        # 20% chance of being unavailable
        esta_disponible = random.random() > 0.2

        if os.path.exists(image_path):
            with open(image_path, "rb") as f:
                zapato = Zapato.objects.create(
                    nombre=nombre,
                    descripcion=descripcion,
                    precio=precio,
                    precioOferta=precio_oferta,
                    genero=random.choice(genders),
                    color=random.choice(colors),
                    material=random.choice(materials),
                    estaDisponible=esta_disponible,
                    estaDestacado=random.choice([True, False]),
                    marca=random.choice(marcas),
                    categoria=random.choice(categorias),
                    imagen=File(f, name=f"shoe_{i + 1}.jpeg"),
                )
        else:
            zapato = Zapato.objects.create(
                nombre=nombre,
                descripcion=descripcion,
                precio=precio,
                precioOferta=precio_oferta,
                genero=random.choice(genders),
                color=random.choice(colors),
                material=random.choice(materials),
                estaDisponible=esta_disponible,
                estaDestacado=random.choice([True, False]),
                marca=random.choice(marcas),
                categoria=random.choice(categorias),
            )
        zapatos.append(zapato)
    print(f"  Created {len(zapatos)} shoes")

    # Seed sizes and stock
    print("  Creating sizes and stock...")
    talla_count = 0
    available_sizes = [36, 37, 38, 39, 40, 41, 42, 43, 44, 45]

    for zapato in zapatos:
        # Each shoe gets 5-8 random sizes
        # and a 20% chance to have no stock
        no_stock = random.random() < 0.2
        num_sizes = 0 if no_stock else random.randint(5, 8)
        selected_sizes = random.sample(available_sizes, k=num_sizes)

        for talla in selected_sizes:
            TallaZapato.objects.create(zapato=zapato, talla=talla, stock=random.randint(5, 25))
            talla_count += 1

    print(f"  Created {talla_count} size entries")

    print("  Seeding complete!")
