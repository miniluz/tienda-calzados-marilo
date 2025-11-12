from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Marca",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField("Nombre de la Marca", max_length=100)),
                ("imagen", models.CharField("Imagen de la Marca", max_length=200, blank=True, null=True)),
                ("fechaCreacion", models.DateField("Fecha de Creación", auto_now_add=True)),
                ("fechaActualizacion", models.DateField("Fecha de Actualización", auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Categoria",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField("Nombre de la Categoría", max_length=100)),
                ("imagen", models.CharField("Imagen de la Categoría", max_length=200, blank=True, null=True)),
                ("fechaCreacion", models.DateField("Fecha de Creación", auto_now_add=True)),
                ("fechaActualizacion", models.DateField("Fecha de Actualización", auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Zapato",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField("Nombre", max_length=200)),
                ("descripcion", models.TextField("Descripción", blank=True)),
                ("precio", models.IntegerField("Precio")),
                ("precioOferta", models.IntegerField("Precio de Oferta", blank=True, null=True)),
                (
                    "genero",
                    models.CharField(
                        "Género",
                        max_length=50,
                        choices=[
                            ("Hombre", "Hombre"),
                            ("Mujer", "Mujer"),
                            ("Niño", "Niño"),
                            ("Niña", "Niña"),
                            ("Unisex", "Unisex"),
                        ],
                    ),
                ),
                ("color", models.CharField("Color", max_length=50, blank=True)),
                ("material", models.CharField("Material", max_length=100, blank=True)),
                ("estaDisponible", models.BooleanField("Disponible", default=True)),
                ("estaDestacado", models.BooleanField("Destacado", default=False)),
                ("fechaCreacion", models.DateField("Fecha de Creación", auto_now_add=True)),
                ("fechaActualizacion", models.DateField("Fecha de Actualización", auto_now=True)),
                (
                    "marca",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="zapatos", to="catalog.Marca"
                    ),
                ),
                (
                    "categoria",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="zapatos",
                        to="catalog.Categoria",
                    ),
                ),
            ],
            options={
                "ordering": ["-fechaCreacion"],
                "verbose_name": "Zapato",
                "verbose_name_plural": "Zapatos",
            },
        ),
        migrations.CreateModel(
            name="TallaZapato",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("talla", models.IntegerField("Talla")),
                ("stock", models.IntegerField("Stock", default=0)),
                ("fechaCreacion", models.DateField("Fecha de Creación", auto_now_add=True)),
                ("fechaActualizacion", models.DateField("Fecha de Actualización", auto_now=True)),
                (
                    "zapato",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="tallas", to="catalog.Zapato"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ImagenZapato",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("imagen", models.CharField("Imagen del Zapato", max_length=200, blank=True, null=True)),
                ("esPrincipal", models.BooleanField("Imagen Principal", default=False)),
                ("fechaCreacion", models.DateField("Fecha de Creación", auto_now_add=True)),
                ("fechaActualizacion", models.DateField("Fecha de Actualización", auto_now=True)),
                (
                    "zapato",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="imagenes", to="catalog.Zapato"
                    ),
                ),
            ],
        ),
    ]
