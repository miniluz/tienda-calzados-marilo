from django.db import transaction

from .models import Marca, Categoria, Zapato, TallaZapato, ImagenZapato


def run():
    """
    Crea datos de ejemplo para Marca, Categoria, Zapato, TallaZapato e ImagenZapato.
    Ejecutar desde el shell de Django o importar y llamar catalog.seeders.run()
    """
    with transaction.atomic():
        # Marcas
        marcas = [
            {"nombre": "Nike", "imagen": "https://example.com/marcas/nike.png"},
            {"nombre": "Adidas", "imagen": "https://example.com/marcas/adidas.png"},
            {"nombre": "Puma", "imagen": "https://example.com/marcas/puma.png"},
            {"nombre": "Reebok", "imagen": "https://example.com/marcas/reebok.png"},
        ]
        marca_objs = {}
        for m in marcas:
            obj, _ = Marca.objects.get_or_create(nombre=m["nombre"], defaults={"imagen": m["imagen"]})
            marca_objs[m["nombre"]] = obj

        # Categorías
        categorias = [
            {"nombre": "Deportivos", "imagen": "https://example.com/cats/deportivos.png"},
            {"nombre": "Casuales", "imagen": "https://example.com/cats/casuales.png"},
            {"nombre": "Formales", "imagen": "https://example.com/cats/formales.png"},
            {"nombre": "Botas", "imagen": "https://example.com/cats/botas.png"},
        ]
        categoria_objs = {}
        for c in categorias:
            obj, _ = Categoria.objects.get_or_create(nombre=c["nombre"], defaults={"imagen": c["imagen"]})
            categoria_objs[c["nombre"]] = obj

        # Zapatos de ejemplo
        zapatos = [
            {
                "nombre": "Air Runner",
                "descripcion": "Zapatilla deportiva ligera para uso diario.",
                "precio": 80,
                "precioOferta": 65,
                "genero": "Hombre",
                "color": "Blanco/Azul",
                "material": "Sintético",
                "estaDisponible": True,
                "estaDestacado": True,
                "marca": "Nike",
                "categoria": "Deportivos",
                "tallas": [39, 40, 41, 42],
                "imagenes": [
                    "https://example.com/zapatos/air_runner_1.jpg",
                    "https://example.com/zapatos/air_runner_2.jpg",
                ],
            },
            {
                "nombre": "Classic Casual",
                "descripcion": "Zapato casual cómodo para el día a día.",
                "precio": 55,
                "precioOferta": None,
                "genero": "Mujer",
                "color": "Negro",
                "material": "Cuero sintético",
                "estaDisponible": True,
                "estaDestacado": False,
                "marca": "Adidas",
                "categoria": "Casuales",
                "tallas": [36, 37, 38, 39],
                "imagenes": [
                    "https://example.com/zapatos/classic_casual_1.jpg",
                ],
            },
            {
                "nombre": "Office Formal",
                "descripcion": "Zapato formal elegante para ocasiones especiales.",
                "precio": 120,
                "precioOferta": 99,
                "genero": "Hombre",
                "color": "Marrón",
                "material": "Cuero",
                "estaDisponible": True,
                "estaDestacado": False,
                "marca": "Reebok",
                "categoria": "Formales",
                "tallas": [40, 41, 42, 43],
                "imagenes": [
                    "https://example.com/zapatos/office_formal_1.jpg",
                    "https://example.com/zapatos/office_formal_2.jpg",
                ],
            },
        ]

        created_zapatos = []
        for z in zapatos:
            marca = marca_objs.get(z["marca"])
            categoria = categoria_objs.get(z["categoria"])
            zapato_obj, created = Zapato.objects.get_or_create(
                nombre=z["nombre"],
                defaults={
                    "descripcion": z["descripcion"],
                    "precio": z["precio"],
                    "precioOferta": z["precioOferta"],
                    "genero": z["genero"],
                    "color": z["color"],
                    "material": z["material"],
                    "estaDisponible": z["estaDisponible"],
                    "estaDestacado": z["estaDestacado"],
                    "marca": marca,
                    "categoria": categoria,
                },
            )
            if created:
                created_zapatos.append(zapato_obj)

            # Tallas y stock
            for talla in z["tallas"]:
                TallaZapato.objects.get_or_create(
                    zapato=zapato_obj,
                    talla=talla,
                    defaults={"stock": 10},
                )

            # Imágenes (la primera es principal)
            for idx, img in enumerate(z["imagenes"]):
                ImagenZapato.objects.get_or_create(
                    zapato=zapato_obj,
                    imagen=img,
                    defaults={"esPrincipal": idx == 0},
                )

        # Resumen
        print("Seed completado:")
        print(f"  Marcas: {Marca.objects.count()}")
        print(f"  Categorías: {Categoria.objects.count()}")
        print(f"  Zapatos: {Zapato.objects.count()}")
        print(f"  Tallas: {TallaZapato.objects.count()}")
        print(f"  Imágenes: {ImagenZapato.objects.count()}")
