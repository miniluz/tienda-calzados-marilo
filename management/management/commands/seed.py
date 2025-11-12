"""
Global seed command that discovers and executes seeders.py in each app

Usage:
    python manage.py seed
"""

import importlib
import sys

from django.apps import apps
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed database by running seeders.py in each installed app"

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("Starting database seeding..."))
        self.stdout.write("=" * 60)

        seeded_apps = []
        failed_apps = []

        for app_config in apps.get_app_configs():
            # Skip built-in Django apps
            if app_config.name.startswith("django."):
                continue

            app_name = app_config.name
            seeder_module_name = f"{app_name}.seeders"

            try:
                # Try to import the seeders module
                seeder_module = importlib.import_module(seeder_module_name)

                # Check if it has a seed() function
                if hasattr(seeder_module, "seed"):
                    self.stdout.write(f"\nSeeding {app_name}...")
                    seeder_module.seed()
                    seeded_apps.append(app_name)
                    self.stdout.write(self.style.SUCCESS(f"✓ {app_name} seeded successfully"))

            except ModuleNotFoundError:
                # No seeders.py in this app, skip silently
                continue
            except Exception as e:
                failed_apps.append((app_name, str(e)))
                self.stdout.write(self.style.ERROR(f"✗ Failed to seed {app_name}: {e}"))

        # Summary
        self.stdout.write("\n" + "=" * 60)
        if seeded_apps:
            self.stdout.write(self.style.SUCCESS(f"✓ Successfully seeded {len(seeded_apps)} app(s):"))
            for app in seeded_apps:
                self.stdout.write(f"  - {app}")

        if failed_apps:
            self.stdout.write(self.style.ERROR(f"\n✗ Failed to seed {len(failed_apps)} app(s):"))
            for app, error in failed_apps:
                self.stdout.write(f"  - {app}: {error}")
            sys.exit(1)

        if not seeded_apps and not failed_apps:
            self.stdout.write(self.style.WARNING("No seeders found in any app"))

        self.stdout.write("=" * 60)
