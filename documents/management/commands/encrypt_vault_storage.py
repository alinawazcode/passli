import hashlib
import logging
import os
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from documents.models import Document
from documents.services.crypto_service import encrypt_bytes

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Encrypt unencrypted documents or re-encrypt legacy vault documents with AES-256-GCM and document UUID AAD."

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help="Number of documents to process in one batch (default: 50)."
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Simulate the migration without modifying files or database records."
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help="Proceed even if stored file_hash does not match plaintext hash."
        )
        parser.add_argument(
            '--reencrypt-legacy',
            action='store_true',
            help="Re-encrypt existing encrypted documents to bind document UUID as associated data (AAD) and update key version."
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        batch_size = options['batch_size']
        reencrypt_legacy = options['reencrypt_legacy']

        self.stdout.write(self.style.MIGRATE_HEADING("=== Passli Vault Storage Encryption Migration ==="))
        if dry_run:
            self.stdout.write(self.style.WARNING("Mode: DRY-RUN (no files or database rows will be altered)\n"))
        else:
            self.stdout.write(self.style.SUCCESS("Mode: LIVE EXECUTION (encrypting storage files at rest)\n"))

        if reencrypt_legacy:
            qs = Document.objects.filter(is_encrypted=True).order_by('created_at')
            mode_desc = "legacy encrypted document(s) to re-encrypt with AAD"
        else:
            qs = Document.objects.filter(is_encrypted=False).order_by('created_at')
            mode_desc = "unencrypted document(s) to encrypt"

        total_count = qs.count()
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS(f"No {mode_desc}. Nothing to do."))
            return

        self.stdout.write(f"Found {total_count} {mode_desc}.\n")

        processed = 0
        success_count = 0
        failed_count = 0

        current_key_version = getattr(settings, 'VAULT_KEY_VERSION', 1)

        for doc in qs.iterator(chunk_size=batch_size):
            processed += 1
            prefix = f"[{processed}/{total_count}] Doc ID {doc.id} ('{doc.title}')"

            if not doc.file:
                self.stdout.write(self.style.WARNING(f"  {prefix}: Skipped (no file attached)."))
                failed_count += 1
                continue

            try:
                if reencrypt_legacy:
                    # Decrypt via legacy/current path
                    raw_bytes = doc.get_decrypted_content()
                else:
                    # Read unencrypted file directly
                    if hasattr(doc.file, 'path') and os.path.exists(doc.file.path):
                        with open(doc.file.path, 'rb') as f:
                            raw_bytes = f.read()
                    else:
                        with default_storage.open(doc.file.name, 'rb') as f:
                            raw_bytes = f.read()
            except (FileNotFoundError, OSError, ValueError) as e:
                self.stdout.write(self.style.ERROR(f"  {prefix}: Could not open file on storage ({e})."))
                failed_count += 1
                continue
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  {prefix}: Decryption failed ({e})."))
                failed_count += 1
                continue

            # Integrity check against plaintext hash if stored
            raw_hash = hashlib.sha256(raw_bytes).hexdigest()
            if doc.file_hash and doc.file_hash != raw_hash:
                if not force:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  {prefix}: Checksum mismatch! Stored: {doc.file_hash[:12]}..., Actual: {raw_hash[:12]}... Use --force to override."
                        )
                    )
                    failed_count += 1
                    continue
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  {prefix}: Warning: Checksum mismatch overridden by --force."
                        )
                    )

            if dry_run:
                action = "re-encrypt with UUID AAD" if reencrypt_legacy else "encrypt"
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {prefix}: [DRY RUN] Would {action} {len(raw_bytes)} bytes."
                    )
                )
                success_count += 1
                continue

            try:
                aad = str(doc.uuid).encode('utf-8')
                encrypted_payload = encrypt_bytes(raw_bytes, associated_data=aad)

                if hasattr(doc.file, 'path') and os.path.exists(doc.file.path):
                    temp_path = doc.file.path + '.enc_tmp'
                    with open(temp_path, 'wb') as f:
                        f.write(encrypted_payload)
                    os.replace(temp_path, doc.file.path)
                else:
                    default_storage.delete(doc.file.name)
                    default_storage.save(doc.file.name, ContentFile(encrypted_payload))

                # Update metadata
                if not doc.file_hash:
                    doc.file_hash = raw_hash
                if not doc.file_size:
                    doc.file_size = len(raw_bytes)
                doc.is_encrypted = True
                doc.key_version = current_key_version
                doc.save(update_fields=['is_encrypted', 'file_hash', 'file_size', 'key_version'])

                action = "re-encrypted with UUID AAD" if reencrypt_legacy else "encrypted"
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {prefix}: Successfully {action} ({len(raw_bytes)} -> {len(encrypted_payload)} bytes, key v{current_key_version})."
                    )
                )
                success_count += 1
            except Exception as e:
                logger.exception("Failed to encrypt document %s", doc.id)
                self.stdout.write(self.style.ERROR(f"  {prefix}: Encryption failed ({e})."))
                failed_count += 1

        self.stdout.write("\n=== Migration Summary ===")
        self.stdout.write(f"Total processed: {processed}")
        self.stdout.write(f"Succeeded:       {success_count}")
        self.stdout.write(f"Failed / Skipped:{failed_count}")
        if dry_run:
            self.stdout.write(self.style.WARNING("No changes committed (dry run)."))
        else:
            self.stdout.write(self.style.SUCCESS("Encryption at rest completed successfully."))
