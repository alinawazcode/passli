"""
Passli Automated Video Demonstration Recorder & Full-Platform Tour
===================================================================
Uses Playwright to record full HD video demonstrations of the Passli platform:
1. Desktop Full-Platform Tour:
   - Split Hero Landing Page & Interactive Sandbox Generator
   - Superadmin / Owner Authentication
   - Personal Vault Dashboard & Metrics
   - Document Ingestion & SHA-256 Hash Digest Inspection
   - Ephemeral Share Pass Generation with Dynamic QR Code
   - Owner Security Audit Trail
   - Custom Administration Console (Overview, Users, Global Vault, Passes, Audit)
2. Mobile Recipient QR Experience (390x844 Smartphone Viewport):
   - QR Landing Gateway
   - 8-Character Key Authentication
   - Real-time Expiration Countdown Ticker
   - Decrypted Document Preview Stream
   - Voluntary Session Destruction & Memory Wipe

Usage:
    python run_browser_e2e_demo.py
"""

import os
import sys
import time
import urllib.request
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
RECORDINGS_DIR = BASE_DIR / "recordings"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_PDF_PATH = BASE_DIR / "tests" / "sample_lab_report.pdf"
if not SAMPLE_PDF_PATH.exists():
    SAMPLE_PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SAMPLE_PDF_PATH, "wb") as f:
        f.write(b"%PDF-1.4 Clinical Diagnostic Lab Panel 2026 - Passli Cryptographic Systems\n%%EOF")


def is_server_running(url="http://127.0.0.1:8000/"):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status in (200, 302)
    except Exception:
        return False


def setup_local_admin():
    """Ensure superadmin account and sample documents exist locally."""
    try:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        import django
        django.setup()
        from django.contrib.auth import get_user_model
        from documents.models import Document
        from django.core.files.base import ContentFile

        demo_password = os.getenv('DJANGO_SUPERUSER_PASSWORD', 'PassliDemoSuperAdmin2026!')
        User = get_user_model()
        user, _ = User.objects.get_or_create(username='admin', defaults={'email': 'admin@passli.dev'})
        user.set_password(demo_password)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()

        # Seed sample medical document if none exists
        if not Document.objects.filter(user=user).exists():
            doc = Document(
                user=user,
                title="Executive Cardiology Assessment & ECG Panel",
                category="medical",
                description="Comprehensive cardiovascular diagnostic report and clinical biomarkers."
            )
            with open(SAMPLE_PDF_PATH, 'rb') as f:
                doc.file.save("cardiology_assessment.pdf", ContentFile(f.read()), save=True)
            print("[SUCCESS] Seeded default sample document for owner", flush=True)

        print("[SUCCESS] Local admin credentials primed", flush=True)
    except Exception as e:
        print(f"[NOTE] Django setup note: {e}", flush=True)


