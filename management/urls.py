from django.urls import path
from .views import (
    AdminDashboardView,
    CustomerListView,
    CustomerDetailView,
    CustomerEditView,
    CustomerDeleteView,
    AdminListView,
    AdminCreateView,
    AdminEditView,
    AdminDeleteView,
)

urlpatterns = [
    path("", AdminDashboardView.as_view(), name="admin_dashboard"),
    path("customers/", CustomerListView.as_view(), name="customer_list"),
    path("customers/<int:user_id>/", CustomerDetailView.as_view(), name="customer_detail"),
    path("customers/<int:user_id>/edit/", CustomerEditView.as_view(), name="customer_edit"),
    path("customers/<int:user_id>/delete/", CustomerDeleteView.as_view(), name="customer_delete"),
    path("admins/", AdminListView.as_view(), name="admin_list"),
    path("admins/create/", AdminCreateView.as_view(), name="admin_create"),
    path("admins/<int:user_id>/edit/", AdminEditView.as_view(), name="admin_edit"),
    path("admins/<int:user_id>/delete/", AdminDeleteView.as_view(), name="admin_delete"),
]
