import os
import sys
import time
from pathlib import Path
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "http://127.0.0.1:8000"
ASSETS_DIR = Path(".github/assets")
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

DRIVER_PATH = r"C:\Users\Ali Nawaz\.cache\selenium\chromedriver\win64\155.0.8059.79\chromedriver.exe"


def get_driver(width=1440, height=900):
    service = Service(executable_path=DRIVER_PATH)
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument(f"--window-size={width},{height}")
    opts.add_argument("--force-device-scale-factor=1")
    opts.add_argument("--hide-scrollbars")
    return webdriver.Chrome(service=service, options=opts)


def capture_landing_and_simulator():
    print("Capturing landing page and interactive sandbox...")
    driver = get_driver(1440, 960)
    driver.get(BASE_URL)
    time.sleep(2)

    # 1. Landing Hero
    driver.save_screenshot(str(ASSETS_DIR / "passli-landing-hero.png"))
    print("Saved passli-landing-hero.png")

    # 2. Find Interactive Demo Section
    try:
        demo_sec = driver.find_element(By.ID, "demo")
    except Exception:
        demo_sec = driver.find_element(
            By.XPATH, "//*[contains(text(), 'Interactive Sandbox') or contains(text(), 'Create Controlled Share Pass')]"
        )

    driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'start'});", demo_sec)
    time.sleep(1.5)

    # Take screenshot of the sandbox
    driver.save_screenshot(str(ASSETS_DIR / "passli-share-simulator.png"))
    print("Saved passli-share-simulator.png")

    # 3. Create animated GIF of the ACTUAL interactive sandbox in action
    print("Recording real interactive simulator animation frames...")
    frames = []

    # Locate checkboxes, expiration buttons, and generate button
    checkboxes = driver.find_elements(By.CSS_SELECTOR, ".sim-doc-checkbox, input[type='checkbox']")
    expiry_btns = driver.find_elements(By.CSS_SELECTOR, ".expiry-btn, button[data-expiry]")
    gen_btn = driver.find_element(By.CSS_SELECTOR, "#sim-generate-btn, button[id*='generate']")

    # Initial state
    for _ in range(4):
        driver.save_screenshot("temp_frame.png")
        frames.append(Image.open("temp_frame.png").copy())

    # Toggle second checkbox
    if len(checkboxes) > 1:
        driver.execute_script("arguments[0].click();", checkboxes[1])
        time.sleep(0.5)
        for _ in range(4):
            driver.save_screenshot("temp_frame.png")
            frames.append(Image.open("temp_frame.png").copy())

    # Click 15 mins expiry
    if expiry_btns:
        driver.execute_script("arguments[0].click();", expiry_btns[0])
        time.sleep(0.5)
        for _ in range(4):
            driver.save_screenshot("temp_frame.png")
            frames.append(Image.open("temp_frame.png").copy())

    # Click generate / refresh key button
    if gen_btn:
        driver.execute_script("arguments[0].click();", gen_btn)
        time.sleep(0.4)
        for _ in range(8):
            driver.save_screenshot("temp_frame.png")
            frames.append(Image.open("temp_frame.png").copy())
            time.sleep(0.1)

    # Click 30 mins
    if len(expiry_btns) > 1:
        driver.execute_script("arguments[0].click();", expiry_btns[1])
        time.sleep(0.5)
        for _ in range(6):
            driver.save_screenshot("temp_frame.png")
            frames.append(Image.open("temp_frame.png").copy())

    # Crop frames to the actual simulator card bounding box
    if frames and demo_sec:
        # Bounding box coordinates with padding
        cropped_frames = []
        for f in frames:
            # Crop to viewport
            cf = f.crop((0, 0, 1440, 850))
            cf.thumbnail((1100, 650), Image.Resampling.LANCZOS)
            cropped_frames.append(cf)

        cropped_frames[0].save(
            str(ASSETS_DIR / "passli-ephemeral-workflow.gif"),
            save_all=True,
            append_images=cropped_frames[1:],
            duration=250,
            loop=0,
            optimize=True,
        )
        print("Saved real passli-ephemeral-workflow.gif from actual site interaction!")

    driver.quit()


def capture_authenticated_pages():
    print("Logging into actual application...")
    driver = get_driver(1440, 900)
    driver.get(f"{BASE_URL}/login/")
    time.sleep(1.5)

    # Enter credentials
    user_input = driver.find_element(By.ID, "login-username")
    pass_input = driver.find_element(By.ID, "login-password")
    user_input.send_keys("qa_test_user")
    pass_input.send_keys("PassliQA2026!Secure")

    submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    submit_btn.click()
    time.sleep(2)

    # Now on Dashboard!
    print("Capturing actual Personal Vault Dashboard...")
    driver.save_screenshot(str(ASSETS_DIR / "passli-dashboard-preview.png"))
    print("Saved real passli-dashboard-preview.png")

    # Encrypted Document Vault
    print("Capturing actual Encrypted Document Vault...")
    driver.get(f"{BASE_URL}/documents/")
    time.sleep(1.5)
    driver.save_screenshot(str(ASSETS_DIR / "passli-vault-documents.png"))
    print("Saved real passli-vault-documents.png")

    # Create Share Pass page
    print("Capturing actual Create Share Pass Portal...")
    driver.get(f"{BASE_URL}/share/create/")
    time.sleep(1.5)
    driver.save_screenshot(str(ASSETS_DIR / "passli-share-create.png"))
    print("Saved real passli-share-create.png")

    # Audit Trail
    print("Capturing actual Security Audit Trail...")
    driver.get(f"{BASE_URL}/audit/")
    time.sleep(1.5)
    driver.save_screenshot(str(ASSETS_DIR / "passli-audit-trail.png"))
    print("Saved real passli-audit-trail.png")

    # Settings
    print("Capturing actual Account Settings...")
    driver.get(f"{BASE_URL}/settings/")
    time.sleep(1.5)
    driver.save_screenshot(str(ASSETS_DIR / "passli-settings-page.png"))
    print("Saved real passli-settings-page.png")

    driver.quit()


if __name__ == "__main__":
    capture_landing_and_simulator()
    capture_authenticated_pages()
    if os.path.exists("temp_frame.png"):
        os.remove("temp_frame.png")
    print("All actual site assets captured successfully!")
