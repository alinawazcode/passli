"""
Landing Page & UI Presentation Test Suite
Validates landing page presentation, responsive navigation, interactive simulator elements,
security matrix, and asset integrity.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from tests.unit import get_test_password

User = get_user_model()


class LandingPageTests(TestCase):
    """Test suite covering Landing Page presentation and responsive routing."""

    def setUp(self):
        self.client = Client()
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="testsecurityuser",
            email="security@passli.dev",
            password=self.password
        )

    def test_landing_page_status_and_templates(self):
        """Verify landing page returns HTTP 200 and uses appropriate templates."""
        response = self.client.get(reverse('landing'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/landing.html')
        self.assertTemplateUsed(response, 'base.html')

    def test_anonymous_navigation_elements(self):
        """Verify navigation bar for unauthenticated anonymous visitors."""
        response = self.client.get(reverse('landing'))
        content = response.content.decode('utf-8')

        self.assertIn('Passli', content)
        self.assertIn('Sign In', content)
        self.assertIn('Launch Vault', content)
        self.assertNotIn('Logout', content)
        self.assertNotIn('Dashboard', content)

    def test_authenticated_navigation_elements(self):
        """Verify navigation bar adapts correctly for logged-in authenticated users."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('landing'))
        content = response.content.decode('utf-8')

        self.assertIn('Dashboard', content)
        self.assertIn('Vault', content)
        self.assertIn('New Pass', content)
        self.assertIn('Logout', content)

    def test_hero_section_and_authentic_photography(self):
        """Verify split-hero section includes authentic photography and clean headings without AI slop."""
        response = self.client.get(reverse('landing'))
        content = response.content.decode('utf-8')

        # Hero headline and subheadline
        self.assertIn('Share only the records you choose.', content)
        self.assertIn('Never your account credentials.', content)
        self.assertIn('hero-visual-img', content)
        self.assertIn('images.unsplash.com', content)

        # Ensure no clunky AI slop pill tags in headings
        self.assertNotIn('[ZERO-KNOWLEDGE ARCHITECTURE]', content)
        self.assertNotIn('[DEFENSIVE CAPABILITIES]', content)

    def test_interactive_generator_sandbox(self):
        """Verify the interactive demo sandbox elements and simulator data bindings."""
        response = self.client.get(reverse('landing'))
        content = response.content.decode('utf-8')

        self.assertIn('id="generator-sandbox"', content)
        self.assertIn('Interactive Share Pass Generator', content)
        self.assertIn('Blood_Test_Panel_2026.pdf', content)
        self.assertIn('National_ID_Card.png', content)
        self.assertIn('Vehicle_Registration_Cert.pdf', content)
        self.assertIn('sim-doc-checkbox', content)
        self.assertIn('expiry-buttons-grid', content)
        self.assertIn('8K7P-42XM', content)
        self.assertIn('sim-generate-btn', content)

    def test_real_world_use_cases(self):
        """Verify real-world scenario showcase with verified photography."""
        response = self.client.get(reverse('landing'))
        content = response.content.decode('utf-8')

        self.assertIn('id="use-cases"', content)
        self.assertIn('Clinic & Doctor Consultations', content)
        self.assertIn('Job Verification & Certifications', content)
        self.assertIn('Vehicle Registration & Inspections', content)

    def test_sharing_protocol_workflow(self):
        """Verify 3-step sharing protocol workflow is clearly defined."""
        response = self.client.get(reverse('landing'))
        content = response.content.decode('utf-8')

        self.assertIn('id="how-it-works"', content)
        self.assertIn('STEP 01', content)
        self.assertIn('Select & Generate', content)
        self.assertIn('STEP 02', content)
        self.assertIn('Recipient Scans & Authenticates', content)
        self.assertIn('STEP 03', content)
        self.assertIn('Automatic Shredding', content)

    def test_defensive_capabilities_grid(self):
        """Verify defensive capabilities bento grid cards."""
        response = self.client.get(reverse('landing'))
        content = response.content.decode('utf-8')

        self.assertIn('id="features"', content)
        self.assertIn('Encrypted Vault', content)
        self.assertIn('Two-Factor Share Access', content)
        self.assertIn('Enforced Expiration', content)
        self.assertIn('Detailed Access Audit', content)

    def test_institutional_security_comparison_matrix(self):
        """Verify institutional comparison table comparing Passli, Cloud Folders, and Email."""
        response = self.client.get(reverse('landing'))
        content = response.content.decode('utf-8')

        self.assertIn('id="security"', content)
        self.assertIn('Institutional Security Comparison', content)
        self.assertIn('Passli Secure Pass', content)
        self.assertIn('Cloud Storage Folders', content)
        self.assertIn('Email Attachments', content)
        self.assertIn('Account Credential Exposure', content)

    def test_navbar_links_match_page_section_ids(self):
        """Verify all navigation links correspond to existing section IDs on the landing page."""
        response = self.client.get(reverse('landing'))
        content = response.content.decode('utf-8')

        required_sections = [
            'generator-sandbox',
            'use-cases',
            'how-it-works',
            'security'
        ]

        for section_id in required_sections:
            # Check link in navbar
            self.assertIn(f'href="#{section_id}"', content)
            # Check target section tag
            self.assertIn(f'id="{section_id}"', content)

    def test_seo_meta_tags_and_title(self):
        """Verify SEO title, description, and accessibility viewport tags."""
        response = self.client.get(reverse('landing'))
        content = response.content.decode('utf-8')

        self.assertIn('<title>Passli — Controlled Document Sharing & Ephemeral Vault</title>', content)
        self.assertIn('meta name="description"', content)
        self.assertIn('meta name="viewport"', content)
        self.assertIn('styles.css', content)
