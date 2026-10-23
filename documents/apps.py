from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'documents'

    def ready(self):
        from .services.crypto_service import validate_vault_master_key
        validate_vault_master_key()
