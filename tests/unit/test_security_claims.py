"""
Security Claims & Transparency Verification Test Suite
Validates that Passli templates and emails are free of false claims,
and that SECURITY.md explicitly states Passli is not zero-knowledge.
"""

from pathlib import Path
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.template.loader import render_to_string
from django.conf import settings
from tests.unit import get_test_password

User = get_user_model()


class SecurityClaimsTests(TestCase):
    """Test suite ensuring absence of false claims in user-facing views and emails."""

    FORBIDDEN_TERMS = [
        "SOC 2",
        "Zero-Knowledge",
        "XChaCha",
        "Argon2",
        "hardware",
        "client-side",
        "only you hold",
    ]

    def setUp(self):
        self.client = Client()
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="claimstestuser",
            email="claims@passli.dev",
            password=self.password,
            is_active=True,
        )

    def _assert_no_forbidden_terms(self, content: str, source_name: str):
        content_lower = content.lower()
        for term in self.FORBIDDEN_TERMS:
            term_lower = term.lower()
            self.assertNotIn(
                term_lower,
                content_lower,
                f"Forbidden security claim '{term}' found in {source_name}",
            )

    def test_landing_page_has_no_false_claims(self):
        """Landing page must not contain false security claims."""
        response = self.client.get(reverse("landing"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self._assert_no_forbidden_terms(content, "landing page")

    def test_dashboard_page_has_no_false_claims(self):
        """Dashboard page must not contain false security claims."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self._assert_no_forbidden_terms(content, "dashboard page")

    def test_register_page_has_no_false_claims(self):
        """Register page must not contain false security claims."""
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self._assert_no_forbidden_terms(content, "register page")

    def test_welcome_email_templates_have_no_false_claims(self):
        """Welcome email HTML and plaintext templates must not contain false claims."""
        context = {
            "username": "claimstestuser",
            "dashboard_url": "https://passli.dev/dashboard/",
            "app_url": "https://passli.dev",
            "timestamp_utc": "2026-10-23 00:00:00",
            "current_year": 2026,
        }
        html_rendered = render_to_string("emails/welcome_registered.html", context)
        txt_rendered = render_to_string("emails/welcome_registered.txt", context)

        self._assert_no_forbidden_terms(html_rendered, "welcome_registered.html")
        self._assert_no_forbidden_terms(txt_rendered, "welcome_registered.txt")

    def test_security_md_contains_not_zero_knowledge_statement(self):
        """SECURITY.md must explicitly declare that Passli is not zero-knowledge and server can read docs."""
        security_file = Path(settings.BASE_DIR) / "SECURITY.md"
        self.assertTrue(security_file.exists(), "SECURITY.md must exist in project root")

        content = security_file.read_text(encoding="utf-8")
        self.assertIn("not zero-knowledge", content.lower())
        self.assertIn("server can read documents", content.lower())
        self.assertIn("not been independently audited", content.lower())
