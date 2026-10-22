import hashlib
import logging
import os
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from documents.models import Document
from documents.services.crypto_service import encrypt_bytes

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Encrypt unencrypted documents in the vault storage with AES-256-GCM."

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

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        batch_size = options['batch_size']

        self.stdout.write(self.style.MIGRATE_HEADING("=== Passli Vault Storage Encryption Migration ==="))
        if dry_run:
            self.stdout.write(self.style.WARNING("Mode: DRY-RUN (no files or database rows will be altered)\n"))
        else:
            self.stdout.write(self.style.SUCCESS("Mode: LIVE EXECUTION (encrypting storage files at rest)\n"))

        unencrypted_qs = Document.objects.filter(is_encrypted=False).order_by('created_at')
        total_count = unencrypted_qs.count()

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("All vault documents are already marked as encrypted at rest. Nothing to do."))
            return

        self.stdout.write(f"Found {total_count} unencrypted document(s) to process.\n")

        processed = 0
        success_count = 0
        failed_count = 0

        for doc in unencrypted_qs.iterator(chunk_size=batch_size):
            processed += 1
            prefix = f"[{processed}/{total_count}] Doc ID {doc.id} ('{doc.title}')"

            if not doc.file:
                self.stdout.write(self.style.WARNING(f"  {prefix}: Skipped (no file attached)."))
                failed_count += 1
                continue

            # Read file raw bytes
            try:
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
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {prefix}: [DRY RUN] Would encrypt {len(raw_bytes)} bytes."
                    )
                )
                success_count += 1
                continue

            try:
                encrypted_payload = encrypt_bytes(raw_bytes)

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
                doc.save(update_fields=['is_encrypted', 'file_hash', 'file_size'])

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {prefix}: Successfully encrypted ({len(raw_bytes)} -> {len(encrypted_payload)} bytes)."
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
