import os
from django.apps import AppConfig


class ManagementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "management"

    def ready(self):
        if os.environ.get("RUN_MAIN") == "true":
            self._initialize_default_admin()

    def _initialize_default_admin(self):
        from django.contrib.auth.models import User
        from tienda_calzados_marilo.env import getEnvConfig

        env_config = getEnvConfig()

        admin_email = "admin@calzmarilo.es"
        admin_password = env_config.ADMIN_PASSWORD

        print("Initializing admin account...")

        try:
            admin_user = User.objects.get(username=admin_email)
            print("Admin account exists, updating...")
            admin_user.set_password(admin_password)
            admin_user.email = admin_email
            admin_user.first_name = "Admin"
            admin_user.last_name = "Sistema"
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()
            print("Admin account updated")
        except User.DoesNotExist:
            print("Admin account does not exist, creating...")
            User.objects.create_superuser(
                username=admin_email,
                email=admin_email,
                password=admin_password,
                first_name="Admin",
                last_name="Sistema",
            )
            print("Admin account created")
