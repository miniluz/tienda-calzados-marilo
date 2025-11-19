from django.urls import path
from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.ZapatoListView.as_view(), name="zapato_list"),
    path("api/zapatos/", views.zapato_list_api, name="zapato_list_api"),
    path("<int:pk>/", views.ZapatoDetailView.as_view(), name="zapato_detail"),
    path("<int:pk>/buy-now/", views.BuyNowView.as_view(), name="buy_now"),
]
