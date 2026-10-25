import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Ensures superadmin users exist from environment variables without resetting existing passwords."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force creation or synchronization of superuser even if an active superuser already exists.",
        )

    def handle(self, *args, **options):
        force = options.get("force", False)

        # Guard: If any active superuser already exists, do not recreate unless --force
        if not force and User.objects.filter(is_superuser=True, is_active=True).exists():
            self.stdout.write(
                self.style.NOTICE(
                    "Active superuser already exists. Skipping superadmin provisioning (pass --force to override)."
                )
            )
            return

        # Configure primary superadmin from environment
        primary_username = os.getenv("DJANGO_SUPERUSER_USERNAME")
        primary_email = os.getenv("DJANGO_SUPERUSER_EMAIL", "")
        primary_password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

        if not primary_username or not primary_password:
            raise CommandError(
                "DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD environment variables are required to run ensure_superadmin."
            )

        admin_configs = [
            {
                "username": primary_username,
                "email": primary_email,
                "password": primary_password,
            }
        ]

        # Optional secondary superadmin from environment
        secondary_username = os.getenv("DJANGO_SECONDARY_SUPERUSER_USERNAME")
        secondary_email = os.getenv("DJANGO_SECONDARY_SUPERUSER_EMAIL", "")
        secondary_password = os.getenv("DJANGO_SECONDARY_SUPERUSER_PASSWORD")
        if secondary_username and secondary_password:
            admin_configs.append(
                {
                    "username": secondary_username,
                    "email": secondary_email,
                    "password": secondary_password,
                }
            )

        if not admin_configs:
            self.stdout.write("No superadmin accounts configured in environment variables to ensure.")
            return

        for account in admin_configs:
            username = account["username"]
            email = account["email"]
            password = account["password"]

            existing_user = User.objects.filter(username=username).first()
            if existing_user:
                # Idempotent safeguard: Never overwrite or reset existing passwords
                changed = False
                if not existing_user.is_staff:
                    existing_user.is_staff = True
                    changed = True
                if not existing_user.is_superuser:
                    existing_user.is_superuser = True
                    changed = True
                if not existing_user.is_active:
                    existing_user.is_active = True
                    changed = True
                if email and existing_user.email != email:
                    existing_user.email = email
                    changed = True

                if changed:
                    existing_user.save(update_fields=["is_staff", "is_superuser", "is_active", "email"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Superadmin '{username}' already exists; preserved existing password and verified permissions."
                    )
                )
            else:
                User.objects.create_superuser(username=username, email=email, password=password)
                self.stdout.write(self.style.SUCCESS(f"Superadmin '{username}' created successfully."))