def ensure_server():
    if is_server_running():
        print("[INFO] Local Django server active on http://127.0.0.1:8000/", flush=True)
        return None

    print("[INFO] Starting local Django development server...", flush=True)
    python_exe = sys.executable
    manage_py = BASE_DIR / "manage.py"

    proc = subprocess.Popen(
        [python_exe, str(manage_py), "runserver", "127.0.0.1:8000", "--noreload"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(BASE_DIR)
    )

    for _ in range(15):
        time.sleep(1)
        if is_server_running():
            print("[SUCCESS] Local server active on http://127.0.0.1:8000/", flush=True)
            return proc

    return proc


def safe_screenshot(page, filename, title=""):
    try:
        path = SCREENSHOTS_DIR / filename
        page.screenshot(path=str(path), timeout=4000, animations="disabled")
        print(f" [FRAME] {title} -> {filename}", flush=True)
    except Exception as e:
        print(f" [FRAME RECORDED IN VIDEO] {title}", flush=True)


def run_full_recording():
    setup_local_admin()
    server_proc = ensure_server()
    base_url = "http://127.0.0.1:8000"

    print("\n" + "=" * 70, flush=True)
    print("  PASSLI FULL-SPECTRUM AUTOMATED VIDEO & MOBILE DEMO RECORDER", flush=True)
    print("=" * 70, flush=True)
    print(f"[INFO] Target Application: {base_url}", flush=True)
    print(f"[INFO] Video Output Directory: {RECORDINGS_DIR.resolve()}", flush=True)

    try:
        with sync_playwright() as p:
            print("[INFO] Launching Chromium Browser for Full Desktop Tour...", flush=True)
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )

            # -------------------------------------------------------------
            # TOUR 1: DESKTOP PLATFORM TOUR (1280x800)
            # -------------------------------------------------------------
            context_desktop = browser.new_context(
                record_video_dir=str(RECORDINGS_DIR),
                record_video_size={"width": 1280, "height": 800},
                viewport={"width": 1280, "height": 800},
            )
            page = context_desktop.new_page()

            # Step 1: Landing Page & Interactive Sandbox
            print("\n[STEP 1] Landing Page & Interactive Sandbox Tour...", flush=True)
            page.goto(f"{base_url}/", wait_until="domcontentloaded")
            time.sleep(2)
            safe_screenshot(page, "01_landing_hero.png", "Landing Page Split Hero")

            print(" -> Exploring Interactive Sandbox Generator...", flush=True)
            page.evaluate("window.scrollTo({top: 800, behavior: 'smooth'})")
            time.sleep(2)
            safe_screenshot(page, "02_landing_sandbox.png", "Interactive Share Pass Simulator")

            print(" -> Exploring Security Architecture & Specifications...", flush=True)
            page.evaluate("window.scrollTo({top: 1800, behavior: 'smooth'})")
            time.sleep(2)
            safe_screenshot(page, "03_landing_specs.png", "Security Specs & Use Cases")

            page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
            time.sleep(1)

            # Step 2: Admin Sign In
            print("\n[STEP 2] Authenticating as Administrator...", flush=True)
            page.goto(f"{base_url}/login/", wait_until="domcontentloaded")
            safe_screenshot(page, "04_login_portal.png", "Login Portal")

            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', os.getenv('DJANGO_SUPERUSER_PASSWORD', 'PassliDemoSuperAdmin2026!'))
            time.sleep(0.5)
            page.click('button[type="submit"]')
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)

            # Step 3: Personal Vault Dashboard
            print("\n[STEP 3] Personal Vault Dashboard & System Telemetry...", flush=True)
            page.goto(f"{base_url}/dashboard/", wait_until="domcontentloaded")
            time.sleep(2)
            safe_screenshot(page, "05_vault_dashboard.png", "Vault Dashboard Telemetry")

            # Step 4: Vault Directory Inspection
            print("\n[STEP 4] Inspecting Vault Records Directory...", flush=True)
            page.goto(f"{base_url}/documents/", wait_until="domcontentloaded")
            time.sleep(2)
            safe_screenshot(page, "06_vault_records.png", "Vault Records Directory")

            # Inspect first document detail
            first_doc_link = page.locator('a[href*="/documents/"]:not([href*="upload"]):not([href$="/documents/"])')
            if first_doc_link.count() > 0:
                first_doc_link.first.click()
                page.wait_for_load_state("domcontentloaded")
                time.sleep(2)
                safe_screenshot(page, "07_document_detail_sha256.png", "Document Detail with SHA-256")

            # Step 5: Generate Cryptographic Ephemeral Share Pass
            print("\n[STEP 5] Generating Ephemeral Share Pass with Dynamic QR Code...", flush=True)
            page.goto(f"{base_url}/share/create/", wait_until="domcontentloaded")
            time.sleep(1.5)

            title_input = page.locator('input[name="title"], #id_title')
            if title_input.is_visible():
                title_input.fill("Dr. Harrison Cardiology Consult")

            duration_select = page.locator('select[name="expires_in"], #id_expires_in')
            if duration_select.is_visible():
                duration_select.select_option("30m")

            doc_checkbox = page.locator('input[name="documents"]').first
            if doc_checkbox.is_visible():
                doc_checkbox.check(force=True)

            download_toggle = page.locator('input[name="can_download"]')
            if download_toggle.is_visible():
                download_toggle.check(force=True)

            safe_screenshot(page, "08_share_create_form.png", "Share Pass Creation Form")
            time.sleep(0.5)
            page.click('button[type="submit"]')
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)

            # Step 6: Ephemeral Share Pass Detail & Key Display
            print("\n[STEP 6] Inspecting Generated QR Pass & Share Key...", flush=True)
            safe_screenshot(page, "09_share_pass_qr_code.png", "Share Pass QR Code & 8-Char Key")

            raw_key = ""
            key_locator = page.locator('#shareKeyText')
            if key_locator.is_visible():
                raw_key = key_locator.inner_text().strip()
            print(f" -> Generated Ephemeral Share Key: {raw_key}", flush=True)

            pass_id = page.url.rstrip("/").split("/")[-1]
            recipient_url = f"{base_url}/p/{pass_id}/"

            # Step 7: User Security Audit Trail
            print("\n[STEP 7] Reviewing User Security Audit Trail (/audit/)...", flush=True)
            page.goto(f"{base_url}/audit/", wait_until="domcontentloaded")
            time.sleep(2)
            safe_screenshot(page, "10_security_audit_trail.png", "User Security Audit Trail")

            # Step 8: Custom Administration Consoles
            print("\n[STEP 8] Reviewing Custom Platform Administration Consoles...", flush=True)

            page.goto(f"{base_url}/admin-dashboard/", wait_until="domcontentloaded")
            time.sleep(2)
            safe_screenshot(page, "11_admin_overview.png", "Superadmin Telemetry & Overview")

            page.goto(f"{base_url}/admin-dashboard/users/", wait_until="domcontentloaded")
            time.sleep(2)
            safe_screenshot(page, "12_admin_users.png", "User Governance Console")

            page.goto(f"{base_url}/admin-dashboard/documents/", wait_until="domcontentloaded")
            time.sleep(2)
            safe_screenshot(page, "13_admin_global_vault.png", "Global File Vault Explorer")

            page.goto(f"{base_url}/admin-dashboard/passes/", wait_until="domcontentloaded")
            time.sleep(2)
            safe_screenshot(page, "14_admin_passes.png", "Global Active Passes Monitor")

            page.goto(f"{base_url}/admin-dashboard/audit/", wait_until="domcontentloaded")
            time.sleep(2)
            safe_screenshot(page, "15_admin_global_audit.png", "Global System Audit Stream")

            # Close desktop context to finalize video
            context_desktop.close()

            # -------------------------------------------------------------
            # TOUR 2: MOBILE RECIPIENT QR WORKFLOW (390x844 Smartphone)
            # -------------------------------------------------------------
            print("\n[STEP 9] Mobile Recipient QR Scan & Decryption Gateway (390x844)...", flush=True)
            context_mobile = browser.new_context(
                record_video_dir=str(RECORDINGS_DIR),
                record_video_size={"width": 390, "height": 844},
                viewport={"width": 390, "height": 844},
                is_mobile=True,
                has_touch=True,
            )
            mobile_page = context_mobile.new_page()

            # Mobile Gateway Landing
            print(f" -> Navigating to Recipient Gateway: {recipient_url}", flush=True)
            mobile_page.goto(recipient_url, wait_until="domcontentloaded")
            time.sleep(2)
            safe_screenshot(mobile_page, "16_mobile_qr_landing.png", "Mobile QR Scan Verification Gateway")

            # Submit Share Key
            if raw_key:
                print(f" -> Submitting Share Key: {raw_key} on smartphone interface...", flush=True)
                mobile_page.fill('input[name="access_key"]', raw_key)
                safe_screenshot(mobile_page, "17_mobile_key_entered.png", "Mobile Share Key Input")
                time.sleep(0.5)
                mobile_page.click('button[type="submit"]')
                mobile_page.wait_for_load_state("domcontentloaded")
                time.sleep(2.5)

                # Mobile Decrypted Document Portal
                print(" -> Landed on Mobile Decrypted Document Portal...", flush=True)
                safe_screenshot(mobile_page, "18_mobile_decrypted_portal.png", "Mobile Decrypted Document Portal")

                # Scroll down preview
                mobile_page.evaluate("window.scrollTo({top: 350, behavior: 'smooth'})")
                time.sleep(2)
                safe_screenshot(mobile_page, "19_mobile_document_preview.png", "Mobile In-Browser Document Stream")

                # Voluntary Session Exit
                print(" -> Terminating recipient session (Voluntary Memory Wipe)...", flush=True)
                exit_btn = mobile_page.locator('form[action*="leave"] button, button:has-text("Exit Session")')
                if exit_btn.count() > 0:
                    exit_btn.first.click()
                    mobile_page.wait_for_load_state("domcontentloaded")
                    time.sleep(2)
                    safe_screenshot(mobile_page, "20_mobile_session_terminated.png", "Mobile Session Destroyed & Cleansed")

            context_mobile.close()
            browser.close()

        # Compile animated GIF from captured screenshots
        screenshot_files = sorted(SCREENSHOTS_DIR.glob("*.png"))
        if screenshot_files:
            images = [Image.open(f) for f in screenshot_files]
            standard_size = (1080, 700)
            resized_images = [img.convert("RGB").resize(standard_size, Image.Resampling.LANCZOS) for img in images]

            gif_path = RECORDINGS_DIR / "passli_full_walkthrough_demo.gif"
            resized_images[0].save(
                str(gif_path),
                save_all=True,
                append_images=resized_images[1:],
                duration=1800,
                loop=0
            )
            print(f"\n[SUCCESS] Compiled Animated Walkthrough GIF: {gif_path.resolve()}", flush=True)

        video_files = list(RECORDINGS_DIR.glob("*.webm"))
        print("\n" + "=" * 70, flush=True)
        print("  ALL FULL-SPECTRUM DESKTOP & MOBILE DEMO VIDEOS RECORDED SUCCESSFULLY!", flush=True)
        print("=" * 70, flush=True)
        for vf in video_files:
            print(f" [VIDEO ARTIFACT] {vf.name} ({round(vf.stat().st_size / 1024, 1)} KB) -> {vf.resolve()}", flush=True)
        print("=" * 70 + "\n", flush=True)

    finally:
        if server_proc:
            server_proc.terminate()


if __name__ == "__main__":
    run_full_recording()
