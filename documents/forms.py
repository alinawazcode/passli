import os
from django import forms
from django.core.exceptions import ValidationError
from .models import Document

ALLOWED_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg']
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB in bytes

MAGIC_HEADERS = {
    '.pdf': [b'%PDF-'],
    '.png': [b'\x89PNG\r\n\x1a\n'],
    '.jpg': [b'\xff\xd8\xff'],
    '.jpeg': [b'\xff\xd8\xff'],
}


class DocumentUploadForm(forms.ModelForm):
    """Secure document upload form with file type, content magic-byte, and size constraints."""

    class Meta:
        model = Document
        fields = ('title', 'category', 'description', 'file')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Blood_Panel_Report_2026',
                'id': 'doc-title',
                'autofocus': True,
            }),
            'category': forms.Select(attrs={
                'class': 'form-input form-select',
                'id': 'doc-category',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Optional notes or medical/legal context...',
                'id': 'doc-description',
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-file-input',
                'id': 'doc-file-input',
                'accept': '.pdf,.png,.jpg,.jpeg',
            }),
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if not file:
            raise ValidationError("Please select a valid document file to upload.")

        # Check file extension
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            allowed_str = ", ".join(ALLOWED_EXTENSIONS)
            raise ValidationError(f"Unsupported file format '{ext}'. Allowed formats: {allowed_str}")

        # Check file size (5 MB limit)
        if file.size > MAX_FILE_SIZE:
            raise ValidationError("File size exceeds maximum allowed limit of 5 MB.")

        # Inspect initial bytes to verify content matches extension
        try:
            file.seek(0)
            header = file.read(16)
            file.seek(0)
        except Exception as read_err:
            raise ValidationError("Unable to read uploaded file stream.") from read_err

        expected_signatures = MAGIC_HEADERS.get(ext, [])
        if not any(header.startswith(sig) for sig in expected_signatures):
            raise ValidationError(
                f"File content does not match the '{ext}' format. Uploaded file may be corrupted or disguised."
            )

        return file


class DocumentEditForm(forms.ModelForm):
    """Form to edit existing document metadata without altering file bytes."""

    class Meta:
        model = Document
        fields = ('title', 'category', 'description')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Document Title',
                'id': 'edit-doc-title',
            }),
            'category': forms.Select(attrs={
                'class': 'form-input form-select',
                'id': 'edit-doc-category',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 4,
                'placeholder': 'Description or notes...',
                'id': 'edit-doc-description',
            }),
        }
