import sys
import threading
from django.apps import AppConfig


class ManagementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "management"

    # Class variable to track if initialization has occurred in this process
    _initialized = False
    _lock = threading.Lock()

    def ready(self):
        # Only run during actual server startup (runserver or WSGI)
        # Skip during management commands (migrate, shell, etc.)
        if self._should_initialize():
            with self._lock:
                if not ManagementConfig._initialized:
                    self._initialize_default_admin()
                    ManagementConfig._initialized = True

    def _should_initialize(self):
        """Determine if we should run initialization."""
        # Check if we're running via WSGI (no sys.argv or wsgi in argv)
        if len(sys.argv) == 0 or "wsgi" in " ".join(sys.argv):
            return True

        # Check if running via runserver (and in the reloaded process)
        if len(sys.argv) >= 2 and sys.argv[1] == "runserver":
            # Only run in the reloaded process, not the initial one
            import os

            return os.environ.get("RUN_MAIN") == "true"

        # For any other management command, don't initialize
        return False

    def _initialize_default_admin(self):
        from django.contrib.auth.models import User
        from tienda_calzados_marilo.env import getEnvConfig

        env_config = getEnvConfig()

        admin_email = "admin@calzmarilo.es"
        admin_password = env_config.ADMIN_PASSWORD

        try:
            admin_user = User.objects.get(username=admin_email)
            admin_user.set_password(admin_password)
            admin_user.email = admin_email
            admin_user.first_name = "Admin"
            admin_user.last_name = "Sistema"
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()
        except User.DoesNotExist:
            User.objects.create_superuser(
                username=admin_email,
                email=admin_email,
                password=admin_password,
                first_name="Admin",
                last_name="Sistema",
            )
