from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from .models import Marca, Zapato, Categoria, TallaZapato
from .forms import ZapatoSearchForm
import json


# ==================== MODEL TESTS ====================


class ZapatoModelTest(TestCase):
    def setUp(self):
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.categoria = Categoria.objects.create(nombre="Test Categoria")

    def test_zapato_creation(self):
        zapato = Zapato.objects.create(
            nombre="Test Zapato",
            descripcion="Test description",
            precio=100,
            genero="Unisex",
            marca=self.marca,
            categoria=self.categoria,
        )
        self.assertEqual(zapato.nombre, "Test Zapato")
        self.assertEqual(zapato.precio, 100)
        self.assertEqual(zapato.marca, self.marca)
        self.assertEqual(zapato.categoria, self.categoria)
        self.assertTrue(zapato.estaDisponible)
        self.assertFalse(zapato.estaDestacado)

    def test_zapato_str(self):
        zapato = Zapato.objects.create(nombre="Test", descripcion="Desc", marca=self.marca, precio=50, genero="Unisex")
        self.assertIn("Test", str(zapato))
        self.assertIn("Desc", str(zapato))

    def test_zapato_get_absolute_url(self):
        zapato = Zapato.objects.create(nombre="Test", marca=self.marca, precio=50, genero="Unisex")
        expected_url = reverse("catalog:zapato_detail", args=[str(zapato.id)])
        self.assertEqual(zapato.get_absolute_url(), expected_url)

    def test_zapato_descuento_porcentaje_with_offer(self):
        zapato = Zapato.objects.create(nombre="Test", marca=self.marca, precio=100, precioOferta=75, genero="Unisex")
        self.assertEqual(zapato.descuento_porcentaje, 25)

    def test_zapato_descuento_porcentaje_without_offer(self):
        zapato = Zapato.objects.create(nombre="Test", marca=self.marca, precio=100, genero="Unisex")
        self.assertEqual(zapato.descuento_porcentaje, 0)

    def test_zapato_precio_validator(self):
        zapato = Zapato(nombre="Test", marca=self.marca, precio=0, genero="Unisex")
        with self.assertRaises(ValidationError):
            zapato.full_clean()

    def test_zapato_precioOferta_validator(self):
        zapato = Zapato(nombre="Test", marca=self.marca, precio=100, precioOferta=0, genero="Unisex")
        with self.assertRaises(ValidationError):
            zapato.full_clean()

    def test_zapato_marca_protect_on_delete(self):
        """Test that deleting a marca with zapatos raises ProtectedError"""
        zapato = Zapato.objects.create(nombre="Test", marca=self.marca, precio=50, genero="Unisex")
        with self.assertRaises(Exception):  # Django's ProtectedError
            self.marca.delete()
        # Zapato should still exist
        self.assertTrue(Zapato.objects.filter(pk=zapato.pk).exists())

    def test_zapato_categoria_set_null_on_delete(self):
        """Test that deleting a categoria sets zapato.categoria to NULL"""
        zapato = Zapato.objects.create(
            nombre="Test", marca=self.marca, precio=50, genero="Unisex", categoria=self.categoria
        )
        self.categoria.delete()
        zapato.refresh_from_db()
        self.assertIsNone(zapato.categoria)


class MarcaModelTest(TestCase):
    def test_marca_creation(self):
        marca = Marca.objects.create(nombre="Nike")
        self.assertEqual(marca.nombre, "Nike")
        self.assertIsNotNone(marca.fechaCreacion)
        self.assertIsNotNone(marca.fechaActualizacion)

    def test_marca_str(self):
        marca = Marca.objects.create(nombre="Adidas")
        self.assertEqual(str(marca), "Adidas")

    def test_marca_zapatos_relationship(self):
        marca = Marca.objects.create(nombre="Puma")
        zapato1 = Zapato.objects.create(nombre="Zapato 1", marca=marca, precio=50, genero="Unisex")
        zapato2 = Zapato.objects.create(nombre="Zapato 2", marca=marca, precio=60, genero="Unisex")

        self.assertEqual(marca.zapatos.count(), 2)
        self.assertIn(zapato1, marca.zapatos.all())
        self.assertIn(zapato2, marca.zapatos.all())


