import io
import os
from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageFont
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

BASE_URL = "http://127.0.0.1:8000"
ASSETS_DIR = Path(".github/assets")
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
DRIVER_PATH = r"C:\Users\Ali Nawaz\.cache\selenium\chromedriver\win64\155.0.8059.79\chromedriver.exe"


def get_headless_driver(w=1440, h=900):
    service = Service(executable_path=DRIVER_PATH)
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument(f"--window-size={w},{h}")
    opts.add_argument("--force-device-scale-factor=1")
    opts.add_argument("--hide-scrollbars")
    return webdriver.Chrome(service=service, options=opts)


def frame_browser_window(screenshot_img, url="https://passli.dev/dashboard/", title="Passli Personal Vault"):
    """Wraps an actual site screenshot in a sleek, modern browser window frame."""
    sw, sh = screenshot_img.size
    header_h = 42
    fw = sw
    fh = sh + header_h

    framed = Image.new("RGBA", (fw, fh), (255, 255, 255, 0))
    draw = ImageDraw.Draw(framed)

    # Outer container with rounded top corners
    draw.rounded_rectangle([0, 0, fw, fh], radius=10, fill=(248, 250, 252), outline=(226, 232, 240), width=1)

    # Header bar
    draw.rounded_rectangle([0, 0, fw, header_h + 10], radius=10, fill=(241, 245, 249))
    draw.rectangle([0, header_h, fw, header_h + 1], fill=(226, 232, 240))

    # Traffic lights (macOS style window buttons)
    colors = [(239, 68, 68), (245, 158, 11), (16, 185, 129)]
    bx = 16
    for c in colors:
        draw.ellipse([bx, 15, bx + 12, 27], fill=c)
        bx += 20

    # Address bar
    try:
        font_bar = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 13)
    except Exception:
        font_bar = ImageFont.load_default()

    url_box_w = 420
    ux = (fw - url_box_w) // 2
    draw.rounded_rectangle(
        [ux, 8, ux + url_box_w, 34], radius=6, fill=(255, 255, 255), outline=(203, 213, 225), width=1
    )

    # Draw vector padlock icon (emerald green)
    lx = ux + 14
    ly = 15
    draw.rounded_rectangle([lx, ly + 4, lx + 10, ly + 13], radius=2, fill=(16, 185, 129))
    draw.arc([lx + 2, ly, lx + 8, ly + 8], start=180, end=0, fill=(16, 185, 129), width=2)

    draw.text((ux + 32, 13), url, font=font_bar, fill=(71, 85, 105))

    # Paste the real screenshot below header
    framed.paste(screenshot_img, (0, header_h))
    return framed.convert("RGB")


def capture_real_dashboard_and_vault():
    print("1. Capturing REAL Personal Vault Dashboard and Encrypted Documents...")
    driver = get_headless_driver(1440, 900)

    # Authenticate as qa_test_user
    driver.get(f"{BASE_URL}/login/")
    time.sleep(1.5)
    driver.find_element(By.ID, "login-username").send_keys("qa_test_user")
    driver.find_element(By.ID, "login-password").send_keys("PassliQA2026!Secure")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(2)

    # We are on the Dashboard
    dash_bytes = driver.get_screenshot_as_png()
    dash_img = Image.open(io.BytesIO(dash_bytes))

    # Save framed dashboard preview
    framed_dash = frame_browser_window(dash_img, "https://passli.dev/dashboard/")
    # Resize cleanly to 1376x768 or standard 16:9
    framed_dash_16_9 = framed_dash.resize((1376, 768), Image.Resampling.LANCZOS)
    framed_dash_16_9.save(str(ASSETS_DIR / "passli-dashboard-preview.png"), "PNG", optimize=True)
    print("Saved real passli-dashboard-preview.png (framed from actual site)")

    # Now go to /documents/
    driver.get(f"{BASE_URL}/documents/")
    time.sleep(1.5)
    doc_bytes = driver.get_screenshot_as_png()
    doc_img = Image.open(io.BytesIO(doc_bytes))
    framed_doc = frame_browser_window(doc_img, "https://passli.dev/documents/")
    framed_doc_16_9 = framed_doc.resize((1376, 768), Image.Resampling.LANCZOS)
    framed_doc_16_9.save(str(ASSETS_DIR / "passli-vault-documents.png"), "PNG", optimize=True)
    print("Saved real passli-vault-documents.png (framed from actual site)")

    driver.quit()
    return dash_img


