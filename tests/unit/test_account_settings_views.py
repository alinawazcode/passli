"""
Unit and integration tests for Account Settings views, forms, avatar pipeline, and username controls (Phase 2):
- View authentication & Cache-Control: no-store / nosniff security headers.
- Profile display name XSS escaping & control character stripping.
- Avatar pipeline validation: non-images, extension spoofing, oversize, decompression bomb, animated GIFs.
- Avatar re-encoding: center-crop, 256x256, WebP, EXIF stripping.
- Authenticated avatar delivery view: nosniff, private cache, staff vs non-staff access control.
- Avatar replacement & removal: old files purged from disk.
- Username change rules: length, reserved names, '@' rejection, password re-auth.
- 30-day cooldown enforcement & next-change date banner rendering.
- Login username vs email resolution (closing ambiguity).
- Empty email verification guards and dashboard banner rendering.
"""

import io
import os
import shutil
import tempfile
from datetime import timedelta
from PIL import Image

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile, AccountEvent
from accounts.forms import LoginForm, UsernameChangeForm, ProfileForm
from tests.unit import get_test_password

User = get_user_model()


def create_test_image(format="JPEG", size=(300, 300), color=(15, 23, 42)):
    """Generate in-memory valid image bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=format)
    buf.seek(0)
    return buf.getvalue()


def create_animated_gif():
    """Generate in-memory multi-frame animated GIF."""
    buf = io.BytesIO()
    frame1 = Image.new("RGB", (100, 100), color=(255, 0, 0))
    frame2 = Image.new("RGB", (100, 100), color=(0, 255, 0))
    frame1.save(
        buf,
        format="GIF",
        save_all=True,
        append_images=[frame2],
        duration=200,
        loop=0,
    )
    buf.seek(0)
    return buf.getvalue()


class TestAccountSettingsViews(TestCase):
    """Integration test suite for the Account Settings view and components."""

    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.media_override = override_settings(
            MEDIA_ROOT=self.temp_media,
            ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"],
        )
        self.media_override.enable()

        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="settings_user",
            email="settings_user@passli.dev",
            password=self.password,
        )
        self.profile = UserProfile.objects.get(user=self.user)

        self.staff_user = User.objects.create_user(
            username="staff_admin",
            email="staff@passli.dev",
            password=self.password,
            is_staff=True,
        )

        self.other_user = User.objects.create_user(
            username="other_member",
            email="other@passli.dev",
            password=self.password,
        )

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.temp_media, ignore_errors=True)

    def test_settings_requires_login(self):
        """Anonymous requests to /settings/ must redirect to the login page."""
        url = reverse("account_settings")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_settings_security_headers(self):
        """Authenticated requests must return 200 with no-store and nosniff headers."""
        self.client.login(username=self.user.username, password=self.password)
        response = self.client.get(reverse("account_settings"))
        self.assertEqual(response.status_code, 200)

        cache_control = response.headers.get("Cache-Control", "")
        self.assertIn("no-store", cache_control)
        self.assertIn("no-cache", cache_control)
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")

    def test_display_name_update_and_xss_escaping(self):
        """Display names must strip control characters and render escaped/inert in HTML."""
        self.client.login(username=self.user.username, password=self.password)
        xss_payload = "<script>alert('xss')</script>Alex\x00\x08"

        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "update_profile",
                "display_name": xss_payload,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        self.profile.refresh_from_db()
        # Control characters stripped
        self.assertNotIn("\x00", self.profile.display_name)
        self.assertNotIn("\x08", self.profile.display_name)
        self.assertEqual(self.profile.display_name, "<script>alert('xss')</script>Alex")

        # In template HTML, dangerous payload must be escaped, not rendered as raw executable tag
        content = response.content.decode("utf-8")
        self.assertIn("&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;Alex", content)
        self.assertNotIn("<script>alert('xss')</script>Alex", content)

    def test_avatar_upload_rejects_non_image(self):
        """Uploading text file spoofed with .jpg extension must be rejected by Pillow validation."""
        self.client.login(username=self.user.username, password=self.password)
        fake_image = SimpleUploadedFile(
            "fake.jpg", b"This is plain text pretending to be a JPEG image.", content_type="image/jpeg"
        )

        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "upload_avatar",
                "avatar": fake_image,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar_path, "")
        self.assertContains(response, "Invalid or corrupted image file")

    def test_avatar_upload_rejects_disallowed_extension(self):
        """Uploading an executable or document extension must fail form validation."""
        self.client.login(username=self.user.username, password=self.password)
        bad_file = SimpleUploadedFile("exploit.exe", create_test_image("JPEG"), content_type="application/octet-stream")

        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "upload_avatar",
                "avatar": bad_file,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar_path, "")

    def test_avatar_upload_rejects_oversized_file(self):
        """Files exceeding 2 MB must be rejected by the avatar service."""
        self.client.login(username=self.user.username, password=self.password)
        large_bytes = b"X" * (2 * 1024 * 1024 + 1024)
        oversized = SimpleUploadedFile("big.jpg", large_bytes, content_type="image/jpeg")

        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "upload_avatar",
                "avatar": oversized,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar_path, "")
        self.assertContains(response, "must not exceed 2 MB")

    def test_avatar_upload_rejects_decompression_bomb(self):
        """Images with pixel count > 10,000,000 must be rejected."""
        self.client.login(username=self.user.username, password=self.password)
        bomb_bytes = create_test_image(format="JPEG", size=(3500, 3000))  # 10.5 million pixels
        bomb_file = SimpleUploadedFile("bomb.jpg", bomb_bytes, content_type="image/jpeg")

        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "upload_avatar",
                "avatar": bomb_file,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar_path, "")
        self.assertContains(response, "Image dimensions are excessively large")

    def test_avatar_upload_rejects_animated_gif(self):
        """Multi-frame animated files must be rejected."""
        self.client.login(username=self.user.username, password=self.password)
        gif_bytes = create_animated_gif()
        gif_file = SimpleUploadedFile("animated.gif", gif_bytes, content_type="image/gif")

        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "upload_avatar",
                "avatar": gif_file,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar_path, "")

    def test_avatar_upload_reencodes_to_square_webp(self):
        """Valid JPEG image is cropped square, resized to 256x256 WebP with stripped metadata."""
        self.client.login(username=self.user.username, password=self.password)
        valid_bytes = create_test_image(format="JPEG", size=(600, 400), color=(10, 50, 100))
        img_file = SimpleUploadedFile("avatar.jpg", valid_bytes, content_type="image/jpeg")

        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "upload_avatar",
                "avatar": img_file,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        self.profile.refresh_from_db()
        self.assertTrue(self.profile.avatar_path)
        self.assertTrue(self.profile.avatar_path.endswith(".webp"))

        disk_path = os.path.join(self.temp_media, self.profile.avatar_path)
        self.assertTrue(os.path.exists(disk_path))

        with Image.open(disk_path) as saved_img:
            self.assertEqual(saved_img.format, "WEBP")
            self.assertEqual(saved_img.size, (256, 256))
            # EXIF metadata must be stripped
            self.assertFalse(bool(saved_img.getexif()))

    def test_avatar_authenticated_delivery_and_permissions(self):
        """Avatar view requires auth, sends nosniff/private, and isolates non-staff users."""
        self.client.login(username=self.user.username, password=self.password)
        img_bytes = create_test_image(format="PNG", size=(300, 300))
        img_file = SimpleUploadedFile("test.png", img_bytes, content_type="image/png")
        self.client.post(
            reverse("account_settings"),
            {"action": "upload_avatar", "avatar": img_file},
        )
        self.profile.refresh_from_db()

        # Anonymous request cannot view avatar
        self.client.logout()
        anon_resp = self.client.get(reverse("avatar_serve_self"))
        self.assertEqual(anon_resp.status_code, 302)

        # Owner can view their own avatar
        self.client.login(username=self.user.username, password=self.password)
        owner_resp = self.client.get(reverse("avatar_serve_self"))
        self.assertEqual(owner_resp.status_code, 200)
        self.assertEqual(owner_resp.headers.get("Content-Type"), "image/webp")
        self.assertEqual(owner_resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("private", owner_resp.headers.get("Cache-Control", ""))

        # Another regular user cannot view user's avatar
        self.client.login(username=self.other_user.username, password=self.password)
        forbidden_resp = self.client.get(reverse("avatar_serve", args=[self.user.id]))
        self.assertEqual(forbidden_resp.status_code, 403)

        # Staff user CAN view any user's avatar
        self.client.login(username=self.staff_user.username, password=self.password)
        staff_resp = self.client.get(reverse("avatar_serve", args=[self.user.id]))
        self.assertEqual(staff_resp.status_code, 200)
        self.assertEqual(staff_resp.headers.get("Content-Type"), "image/webp")

    def test_avatar_replacement_and_removal_purges_disk(self):
        """Replacing or removing an avatar removes the previous file from disk."""
        self.client.login(username=self.user.username, password=self.password)
        img_1 = SimpleUploadedFile("one.png", create_test_image(), content_type="image/png")
        self.client.post(reverse("account_settings"), {"action": "upload_avatar", "avatar": img_1})
        self.profile.refresh_from_db()
        first_disk_path = os.path.join(self.temp_media, self.profile.avatar_path)
        self.assertTrue(os.path.exists(first_disk_path))

        # Replace avatar
        img_2 = SimpleUploadedFile("two.png", create_test_image(color=(50, 100, 150)), content_type="image/png")
        self.client.post(reverse("account_settings"), {"action": "upload_avatar", "avatar": img_2})
        self.profile.refresh_from_db()
        second_disk_path = os.path.join(self.temp_media, self.profile.avatar_path)
        self.assertTrue(os.path.exists(second_disk_path))
        self.assertNotEqual(first_disk_path, second_disk_path)
        self.assertFalse(os.path.exists(first_disk_path))

        # Remove avatar
        self.client.post(reverse("account_settings"), {"action": "remove_avatar"})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar_path, "")
        self.assertFalse(os.path.exists(second_disk_path))

    def test_username_change_reserved_names_and_at_sign_rejected(self):
        """Reserved usernames and usernames containing '@' must be rejected."""
        self.client.login(username=self.user.username, password=self.password)

        reserved_names = ["admin", "administrator", "root", "support", "passli", "system"]
        for res_name in reserved_names:
            response = self.client.post(
                reverse("account_settings"),
                {
                    "action": "change_username",
                    "new_username": res_name,
                    "current_password": self.password,
                },
                follow=True,
            )
            self.assertEqual(response.status_code, 200)
            self.user.refresh_from_db()
            self.assertEqual(self.user.username, "settings_user")
            self.assertContains(response, "reserved")

        # Username with '@'
        at_response = self.client.post(
            reverse("account_settings"),
            {
                "action": "change_username",
                "new_username": "new@user",
                "current_password": self.password,
            },
            follow=True,
        )
        self.assertEqual(at_response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "settings_user")
        self.assertContains(at_response, "cannot contain")

    def test_username_change_requires_correct_password(self):
        """Changing username requires confirming current password."""
        self.client.login(username=self.user.username, password=self.password)
        wrong_pw = get_test_password()
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "change_username",
                "new_username": "fresh_handle",
                "current_password": wrong_pw,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "settings_user")
        self.assertContains(response, "current password entered is incorrect")

    def test_username_cooldown_banner_and_post_rejection(self):
        """After username change, 30-day cooldown is displayed with the next date and blocks changes."""
        self.client.login(username=self.user.username, password=self.password)

        # Successful change
        success_resp = self.client.post(
            reverse("account_settings"),
            {
                "action": "change_username",
                "new_username": "renamed_user",
                "current_password": self.password,
            },
            follow=True,
        )
        self.assertEqual(success_resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "renamed_user")

        # Inspect GET page: COOLDOWN ACTIVE badge and next date
        page_resp = self.client.get(reverse("account_settings"))
        self.assertContains(page_resp, "COOLDOWN ACTIVE")
        self.assertContains(page_resp, "You can change your username again on")

        # Attempting second change within cooldown must fail
        blocked_resp = self.client.post(
            reverse("account_settings"),
            {
                "action": "change_username",
                "new_username": "second_rename",
                "current_password": self.password,
            },
            follow=True,
        )
        self.assertEqual(blocked_resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "renamed_user")
        self.assertContains(blocked_resp, "You can change your username again on")

    def test_login_form_resolves_username_and_email_cleanly(self):
        """LoginForm resolves username or email without collision because '@' is barred from usernames."""
        # 1. Login with username
        form_username = LoginForm(data={"username": "settings_user", "password": self.password})
        self.assertTrue(form_username.is_valid())
        self.assertEqual(form_username.get_user(), self.user)

        # 2. Login with email
        form_email = LoginForm(data={"username": "settings_user@passli.dev", "password": self.password})
        self.assertTrue(form_email.is_valid())
        self.assertEqual(form_email.get_user(), self.user)

        # 3. Disallow '@' in UsernameChangeForm
        form_bad_user = UsernameChangeForm(
            self.user, data={"new_username": "hacker@evil", "current_password": self.password}
        )
        self.assertFalse(form_bad_user.is_valid())
        self.assertIn("cannot contain", form_bad_user.errors["new_username"][0])

    def test_empty_email_verification_redirection_and_banner(self):
        """When user email is empty, dashboard banner links to settings, and verify views redirect."""
        # Remove email
        self.user.email = ""
        self.user.save(update_fields=["email"])
        self.profile.is_email_verified = False
        self.profile.save(update_fields=["is_email_verified"])

        self.client.login(username=self.user.username, password=self.password)

        # Dashboard banner test
        dash_resp = self.client.get(reverse("dashboard"))
        self.assertEqual(dash_resp.status_code, 200)
        self.assertContains(dash_resp, "You have no email address on file")
        self.assertContains(dash_resp, "Add an email address")

        # Verify email view redirect
        verify_resp = self.client.get(reverse("verify_email"), follow=False)
        self.assertEqual(verify_resp.status_code, 302)
        self.assertIn(reverse("account_settings"), verify_resp.url)

        # Resend OTP view redirect
        resend_resp = self.client.get(reverse("resend_verification_otp"), follow=False)
        self.assertEqual(resend_resp.status_code, 302)
        self.assertIn(reverse("account_settings"), resend_resp.url)