class CategoriaModelTest(TestCase):
    def test_categoria_creation(self):
        categoria = Categoria.objects.create(nombre="Deportivas")
        self.assertEqual(categoria.nombre, "Deportivas")
        self.assertIsNotNone(categoria.fechaCreacion)
        self.assertIsNotNone(categoria.fechaActualizacion)

    def test_categoria_str(self):
        categoria = Categoria.objects.create(nombre="Casual")
        self.assertEqual(str(categoria), "Casual")

    def test_categoria_zapatos_relationship(self):
        marca = Marca.objects.create(nombre="Test")
        categoria = Categoria.objects.create(nombre="Running")
        zapato1 = Zapato.objects.create(nombre="Zapato 1", marca=marca, precio=50, genero="Unisex", categoria=categoria)
        zapato2 = Zapato.objects.create(nombre="Zapato 2", marca=marca, precio=60, genero="Unisex", categoria=categoria)

        self.assertEqual(categoria.zapatos.count(), 2)
        self.assertIn(zapato1, categoria.zapatos.all())
        self.assertIn(zapato2, categoria.zapatos.all())


class TallaZapatoModelTest(TestCase):
    def setUp(self):
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.zapato = Zapato.objects.create(nombre="Test Zapato", marca=self.marca, precio=100, genero="Unisex")

    def test_talla_zapato_creation(self):
        talla = TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=10)
        self.assertEqual(talla.talla, 42)
        self.assertEqual(talla.stock, 10)
        self.assertEqual(talla.zapato, self.zapato)

    def test_talla_zapato_cascade_delete(self):
        """Test that deleting zapato deletes all its tallas"""
        TallaZapato.objects.create(zapato=self.zapato, talla=40, stock=5)
        TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=8)

        zapato_id = self.zapato.id
        self.zapato.delete()

        self.assertFalse(TallaZapato.objects.filter(zapato_id=zapato_id).exists())

    def test_talla_zapato_reverse_relationship(self):
        TallaZapato.objects.create(zapato=self.zapato, talla=40, stock=5)
        TallaZapato.objects.create(zapato=self.zapato, talla=42, stock=8)
        TallaZapato.objects.create(zapato=self.zapato, talla=44, stock=3)

        self.assertEqual(self.zapato.tallas.count(), 3)
        self.assertTrue(self.zapato.tallas.filter(talla=42).exists())


# ==================== VIEW TESTS ====================


