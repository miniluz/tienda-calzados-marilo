from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["user", "phone_number", "city", "created_at"]
    search_fields = ["user__username", "user__email", "phone_number", "city"]
    list_filter = ["city", "created_at"]
    readonly_fields = ["created_at", "updated_at"]
