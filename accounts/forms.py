from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError

User = get_user_model()


class RegisterForm(UserCreationForm):
    """Custom user registration form with email validation and modern UI styling."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-input",
                "placeholder": "name@example.com",
                "autocomplete": "email",
                "id": "reg-email",
            }
        ),
    )

    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "class": "form-input",
                "placeholder": "Choose a username",
                "autocomplete": "username",
                "id": "reg-username",
            }
        )
        self.fields["password1"].widget.attrs.update(
            {
                "class": "form-input",
                "placeholder": "Create strong passphrase",
                "autocomplete": "new-password",
                "id": "reg-password1",
            }
        )
        self.fields["password2"].widget.attrs.update(
            {
                "class": "form-input",
                "placeholder": "Repeat passphrase",
                "autocomplete": "new-password",
                "id": "reg-password2",
            }
        )

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email


class LoginForm(AuthenticationForm):
    """Custom authentication form with styled inputs and email resolution."""

    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "placeholder": "Username or Email",
                "autocomplete": "username",
                "id": "login-username",
                "autofocus": True,
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input",
                "placeholder": "Enter your password",
                "autocomplete": "current-password",
                "id": "login-password",
            }
        )
    )

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username is not None and password:
            clean_username = username.strip()
            lookup_username = clean_username
            if "@" in clean_username:
                user_match = User.objects.filter(email__iexact=clean_username).first()
                if user_match:
                    lookup_username = user_match.username

            from django.contrib.auth import authenticate

            self.user_cache = authenticate(self.request, username=lookup_username, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class ForgotPasswordRequestForm(forms.Form):
    """Form to initiate password recovery via email."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-input",
                "placeholder": "name@example.com",
                "autocomplete": "email",
                "id": "forgot-email",
                "autofocus": True,
            }
        ),
    )

    def clean_email(self):
        return self.cleaned_data.get("email", "").strip().lower()


class SetNewPasswordForm(forms.Form):
    """Form to define and confirm a new master password during token-verified reset."""

    password1 = forms.CharField(
        label="New Master Passphrase",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input",
                "placeholder": "Enter new strong passphrase",
                "autocomplete": "new-password",
                "id": "reset-password1",
                "autofocus": True,
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirm New Master Passphrase",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input",
                "placeholder": "Repeat new passphrase",
                "autocomplete": "new-password",
                "id": "reset-password2",
            }
        ),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password1")
        p2 = cleaned_data.get("password2")

        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "The two passwords did not match. Please re-enter both.")
            else:
                from django.contrib.auth.password_validation import validate_password

                validate_password(p1, self.user)

        return cleaned_data


class EmailVerificationOTPForm(forms.Form):
    """Form for submitting 6-digit OTP code to verify email address."""

    code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                "class": "form-input font-mono-data",
                "placeholder": "123456",
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "pattern": "[0-9]*",
                "id": "otp-input",
                "autofocus": True,
                "style": "text-align: center; letter-spacing: 0.3em; font-size: 1.5rem;",
            }
        ),
    )

    def clean_code(self):
        raw = self.cleaned_data.get("code", "").strip()
        if not raw.isdigit() or len(raw) != 6:
            raise ValidationError("Please enter a valid 6-digit numerical code.")
        return raw


class SanitizedCharField(forms.CharField):
    """CharField that strips ASCII/Unicode control characters before validation."""

    def to_python(self, value):
        if value is not None:
            import re

            value = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", str(value)).strip()
        return super().to_python(value)


class ProfileForm(forms.Form):
    """Form for updating personal display name."""

    display_name = SanitizedCharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "placeholder": "e.g. Alex Morgan",
                "id": "profile-display-name",
                "maxlength": "50",
            }
        ),
    )

    def clean_display_name(self):
        import re

        raw = self.cleaned_data.get("display_name", "").strip()
        cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", raw)
        return cleaned[:50]


class AvatarUploadForm(forms.Form):
    """Form for uploading square user avatar image."""

    avatar = forms.FileField(
        required=True,
        widget=forms.FileInput(
            attrs={
                "class": "settings-avatar-file-input",
                "id": "avatar-file-input",
                "accept": "image/jpeg,image/png,image/webp",
            }
        ),
    )

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            import os

            ext = os.path.splitext(avatar.name)[1].lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                raise ValidationError("Only .jpg, .jpeg, .png, and .webp file extensions are permitted.")
        return avatar


class UsernameChangeForm(forms.Form):
    """Form for requesting a 30-day cooldown username change with re-authentication."""

    new_username = forms.CharField(
        min_length=3,
        max_length=30,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-input font-mono-data",
                "placeholder": "new_username",
                "autocomplete": "username",
                "id": "settings-new-username",
                "maxlength": "30",
            }
        ),
    )
    current_password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input",
                "placeholder": "Enter current password to confirm",
                "autocomplete": "current-password",
                "id": "settings-username-password",
            }
        ),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_new_username(self):
        from accounts.services.username_service import validate_username_format

        raw = self.cleaned_data.get("new_username", "").strip()
        return validate_username_format(raw, current_user=self.user)


class EmailChangeRequestForm(forms.Form):
    """Form to initiate email address change with password confirmation."""

    new_email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-input",
                "placeholder": "new.email@example.com",
                "autocomplete": "email",
                "id": "settings-new-email",
            }
        ),
    )
    current_password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input",
                "placeholder": "Enter current password to authorize",
                "autocomplete": "current-password",
                "id": "settings-email-password",
            }
        ),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_new_email(self):
        raw = self.cleaned_data.get("new_email", "").strip().lower()
        current_email = (self.user.email or "").strip().lower()
        if raw == current_email:
            raise ValidationError("The new email address cannot be the same as your current address.")
        return raw


class EmailChangeConfirmForm(forms.Form):
    """Form to confirm 6-digit OTP code sent to the new email address."""

    code = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-input font-mono-data",
                "placeholder": "123456",
                "id": "email-otp-combined-input",
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "pattern": "[0-9]{6}",
                "maxlength": "6",
                "style": "letter-spacing: 0.25em; text-align: center; font-size: 1.15rem; max-width: 200px;",
            }
        ),
    )

    def clean_code(self):
        raw = self.cleaned_data.get("code", "").strip()
        if not raw.isdigit() or len(raw) != 6:
            raise ValidationError("Please enter a valid 6-digit numerical code.")
        return raw
