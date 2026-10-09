"""
Passli Full-Spectrum Walkthrough & Automated Demo Recorder
==========================================================
Executes a complete visual walkthrough against the production deployment:
1. Landing Page & Interactive Cryptographic Sandbox
2. Superadmin Authentication (alinawazcode)
3. Vault Dashboard & Metric Telemetry
4. Document Vault & SHA-256 Digest Inspection
5. Ephemeral Share Pass Generation with Dynamic QR Code
6. Mobile Recipient QR Gateway & 8-Character Key Verification (Mobile 390x844 Viewport)
7. Mobile Decrypted Document Inspection & Session Teardown
8. User Security Audit Trail
9. Custom Platform Administration Consoles (Overview, Users, Documents, Passes, Audit)

Usage:
    python run_selenium_walkthrough.py
"""

import os
import sys
import time
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_PDF_PATH = BASE_DIR / "tests" / "sample_lab_report.pdf"
if not SAMPLE_PDF_PATH.exists():
    SAMPLE_PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SAMPLE_PDF_PATH, "wb") as f:
        f.write(b"%PDF-1.4 Clinical Diagnostic Panel 2026 - Passli Cryptographic Systems\n%%EOF")


def capture_step(driver, filename, title=""):
    path = SCREENSHOTS_DIR / filename
    driver.save_screenshot(str(path))
    print(f" [SCREENSHOT] {title} -> {filename}", flush=True)
    time.sleep(1)