def record_real_simulator_gif():
    print("2. Recording REAL interactive simulator GIF from actual DOM elements...")
    driver = get_headless_driver(1440, 960)
    driver.get(BASE_URL)
    time.sleep(2)

    card = driver.find_element(By.CSS_SELECTOR, ".generator-card")
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", card)
    time.sleep(1)

    checkboxes = driver.find_elements(By.CSS_SELECTOR, ".sim-doc-checkbox")
    expiry_btns = driver.find_elements(By.CSS_SELECTOR, ".expiry-btn")
    gen_btn = driver.find_element(By.ID, "sim-generate-btn")

    raw_frames = []

    def snap(count=1):
        for _ in range(count):
            buf = card.screenshot_as_png
            im = Image.open(io.BytesIO(buf))
            raw_frames.append(im)
            time.sleep(0.08)

    # Initial state (2 docs selected, 30m active)
    snap(6)

    # Toggle 3rd checkbox (Vehicle Registration)
    if len(checkboxes) > 2:
        driver.execute_script("arguments[0].click();", checkboxes[2])
        time.sleep(0.2)
        snap(6)

    # Toggle 2nd checkbox off
    if len(checkboxes) > 1:
        driver.execute_script("arguments[0].click();", checkboxes[1])
        time.sleep(0.2)
        snap(5)

    # Click 15 mins expiry
    if expiry_btns:
        driver.execute_script("arguments[0].click();", expiry_btns[0])
        time.sleep(0.2)
        snap(6)

    # Click Generate / Re-encrypt Key
    driver.execute_script("arguments[0].click();", gen_btn)
    time.sleep(0.1)
    snap(12)

    # Click 24 hours expiry
    if len(expiry_btns) > 3:
        driver.execute_script("arguments[0].click();", expiry_btns[3])
        time.sleep(0.2)
        snap(6)

    # Re-click generate
    driver.execute_script("arguments[0].click();", gen_btn)
    time.sleep(0.1)
    snap(10)

    driver.quit()

    # Wrap each frame in a subtle card container for maximum clarity
    processed_frames = []
    for f in raw_frames:
        # Scale to crisp 1000px width
        fw, fh = f.size
        target_w = 980
        target_h = int(fh * (target_w / fw))
        scaled = f.resize((target_w, target_h), Image.Resampling.LANCZOS)

        # Frame with 1px border and soft shadow
        pad_x = 24
        pad_y = 20
        canvas = Image.new("RGB", (target_w + pad_x * 2, target_h + pad_y * 2), (248, 250, 252))
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(
            [pad_x - 1, pad_y - 1, pad_x + target_w + 1, pad_y + target_h + 1],
            radius=12,
            fill=(255, 255, 255),
            outline=(226, 232, 240),
            width=1,
        )
        canvas.paste(scaled, (pad_x, pad_y))
        processed_frames.append(canvas)

    out_gif = ASSETS_DIR / "passli-ephemeral-workflow.gif"
    processed_frames[0].save(
        str(out_gif), save_all=True, append_images=processed_frames[1:], duration=180, loop=0, optimize=True
    )
    print(f"Saved real passli-ephemeral-workflow.gif: {len(processed_frames)} frames, {os.path.getsize(out_gif)} bytes")


def build_authentic_hero_banner(dash_raw_img=None):
    print("3. Building authentic Hero Banner featuring the Passli visual identity...")
    from scripts.generate_banner import generate_identity_banner

    return generate_identity_banner()


if __name__ == "__main__":
    dash_raw = capture_real_dashboard_and_vault()
    record_real_simulator_gif()
    build_authentic_hero_banner(dash_raw)
    print("All authentic real site assets generated!")
