from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError

User = get_user_model()


class RegisterForm(UserCreationForm):
    """Custom user registration form with email validation and modern UI styling."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'name@example.com',
            'autocomplete': 'email',
            'id': 'reg-email',
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Choose a username',
            'autocomplete': 'username',
            'id': 'reg-username',
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Create strong passphrase',
            'autocomplete': 'new-password',
            'id': 'reg-password1',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Repeat passphrase',
            'autocomplete': 'new-password',
            'id': 'reg-password2',
        })

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email


class LoginForm(AuthenticationForm):
    """Custom authentication form with styled inputs."""

    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Username or Email',
            'autocomplete': 'username',
            'id': 'login-username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
            'id': 'login-password',
        })
    )


class ForgotPasswordRequestForm(forms.Form):
    """Form to initiate password recovery via email."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'name@example.com',
            'autocomplete': 'email',
            'id': 'forgot-email',
            'autofocus': True,
        })
    )

    def clean_email(self):
        return self.cleaned_data.get('email', '').strip().lower()


class SetNewPasswordForm(forms.Form):
    """Form to define and confirm a new master password during token-verified reset."""

    password1 = forms.CharField(
        label="New Master Passphrase",
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter new strong passphrase',
            'autocomplete': 'new-password',
            'id': 'reset-password1',
            'autofocus': True,
        })
    )
    password2 = forms.CharField(
        label="Confirm New Master Passphrase",
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Repeat new passphrase',
            'autocomplete': 'new-password',
            'id': 'reset-password2',
        })
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')

        if p1 and p2:
            if p1 != p2:
                self.add_error('password2', "The two passwords did not match. Please re-enter both.")
            else:
                from django.contrib.auth.password_validation import validate_password
                validate_password(p1, self.user)

        return cleaned_data


class EmailVerificationOTPForm(forms.Form):
    """Form for submitting 6-digit OTP code to verify email address."""

    code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-input font-mono-data',
            'placeholder': '123456',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
            'id': 'otp-input',
            'autofocus': True,
            'style': 'text-align: center; letter-spacing: 0.3em; font-size: 1.5rem;',
        })
    )

    def clean_code(self):
        raw = self.cleaned_data.get('code', '').strip()
        if not raw.isdigit() or len(raw) != 6:
            raise ValidationError("Please enter a valid 6-digit numerical code.")
        return raw