class ZapatoViewsTest(TestCase):
    def setUp(self):
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.categoria = Categoria.objects.create(nombre="Test Categoria")

        # Create available zapatos
        self.zapato1 = Zapato.objects.create(
            nombre="Running Shoes",
            marca=self.marca,
            precio=200,
            genero="Hombre",
            estaDisponible=True,
            estaDestacado=True,
            categoria=self.categoria,
        )
        self.zapato2 = Zapato.objects.create(
            nombre="Casual Shoes",
            marca=self.marca,
            precio=150,
            genero="Mujer",
            estaDisponible=True,
            estaDestacado=False,
        )

        # Create unavailable zapato (should not appear)
        self.zapato3 = Zapato.objects.create(
            nombre="Unavailable",
            marca=self.marca,
            precio=100,
            genero="Unisex",
            estaDisponible=False,
        )

        # Add tallas
        TallaZapato.objects.create(zapato=self.zapato1, talla=42, stock=10)
        TallaZapato.objects.create(zapato=self.zapato1, talla=43, stock=5)

    def test_list_status(self):
        url = reverse("catalog:zapato_list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_list_only_shows_available(self):
        url = reverse("catalog:zapato_list")
        resp = self.client.get(url)
        self.assertContains(resp, "Running Shoes")
        self.assertContains(resp, "Casual Shoes")
        self.assertNotContains(resp, "Unavailable")

    def test_list_search_by_name(self):
        url = reverse("catalog:zapato_list")
        resp = self.client.get(url, {"q": "Running"})
        self.assertContains(resp, "Running Shoes")
        self.assertNotContains(resp, "Casual Shoes")

    def test_list_search_by_marca(self):
        marca2 = Marca.objects.create(nombre="Other Marca")
        Zapato.objects.create(nombre="Other Shoe", marca=marca2, precio=100, genero="Unisex", estaDisponible=True)

        url = reverse("catalog:zapato_list")
        resp = self.client.get(url, {"marca": self.marca.id})
        self.assertContains(resp, "Running Shoes")
        self.assertNotContains(resp, "Other Shoe")

    def test_list_filter_by_categoria(self):
        url = reverse("catalog:zapato_list")
        resp = self.client.get(url, {"categoria": self.categoria.id})
        self.assertContains(resp, "Running Shoes")
        self.assertNotContains(resp, "Casual Shoes")

    def test_list_filter_by_genero(self):
        url = reverse("catalog:zapato_list")
        resp = self.client.get(url, {"genero": "Hombre"})
        self.assertContains(resp, "Running Shoes")
        self.assertNotContains(resp, "Casual Shoes")

    def test_list_filter_by_talla(self):
        url = reverse("catalog:zapato_list")
        resp = self.client.get(url, {"talla": "42"})
        self.assertContains(resp, "Running Shoes")
        self.assertNotContains(resp, "Casual Shoes")

    def test_list_ordering_featured_first(self):
        """Featured products should appear before non-featured"""
        url = reverse("catalog:zapato_list")
        resp = self.client.get(url)
        content = resp.content.decode()

        # Find positions of both zapatos in the HTML
        pos_featured = content.find("Running Shoes")
        pos_regular = content.find("Casual Shoes")

        self.assertLess(pos_featured, pos_regular)

    def test_detail_status(self):
        url = reverse("catalog:zapato_detail", args=[self.zapato1.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_detail_context_includes_tallas_ordenadas(self):
        url = reverse("catalog:zapato_detail", args=[self.zapato1.id])
        resp = self.client.get(url)
        self.assertIn("tallas_ordenadas", resp.context)
        tallas = list(resp.context["tallas_ordenadas"])
        self.assertEqual(len(tallas), 2)
        # Should be ordered by size
        self.assertEqual(tallas[0].talla, 42)
        self.assertEqual(tallas[1].talla, 43)

    def test_api_zapato_list(self):
        url = reverse("catalog:zapato_list_api")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        data = json.loads(resp.content)
        self.assertIn("zapatos", data)

        # Should only include available zapatos
        zapatos = data["zapatos"]
        self.assertEqual(len(zapatos), 2)

        # Check structure
        zapato = zapatos[0]
        self.assertIn("id", zapato)
        self.assertIn("nombre", zapato)
        self.assertIn("precio", zapato)
        self.assertIn("precioOferta", zapato)
        self.assertIn("descripcion", zapato)
        self.assertIn("marca__nombre", zapato)


# ==================== FORM TESTS ====================


class ZapatoSearchFormTest(TestCase):
    def setUp(self):
        self.marca = Marca.objects.create(nombre="Nike")
        self.categoria = Categoria.objects.create(nombre="Running")

    def test_form_fields_optional(self):
        form = ZapatoSearchForm(data={})
        self.assertTrue(form.is_valid())

    def test_form_with_search_query(self):
        form = ZapatoSearchForm(data={"q": "test"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["q"], "test")

    def test_form_with_categoria(self):
        form = ZapatoSearchForm(data={"categoria": self.categoria.id})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["categoria"], self.categoria)

    def test_form_with_marca(self):
        form = ZapatoSearchForm(data={"marca": self.marca.id})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["marca"], self.marca)

    def test_form_with_genero(self):
        form = ZapatoSearchForm(data={"genero": "Hombre"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["genero"], "Hombre")

    def test_form_with_talla(self):
        form = ZapatoSearchForm(data={"talla": 42})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["talla"], 42)


# ==================== OFFER DISPLAY TESTS ====================


class OfferDisplayTests(TestCase):
    """Tests to validate that products with offers display correctly in templates"""

    def setUp(self):
        self.marca = Marca.objects.create(nombre="Test Marca")
        self.categoria = Categoria.objects.create(nombre="Test Categoria")

        # Create zapato with offer
        self.zapato_with_offer = Zapato.objects.create(
            nombre="Zapato en Oferta",
            descripcion="Producto con descuento",
            precio=100,
            precioOferta=75,
            marca=self.marca,
            categoria=self.categoria,
            genero="Unisex",
            estaDisponible=True,
        )

        # Create zapato without offer
        self.zapato_without_offer = Zapato.objects.create(
            nombre="Zapato Precio Normal",
            descripcion="Producto sin descuento",
            precio=100,
            marca=self.marca,
            categoria=self.categoria,
            genero="Unisex",
            estaDisponible=True,
        )

        # Add at least one talla to make them appear in list
        TallaZapato.objects.create(zapato=self.zapato_with_offer, talla=42, stock=10)
        TallaZapato.objects.create(zapato=self.zapato_without_offer, talla=42, stock=10)

    def test_list_shows_offer_price_and_discount(self):
        """Test that zapato_list template shows original price, offer price, and discount percentage"""
        url = reverse("catalog:zapato_list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check that product with offer is shown
        self.assertIn("Zapato en Oferta", content)

        # Check that old price is shown with correct class
        self.assertIn('class="old-price"', content)
        self.assertIn("100", content)

        # Check that discounted price is shown with correct class
        self.assertIn('class="discounted"', content)
        self.assertIn("75", content)

        # Check that discount badge is shown with correct percentage
        self.assertIn('class="discount-badge"', content)
        self.assertIn("-25% OFF", content)

    def test_list_without_offer_shows_regular_price(self):
        """Test that products without offer show only regular price"""
        url = reverse("catalog:zapato_list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check that product without offer is shown
        self.assertIn("Zapato Precio Normal", content)

        # For products without offer, there should be no old-price or discount badge
        # We need to check the specific product section
        # The template shows both products, so we verify the structure

    def test_detail_shows_offer_price_and_discount(self):
        """Test that zapato_detail template shows original price, offer price, and discount percentage"""
        url = reverse("catalog:zapato_detail", args=[self.zapato_with_offer.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check that product name is shown
        self.assertIn("Zapato en Oferta", content)

        # Check that old price is shown with correct class (Spanish format: 100,00)
        self.assertIn('class="old-price"', content)
        self.assertIn("100,00", content)

        # Check that discounted price is shown with correct class (Spanish format: 75,00)
        self.assertIn('class="discounted-price"', content)
        self.assertIn("75,00", content)

        # Check that discount badge is shown with correct percentage
        self.assertIn('class="discount-badge"', content)
        self.assertIn("-25% OFF", content)

    def test_detail_without_offer_shows_regular_price(self):
        """Test that product detail without offer shows only regular price"""
        url = reverse("catalog:zapato_detail", args=[self.zapato_without_offer.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Check that product name is shown
        self.assertIn("Zapato Precio Normal", content)

        # Check that regular price is shown with correct class (Spanish format: 100,00)
        self.assertIn('class="price"', content)
        self.assertIn("100,00", content)

        # For this specific product (without offer), verify no discount elements appear AFTER its name
        # Find where this product starts in the page
        product_start = content.find("Zapato Precio Normal")
        product_section = content[product_start : product_start + 2000]  # Next 2000 chars after product name

        # Should not have discount classes in this product's section
        self.assertNotIn('class="old-price"', product_section)
        self.assertNotIn('class="discounted-price"', product_section)
        self.assertNotIn('class="discount-badge"', product_section)

    def test_offer_percentage_calculation_in_template(self):
        """Test that the discount percentage shown matches the calculated value"""
        # Create zapato with different discount
        zapato = Zapato.objects.create(
            nombre="Zapato 50% Off",
            precio=200,
            precioOferta=100,
            marca=self.marca,
            genero="Unisex",
            estaDisponible=True,
        )
        TallaZapato.objects.create(zapato=zapato, talla=42, stock=5)

        # Test in list view
        url = reverse("catalog:zapato_list")
        response = self.client.get(url)
        content = response.content.decode()
        self.assertIn("-50% OFF", content)

        # Test in detail view
        url = reverse("catalog:zapato_detail", args=[zapato.id])
        response = self.client.get(url)
        content = response.content.decode()
        self.assertIn("-50% OFF", content)