def run_walkthrough():
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    print("\n" + "=" * 70, flush=True)
    print("  PASSLI FULL-SPECTRUM AUTOMATED WALKTHROUGH & DEMO RECORDER", flush=True)
    print("=" * 70, flush=True)

    base_url = os.environ.get("TARGET_URL", "https://web-production-c1bd05e.up.railway.app").rstrip("/")
    print(f"[INFO] Target Application: {base_url}", flush=True)

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1280,850")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    print("[INFO] Launching Chrome WebDriver...", flush=True)
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 20)

    try:
        # -------------------------------------------------------------
        # 1. LANDING PAGE & SANDBOX
        # -------------------------------------------------------------
        print("\n[STEP 1] Landing Page & Interactive Cryptographic Sandbox...", flush=True)
        driver.set_window_size(1280, 850)
        driver.get(f"{base_url}/")
        time.sleep(2)
        capture_step(driver, "01_landing_hero.png", "Landing Page Split Hero")

        driver.execute_script("window.scrollTo({top: 800, behavior: 'smooth'});")
        time.sleep(1.5)
        capture_step(driver, "02_landing_sandbox.png", "Interactive Share Pass Simulator")

        driver.execute_script("window.scrollTo({top: 1800, behavior: 'smooth'});")
        time.sleep(1.5)
        capture_step(driver, "03_landing_specs.png", "Security Specs & Use Cases")

        # -------------------------------------------------------------
        # 2. SUPERADMIN AUTHENTICATION
        # -------------------------------------------------------------
        print("\n[STEP 2] Signing in as Superadmin (alinawazcode)...", flush=True)
        driver.get(f"{base_url}/login/")
        time.sleep(1.5)
        capture_step(driver, "04_login_page.png", "Login Portal")

        user_input = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        pass_input = driver.find_element(By.NAME, "password")
        user_input.send_keys(os.getenv("DJANGO_SUPERUSER_USERNAME", "admin"))
        pass_input.send_keys(os.getenv("DJANGO_SUPERUSER_PASSWORD", "PassliAdminDefault2026!"))
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2.5)

        # -------------------------------------------------------------
        # 3. VAULT DASHBOARD
        # -------------------------------------------------------------
        print("\n[STEP 3] Personal Vault Dashboard & Metrics...", flush=True)
        driver.get(f"{base_url}/dashboard/")
        time.sleep(2)
        capture_step(driver, "05_vault_dashboard.png", "Vault Dashboard Telemetry")

        # -------------------------------------------------------------
        # 4. DOCUMENT UPLOAD & VAULT RECORDS
        # -------------------------------------------------------------
        print("\n[STEP 4] Document Ingestion & Checksum Inspection...", flush=True)
        driver.get(f"{base_url}/documents/upload/")
        time.sleep(1.5)
        capture_step(driver, "06_document_upload.png", "Document Upload Form")

        file_input = driver.find_element(By.CSS_SELECTOR, "input[name='file']")
        file_input.send_keys(str(SAMPLE_PDF_PATH.resolve()))
        driver.find_element(By.CSS_SELECTOR, "input[name='title']").send_keys("Cardiology Diagnostic & ECG Assessment")
        driver.find_element(By.CSS_SELECTOR, "textarea[name='description']").send_keys("Confidential cardiovascular ultrasound and clinical biomarker panel.")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2.5)

        # Vault list view
        driver.get(f"{base_url}/documents/")
        time.sleep(2)
        capture_step(driver, "07_vault_records_list.png", "Vault Records Directory")

        # -------------------------------------------------------------
        # 5. CREATE CRYPTOGRAPHIC SHARE PASS
        # -------------------------------------------------------------
        print("\n[STEP 5] Generating Cryptographic Ephemeral Share Pass...", flush=True)
        driver.get(f"{base_url}/share/create/")
        time.sleep(2)

        title_input = wait.until(EC.presence_of_element_located((By.NAME, "title")))
        title_input.send_keys("Dr. Harrison Cardiology Consult")

        doc_boxes = driver.find_elements(By.CSS_SELECTOR, "input[name='documents']")
        if doc_boxes:
            driver.execute_script("arguments[0].click();", doc_boxes[0])

        dl_toggle = driver.find_elements(By.CSS_SELECTOR, "input[name='can_download']")
        if dl_toggle:
            driver.execute_script("arguments[0].click();", dl_toggle[0])

        capture_step(driver, "08_share_create_form.png", "Share Pass Creation Form")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2.5)

        # Share pass detail view
        capture_step(driver, "09_share_pass_detail_qr.png", "Generated Ephemeral QR & Share Key")

        raw_key = ""
        key_elems = driver.find_elements(By.ID, "shareKeyText")
        if key_elems:
            raw_key = key_elems[0].text.strip()
        print(f" -> Generated Ephemeral Share Key: {raw_key}", flush=True)

        pass_url = driver.current_url
        pass_id = pass_url.rstrip("/").split("/")[-1]
        recipient_url = f"{base_url}/p/{pass_id}/"

        # -------------------------------------------------------------
        # 6. MOBILE RECIPIENT QR GATEWAY (SmartPhone Viewport)
        # -------------------------------------------------------------
        print("\n[STEP 6] Mobile Recipient Gateway & QR Verification (390x844)...", flush=True)
        driver.set_window_size(390, 844)
        driver.get(recipient_url)
        time.sleep(2)
        capture_step(driver, "10_mobile_recipient_verify.png", "Mobile QR Scan Landing Gateway")

        if raw_key:
            key_field = wait.until(EC.presence_of_element_located((By.NAME, "access_key")))
            key_field.send_keys(raw_key)
            capture_step(driver, "11_mobile_recipient_entered_key.png", "Mobile Key Entered")
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            time.sleep(2.5)

            # Mobile Decrypted Document Portal
            capture_step(driver, "12_mobile_recipient_portal.png", "Mobile Decrypted Document Portal with Timer")

            # Exit session
            exit_btn = driver.find_elements(By.CSS_SELECTOR, "form[action*='leave'] button, button.btn-secondary")
            if exit_btn:
                driver.execute_script("arguments[0].click();", exit_btn[0])
                time.sleep(1.5)
                capture_step(driver, "13_mobile_session_terminated.png", "Mobile Recipient Memory Cleansed")

        # -------------------------------------------------------------
        # 7. SECURITY AUDIT TRAIL
        # -------------------------------------------------------------
        print("\n[STEP 7] Security Audit Trail...", flush=True)
        driver.set_window_size(1280, 850)
        driver.get(f"{base_url}/audit/")
        time.sleep(2)
        capture_step(driver, "14_owner_audit_trail.png", "Structured Security Audit Trail")

        # -------------------------------------------------------------
        # 8. CUSTOM ADMINISTRATION DASHBOARDS
        # -------------------------------------------------------------
        print("\n[STEP 8] Custom Platform Administration Consoles...", flush=True)

        driver.get(f"{base_url}/admin-dashboard/")
        time.sleep(2)
        capture_step(driver, "15_admin_telemetry_overview.png", "Admin Overview & System Telemetry")

        driver.get(f"{base_url}/admin-dashboard/users/")
        time.sleep(2)
        capture_step(driver, "16_admin_user_governance.png", "Admin User Governance Directory")

        driver.get(f"{base_url}/admin-dashboard/documents/")
        time.sleep(2)
        capture_step(driver, "17_admin_file_vault.png", "Admin Global Vault Explorer")

        driver.get(f"{base_url}/admin-dashboard/passes/")
        time.sleep(2)
        capture_step(driver, "18_admin_passes_monitor.png", "Admin Global Active Passes Monitor")

        driver.get(f"{base_url}/admin-dashboard/audit/")
        time.sleep(2)
        capture_step(driver, "19_admin_global_audit.png", "Admin Global Security Audit Stream")

        # -------------------------------------------------------------
        # 9. COMPILE ANIMATED GIF / DEMO ARTIFACT
        # -------------------------------------------------------------
        print("\n[STEP 9] Compiling High-Resolution Animated Demo...", flush=True)
        screenshot_files = sorted(SCREENSHOTS_DIR.glob("*.png"))
        if screenshot_files:
            images = [Image.open(f) for f in screenshot_files]
            standard_size = (1080, 700)
            resized_images = [img.convert("RGB").resize(standard_size, Image.Resampling.LANCZOS) for img in images]

            gif_path = SCREENSHOTS_DIR / "passli_full_walkthrough_demo.gif"
            resized_images[0].save(
                str(gif_path),
                save_all=True,
                append_images=resized_images[1:],
                duration=1800,  # 1.8 seconds per screen
                loop=0
            )
            print(f"[SUCCESS] Animated Walkthrough Demo created: {gif_path.resolve()}", flush=True)

        print("\n" + "=" * 70, flush=True)
        print(f"  ALL {len(screenshot_files)} DEMONSTRATION VIEWS & MOBILE QR FLOW RECORDED SUCCESSFULLY!", flush=True)
        print("=" * 70 + "\n", flush=True)

    finally:
        driver.quit()


if __name__ == "__main__":
    run_walkthrough()
