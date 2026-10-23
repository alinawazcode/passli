import uuid
from django.db import migrations, models


def gen_uuid(apps, schema_editor):
    Document = apps.get_model('documents', 'Document')
    for row in Document.objects.all():
        row.uuid = uuid.uuid4()
        row.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0002_document_is_encrypted'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='key_version',
            field=models.PositiveIntegerField(default=1, help_text='Vault encryption key version used for this document'),
        ),
        migrations.AddField(
            model_name='document',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, null=True, editable=False, verbose_name='Document UUID'),
        ),
        migrations.RunPython(gen_uuid, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='document',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True, verbose_name='Document UUID'),
        ),
        migrations.AlterField(
            model_name='document',
            name='is_encrypted',
            field=models.BooleanField(default=True, help_text='Indicates if file content is stored with AES-256-GCM authenticated encryption.', verbose_name='Encrypted at Rest'),
        ),
    ]
