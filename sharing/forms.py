from django import forms
from django.utils import timezone
from datetime import timedelta
from documents.models import Document
from .models import SharePass

EXPIRATION_CHOICES = [
    ('15m', '15 Minutes (Ephemeral Emergency Access)'),
    ('30m', '30 Minutes (Recommended Standard)'),
    ('1h', '1 Hour (Appointment / Consultation)'),
    ('2h', '2 Hours (Extended Evaluation)'),
    ('24h', '24 Hours (Full Day Access)'),
    ('1time', 'One-Time View (Burns after 1 access or 30 mins)'),
]


class SharePassCreateForm(forms.ModelForm):
    """
    Form for creating a cryptographic Share Pass with selected documents,
    duration, and granular permission constraints.
    """
    documents = forms.ModelMultipleChoiceField(
        queryset=Document.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        error_messages={'required': 'Please select at least one document to include in this Share Pass.'}
    )
    expires_in = forms.ChoiceField(
        choices=EXPIRATION_CHOICES,
        initial='30m',
        widget=forms.Select(attrs={'class': 'form-input form-select', 'data-testid': 'expires-in-select'}),
        help_text="Time after which the pass and its access key automatically expire."
    )
    can_download = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox', 'data-testid': 'can-download-toggle'}),
        help_text="If enabled, recipient can download raw decrypted document files. If disabled, view-only."
    )

    class Meta:
        model = SharePass
        fields = ['title', 'documents', 'can_download']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. Cardiology Clinic Visit / KYC Verification',
                'data-testid': 'share-pass-title-input'
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user and user.is_authenticated:
            self.fields['documents'].queryset = Document.objects.filter(user=user).order_by('-created_at')

    def clean_documents(self):
        docs = self.cleaned_data.get('documents')
        if not docs:
            raise forms.ValidationError("You must select at least one document.")

        # Verify strict ownership for every document (anti-tampering IDOR defense)
        if self.user and self.user.is_authenticated:
            for doc in docs:
                if doc.user_id != self.user.id:
                    raise forms.ValidationError(f"Unauthorized document selection: '{doc.title}'.")
        return docs

    def get_expiration_and_max_uses(self):
        """Calculates expiration datetime and max_uses based on selected choice."""
        expires_choice = self.cleaned_data.get('expires_in', '30m')
        now = timezone.now()

        if expires_choice == '15m':
            return now + timedelta(minutes=15), 0
        elif expires_choice == '30m':
            return now + timedelta(minutes=30), 0
        elif expires_choice == '1h':
            return now + timedelta(hours=1), 0
        elif expires_choice == '2h':
            return now + timedelta(hours=2), 0
        elif expires_choice == '24h':
            return now + timedelta(hours=24), 0
        elif expires_choice == '1time':
            return now + timedelta(minutes=30), 1
        return now + timedelta(minutes=30), 0


class RecipientKeyVerificationForm(forms.Form):
    """
    Form for recipient Share Key authentication.
    Normalizes input (removes spaces, hyphens, and standardizes to uppercase).
    """
    access_key = forms.CharField(
        max_length=20,
        min_length=8,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input font-mono-data key-input-display',
            'placeholder': '••••-••••',
            'autocomplete': 'off',
            'autocorrect': 'off',
            'autocapitalize': 'characters',
            'spellcheck': 'false',
            'maxlength': '9',
            'data-testid': 'recipient-key-input',
            'autofocus': True,
        }),
        error_messages={
            'required': 'Please enter the 8-character Share Key provided by the vault owner.',
        }
    )

    def clean_access_key(self):
        raw_key = self.cleaned_data.get('access_key', '').strip()
        # Normalize: remove dashes, whitespace, and convert to uppercase
        clean_key = raw_key.replace('-', '').replace(' ', '').upper()
        if len(clean_key) != 8 or not clean_key.isalnum():
            raise forms.ValidationError("Share Key must be exactly 8 alphanumeric characters (e.g., A1B2-C3D4).")
        return clean_key

