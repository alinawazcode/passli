"""
Tests for repository visual identity assets and documentation.
Verifies existence, dimensions, aspect ratios, file size bounds,
and README/docs link integrity.
"""

from pathlib import Path
from django.test import SimpleTestCase
from django.conf import settings
from PIL import Image


class RepoVisualIdentityTests(SimpleTestCase):
    """Test suite ensuring visual identity assets meet open-source repository standards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_dir = Path(settings.BASE_DIR)
        cls.assets_dir = cls.base_dir / ".github" / "assets"
        cls.readme_path = cls.base_dir / "README.md"
        cls.branding_path = cls.base_dir / "docs" / "BRANDING.md"

    def test_assets_directory_exists(self):
        """The .github/assets directory must exist."""
        self.assertTrue(self.assets_dir.is_dir(), ".github/assets directory must exist")

    def test_repo_banner_asset(self):
        """Hero banner must exist, be under 2MB, and have 16:9 aspect ratio."""
        banner_path = self.assets_dir / "passli-repo-banner.png"
        self.assertTrue(banner_path.exists(), "passli-repo-banner.png must exist")
        self.assertLess(banner_path.stat().st_size, 2 * 1024 * 1024, "Banner must be under 2MB")

        with Image.open(banner_path) as im:
            self.assertEqual(im.format, "PNG")
            self.assertEqual(im.size, (1376, 768))

    def test_dashboard_preview_asset(self):
        """Dashboard preview must exist, be under 2MB, and have 16:9 aspect ratio."""
        preview_path = self.assets_dir / "passli-dashboard-preview.png"
        self.assertTrue(preview_path.exists(), "passli-dashboard-preview.png must exist")
        self.assertLess(preview_path.stat().st_size, 2 * 1024 * 1024, "Preview must be under 2MB")

        with Image.open(preview_path) as im:
            self.assertEqual(im.format, "PNG")
            self.assertEqual(im.size, (1376, 768))

    def test_cryptographic_pipeline_asset(self):
        """Architecture diagram must exist, be under 2MB, and have 16:9 aspect ratio."""
        arch_path = self.assets_dir / "passli-cryptographic-pipeline.png"
        self.assertTrue(arch_path.exists(), "passli-cryptographic-pipeline.png must exist")
        self.assertLess(arch_path.stat().st_size, 2 * 1024 * 1024, "Architecture image must be under 2MB")

        with Image.open(arch_path) as im:
            self.assertEqual(im.format, "PNG")
            self.assertEqual(im.size, (1376, 768))

    def test_ephemeral_workflow_gif_asset(self):
        """Animated workflow GIF must exist, have multiple frames, and be under 2MB."""
        gif_path = self.assets_dir / "passli-ephemeral-workflow.gif"
        self.assertTrue(gif_path.exists(), "passli-ephemeral-workflow.gif must exist")
        self.assertLess(gif_path.stat().st_size, 2 * 1024 * 1024, "Workflow GIF must be under 2MB")

        with Image.open(gif_path) as im:
            self.assertEqual(im.format, "GIF")
            self.assertTrue(getattr(im, "is_animated", False), "Workflow image must be an animated GIF")
            self.assertGreaterEqual(im.n_frames, 30, "Workflow GIF must contain at least 30 frames")

    def test_readme_references_assets(self):
        """README.md must reference the visual identity assets via valid relative paths."""
        self.assertTrue(self.readme_path.exists(), "README.md must exist")
        content = self.readme_path.read_text(encoding="utf-8")

        required_assets = [
            ".github/assets/passli-repo-banner.png",
            ".github/assets/passli-ephemeral-workflow.gif",
            ".github/assets/passli-dashboard-preview.png",
            ".github/assets/passli-cryptographic-pipeline.png",
        ]
        for asset in required_assets:
            self.assertIn(asset, content, f"README.md must contain relative link to {asset}")

    def test_branding_doc_exists_and_references_assets(self):
        """docs/BRANDING.md must exist and document brand tokens and assets."""
        self.assertTrue(self.branding_path.exists(), "docs/BRANDING.md must exist")
        content = self.branding_path.read_text(encoding="utf-8")

        self.assertIn("#0B0F17", content)
        self.assertIn("#10B981", content)
        self.assertIn("passli-repo-banner.png", content)
        self.assertIn("passli-ephemeral-workflow.gif", content)

    def test_gif_generator_script_exists(self):
        """scripts/generate_ephemeral_flow_gif.py generator script must exist."""
        script_path = self.base_dir / "scripts" / "generate_ephemeral_flow_gif.py"
        self.assertTrue(script_path.exists(), "generate_ephemeral_flow_gif.py must exist")
