import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Ensures the default superadmin user exists in the production database (Railway/Deployment).'

    def handle(self, *args, **options):
        username = os.getenv('DJANGO_SUPERUSER_USERNAME', 'admin')
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD', 'PassliAdminDefault2026!')
        email = os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@passli.dev')

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email}
        )

        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Superadmin '{username}' created successfully."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Superadmin '{username}' credentials updated."))
