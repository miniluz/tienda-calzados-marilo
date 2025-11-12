from django.test import TestCase
from django.urls import reverse
from .models import Marca, Zapato


class ZapatoModelTest(TestCase):
    def test_str(self):
        marca = Marca.objects.create(nombre="Marca")
        s = Zapato.objects.create(nombre="Test", marca=marca, precio=50, genero="Unisex")
        self.assertIn("Test", str(s))


class ZapatoViewsTest(TestCase):
    def setUp(self):
        marca = Marca.objects.create(nombre="X")
        Zapato.objects.create(nombre="A", marca=marca, precio=200, genero="Unisex", estaDisponible=True)

    def test_list_status(self):
        url = reverse("catalog:zapato_list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_detail_status(self):
        s = Zapato.objects.first()
        url = reverse("catalog:zapato_detail", args=[s.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
