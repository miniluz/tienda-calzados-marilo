from django.test import TestCase
from django.urls import reverse
from .models import Zapato


class ZapatoModelTest(TestCase):
    def test_str(self):
        s = Zapato.objects.create(nombre="Test", marca="Marca", talla=42.0, precio=50.0)
        self.assertIn("Test", str(s))


class ZapatoViewsTest(TestCase):
    def setUp(self):
        Zapato.objects.create(nombre="A", marca="X", talla=40, precio=200, available=True)

    def test_list_status(self):
        url = reverse("catalog:zapato_list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_detail_status(self):
        s = Zapato.objects.first()
        url = reverse("catalog:zapato_detail", args=[s.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
