import sys
import threading
from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"

    # Class variable to track if scheduler has been initialized in this process
    _scheduler_initialized = False
    _lock = threading.Lock()

    def ready(self):
        """Initialize background scheduler for order cleanup"""
        # Only run during actual server startup (runserver or WSGI)
        # Skip during management commands (migrate, shell, etc.)
        if self._should_initialize():
            with self._lock:
                if not OrdersConfig._scheduler_initialized:
                    self._start_scheduler()
                    OrdersConfig._scheduler_initialized = True

    def _should_initialize(self):
        """Determine if we should run scheduler initialization."""
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

    def _start_scheduler(self):
        """Start the background scheduler for order cleanup."""
        from apscheduler.schedulers.background import BackgroundScheduler
        from orders.utils import cleanup_expired_orders
        from tienda_calzados_marilo.env import getEnvConfig

        env_config = getEnvConfig()
        cleanup_minutes = env_config.CLEANUP_CRON_MINUTES

        scheduler = BackgroundScheduler()

        # Schedule cleanup job
        scheduler.add_job(
            cleanup_expired_orders,
            "interval",
            minutes=cleanup_minutes,
            id="cleanup_expired_orders",
            replace_existing=True,
        )

        scheduler.start()

        # Ensure scheduler shuts down when Django exits
        import atexit

        atexit.register(lambda: scheduler.shutdown())
