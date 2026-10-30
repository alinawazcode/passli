"""
Tests for repository visual identity assets, generator scripts, and documentation.
Verifies existence, dimensions, aspect ratios, file size bounds, animation frame integrity,
and comprehensive cross-doc markdown reference validity.
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
        cls.arch_path = cls.base_dir / "docs" / "ARCHITECTURE.md"
        cls.asset_catalog_path = cls.assets_dir / "README.md"

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
        """Animated workflow GIF must exist, have 58 frames, and be under 2MB."""
        gif_path = self.assets_dir / "passli-ephemeral-workflow.gif"
        self.assertTrue(gif_path.exists(), "passli-ephemeral-workflow.gif must exist")
        self.assertLess(gif_path.stat().st_size, 2 * 1024 * 1024, "Workflow GIF must be under 2MB")

        with Image.open(gif_path) as im:
            self.assertEqual(im.format, "GIF")
            self.assertTrue(getattr(im, "is_animated", False), "Workflow image must be an animated GIF")
            self.assertEqual(im.n_frames, 58, "Workflow GIF must contain exactly 58 distinct frames")
            self.assertEqual(im.size, (1100, 580), "Workflow GIF dimensions must be 1100x580")

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
            target_file = self.base_dir / asset
            self.assertTrue(target_file.exists(), f"Asset {asset} referenced in README.md must exist")

    def test_architecture_doc_references_assets(self):
        """docs/ARCHITECTURE.md must reference architecture and workflow assets."""
        self.assertTrue(self.arch_path.exists(), "docs/ARCHITECTURE.md must exist")
        content = self.arch_path.read_text(encoding="utf-8")

        self.assertIn("../.github/assets/passli-cryptographic-pipeline.png", content)
        self.assertIn("../.github/assets/passli-ephemeral-workflow.gif", content)

    def test_branding_doc_exists_and_references_assets(self):
        """docs/BRANDING.md must exist and document brand tokens and assets."""
        self.assertTrue(self.branding_path.exists(), "docs/BRANDING.md must exist")
        content = self.branding_path.read_text(encoding="utf-8")

        self.assertIn("#0B0F17", content)
        self.assertIn("#10B981", content)
        self.assertIn("passli-repo-banner.png", content)
        self.assertIn("passli-ephemeral-workflow.gif", content)
        self.assertIn("passli-dashboard-preview.png", content)
        self.assertIn("passli-cryptographic-pipeline.png", content)

    def test_asset_catalog_doc_references_all_assets(self):
        """.github/assets/README.md must catalog all repository assets."""
        self.assertTrue(self.asset_catalog_path.exists(), ".github/assets/README.md must exist")
        content = self.asset_catalog_path.read_text(encoding="utf-8")

        for asset_filename in [
            "passli-repo-banner.png",
            "passli-ephemeral-workflow.gif",
            "passli-dashboard-preview.png",
            "passli-cryptographic-pipeline.png",
        ]:
            self.assertIn(asset_filename, content)
            self.assertTrue((self.assets_dir / asset_filename).exists())

    def test_generator_scripts_exist(self):
        """Scripts to generate GIF and dashboard preview must exist and be accessible."""
        gif_script = self.base_dir / "scripts" / "generate_ephemeral_flow_gif.py"
        dash_script = self.base_dir / "scripts" / "generate_dashboard_preview.py"
        self.assertTrue(gif_script.exists(), "generate_ephemeral_flow_gif.py must exist")
        self.assertTrue(dash_script.exists(), "generate_dashboard_preview.py must exist")
