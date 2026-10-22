import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Ensures superadmin users exist from environment variables without resetting existing passwords.'

    def handle(self, *args, **options):
        # Configure primary superadmin from environment
        primary_username = os.getenv('DJANGO_SUPERUSER_USERNAME')
        primary_email = os.getenv('DJANGO_SUPERUSER_EMAIL', '')
        primary_password = os.getenv('DJANGO_SUPERUSER_PASSWORD')

        admin_configs = []
        if primary_username and primary_password:
            admin_configs.append({
                'username': primary_username,
                'email': primary_email,
                'password': primary_password,
            })
        else:
            self.stdout.write(
                self.style.WARNING(
                    "DJANGO_SUPERUSER_USERNAME or DJANGO_SUPERUSER_PASSWORD not set in environment. Skipping primary superadmin creation."
                )
            )

        # Optional secondary superadmin from environment
        secondary_username = os.getenv('DJANGO_SECONDARY_SUPERUSER_USERNAME')
        secondary_email = os.getenv('DJANGO_SECONDARY_SUPERUSER_EMAIL', '')
        secondary_password = os.getenv('DJANGO_SECONDARY_SUPERUSER_PASSWORD')
        if secondary_username and secondary_password:
            admin_configs.append({
                'username': secondary_username,
                'email': secondary_email,
                'password': secondary_password,
            })

        if not admin_configs:
            self.stdout.write("No superadmin accounts configured in environment variables to ensure.")
            return

        for account in admin_configs:
            username = account['username']
            email = account['email']
            password = account['password']

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
                    existing_user.save(update_fields=['is_staff', 'is_superuser', 'is_active', 'email'])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Superadmin '{username}' already exists; preserved existing password and verified permissions."
                    )
                )
            else:
                User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Superadmin '{username}' created successfully.")
                )


