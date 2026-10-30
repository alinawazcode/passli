import os
import math
from PIL import Image, ImageDraw, ImageFont

# Canvas dimensions
WIDTH = 1100
HEIGHT = 580
FPS = 12
BG_COLOR = (11, 15, 23)  # #0B0F17 Deep obsidian
CARD_BG = (17, 24, 39)  # #111827 Dark slate
CARD_BORDER = (31, 41, 55)  # #1F2937 Hairline border
ACCENT_GREEN = (16, 185, 129)  # #10B981 Emerald
ACCENT_CYAN = (6, 182, 212)  # #06B6D4 Electric cyan
TEXT_WHITE = (248, 250, 252)  # #F8FAFC
TEXT_MUTED = (148, 163, 184)  # #94A3B8
TEXT_DIM = (100, 116, 139)  # #64748B
RED_REVOKE = (239, 68, 68)  # #EF4444
GOLD_WARN = (245, 158, 11)  # #F59E0B

# Load fonts
try:
    font_title = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 26)
    font_heading = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 20)
    font_sub = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 15)
    font_bold = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 15)
    font_mono_large = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 32)
    font_mono = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 14)
    font_badge = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 12)
    font_small = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 12)
except Exception:
    font_title = font_heading = font_sub = font_bold = font_mono_large = font_mono = font_badge = font_small = (
        ImageFont.load_default()
    )


def draw_rounded_rect(draw, bbox, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline, width=width)


def draw_header(draw, active_tab="Share Pass"):
    # App Header Bar
    draw.rectangle([0, 0, WIDTH, 54], fill=(15, 23, 42))
    draw.line([0, 54, WIDTH, 54], fill=(30, 41, 59), width=1)

    # Shield mark icon
    sx, sy = 24, 16
    draw.polygon(
        [(sx + 10, sy), (sx + 20, sy + 4), (sx + 20, sy + 14), (sx + 10, sy + 22), (sx, sy + 14), (sx, sy + 4)],
        outline=ACCENT_GREEN,
        fill=(16, 185, 129, 40),
    )
    draw.ellipse([sx + 8, sy + 8, sx + 12, sy + 12], fill=ACCENT_GREEN)

    # Brand Text
    draw.text((sx + 28, sy - 2), "Passli", font=font_heading, fill=TEXT_WHITE)
    draw.text((sx + 95, sy + 3), "Cryptographic Document Vault", font=font_sub, fill=TEXT_MUTED)

    # Tabs
    tabs = ["Dashboard", "Documents", "Share Passes", "Audit Log"]
    tx = 440
    for t in tabs:
        is_active = t == active_tab or (active_tab.startswith("Share") and t == "Share Passes")
        col = TEXT_WHITE if is_active else TEXT_DIM
        draw.text((tx, sy + 2), t, font=font_sub, fill=col)
        if is_active:
            tw = int(draw.textlength(t, font=font_sub))
            draw.line([tx, 53, tx + tw, 53], fill=ACCENT_GREEN, width=2)
        tx += 130

    # User status pill
    draw_rounded_rect(draw, [WIDTH - 170, 12, WIDTH - 24, 42], radius=15, fill=(30, 41, 59), outline=(51, 65, 85))
    draw.ellipse([WIDTH - 160, 20, WIDTH - 146, 34], fill=ACCENT_GREEN)
    draw.text((WIDTH - 138, 19), "qa_vault_user", font=font_badge, fill=TEXT_WHITE)


def draw_qr_code(draw, x, y, size=140, scan_pos=None):
    # Stylized clean QR Code matrix
    draw_rounded_rect(draw, [x, y, x + size, y + size], radius=8, fill=(255, 255, 255), outline=(203, 213, 225))

    # Outer markers
    def marker(mx, my):
        draw.rectangle([mx, my, mx + 28, my + 28], fill=(11, 15, 23))
        draw.rectangle([mx + 4, my + 4, mx + 24, my + 24], fill=(255, 255, 255))
        draw.rectangle([mx + 8, my + 8, mx + 20, my + 20], fill=(11, 15, 23))

    marker(x + 10, y + 10)
    marker(x + size - 38, y + 10)
    marker(x + 10, y + size - 38)

    # Pseudo-random deterministic grid dots
    import random

    rng = random.Random(42)
    step = 7
    for gx in range(x + 12, x + size - 12, step):
        for gy in range(y + 12, y + size - 12, step):
            if (
                (gx < x + 44 and gy < y + 44)
                or (gx > x + size - 46 and gy < y + 44)
                or (gx < x + 44 and gy > y + size - 46)
            ):
                continue
            if rng.random() > 0.45:
                draw.rectangle([gx, gy, gx + 4, gy + 4], fill=(15, 23, 42))

    # Animated scanline effect
    if scan_pos is not None:
        scan_y = int(y + 8 + (size - 16) * scan_pos)
        draw.line([x + 4, scan_y, x + size - 4, scan_y], fill=ACCENT_CYAN, width=3)
        draw.line([x + 6, scan_y - 1, x + size - 6, scan_y - 1], fill=(6, 182, 212, 100), width=1)
        draw.line([x + 6, scan_y + 1, x + size - 6, scan_y + 1], fill=(6, 182, 212, 100), width=1)


frames = []

# ==========================================
# SCENE 1: Owner Configures Pass (Frames 0-14)
# ==========================================
for i in range(15):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, active_tab="Share Passes")

    # Main container card
    draw_rounded_rect(draw, [50, 75, WIDTH - 50, HEIGHT - 35], radius=12, fill=CARD_BG, outline=CARD_BORDER)

    # Step Breadcrumbs / Progress
    draw.text((80, 95), "STEP 1 OF 3", font=font_badge, fill=ACCENT_CYAN)
    draw.text((80, 115), "Create Ephemeral Share Pass", font=font_title, fill=TEXT_WHITE)
    draw.text(
        (80, 148),
        "Select encrypted vault documents and enforce zero-persistence TTL duration.",
        font=font_sub,
        fill=TEXT_MUTED,
    )

    # Left Column: Document Selection Checklist
    draw.text((80, 185), "1. Included Vault Documents", font=font_heading, fill=TEXT_WHITE)

    docs = [
        ("Medical_Lab_Results_2025.pdf", "Medical Records", "SHA256: 8f4a...29b1", True),
        ("Passport_Identity_Scan.pdf", "Personal & Identity", "SHA256: 3c9e...5402", True),
        ("Vehicle_Registration_Title.pdf", "Vehicle & Asset", "SHA256: e7a1...8d12", i >= 6),
    ]
    dy = 220
    for doc_name, cat, sha, checked in docs:
        b_color = (30, 41, 59) if checked else (20, 27, 45)
        border = ACCENT_GREEN if checked else (45, 55, 72)
        draw_rounded_rect(draw, [80, dy, 520, dy + 55], radius=8, fill=b_color, outline=border)
        # Checkbox
        cb_fill = ACCENT_GREEN if checked else None
        draw_rounded_rect(
            draw, [96, dy + 18, 116, dy + 38], radius=4, fill=cb_fill, outline=ACCENT_GREEN if checked else TEXT_DIM
        )
        if checked:
            draw.text((101, dy + 18), "✓", font=font_badge, fill=(11, 15, 23))
        # Doc Details
        draw.text((130, dy + 10), doc_name, font=font_bold, fill=TEXT_WHITE)
        draw.text((130, dy + 30), f"{cat}  •  {sha}", font=font_small, fill=TEXT_MUTED)
        dy += 65

    # Right Column: Expiration & Access Constraints
    draw.text((570, 185), "2. Time-To-Live & Access Policy", font=font_heading, fill=TEXT_WHITE)

    # TTL Pills
    ttls = [("15 mins", True), ("30 mins", False), ("1 hour", False), ("24 hours", False), ("Single View", False)]
    px = 570
    py = 220
    for label, is_sel in ttls:
        pw = int(draw.textlength(label, font=font_badge)) + 26
        fill = (16, 185, 129, 35) if is_sel else (30, 41, 59)
        border = ACCENT_GREEN if is_sel else (51, 65, 85)
        draw_rounded_rect(draw, [px, py, px + pw, py + 34], radius=6, fill=fill, outline=border)
        draw.text((px + 13, py + 8), label, font=font_badge, fill=ACCENT_GREEN if is_sel else TEXT_MUTED)
        px += pw + 10
        if px > WIDTH - 120:
            px = 570
            py += 44

    # Permissions Box
    draw_rounded_rect(draw, [570, 280, WIDTH - 80, 370], radius=8, fill=(15, 23, 42), outline=(30, 41, 59))
    draw.text((585, 292), "🔒 Permissions & Security Guarantees", font=font_bold, fill=TEXT_WHITE)
    draw.text((585, 316), "• In-Browser Decrypted Preview Stream: Enabled", font=font_sub, fill=ACCENT_CYAN)
    draw.text((585, 338), "• Raw File Download: Disabled (View-Only Mode)", font=font_sub, fill=TEXT_MUTED)

    # CTA Button with animated click on frames 12-14
    btn_color = (5, 150, 105) if i >= 12 else ACCENT_GREEN
    btn_w = 340
    btn_rect = [570, 400, 570 + btn_w, 448]
    draw_rounded_rect(draw, btn_rect, radius=8, fill=btn_color)
    btn_txt = "Generating Ephemeral Pass..." if i >= 12 else "Generate Ephemeral Share Pass →"
    tw = int(draw.textlength(btn_txt, font=font_bold))
    draw.text((570 + (btn_w - tw) // 2, 414), btn_txt, font=font_bold, fill=(11, 15, 23))

    frames.append(img)

# ==========================================
# SCENE 2: Cryptographic Key & QR Generated (Frames 15-32)
# ==========================================
token_target = "7K9X-2M4P"
for i in range(18):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, active_tab="Share Passes")

    draw_rounded_rect(draw, [50, 75, WIDTH - 50, HEIGHT - 35], radius=12, fill=CARD_BG, outline=CARD_BORDER)

    draw.text((80, 95), "STEP 2 OF 3", font=font_badge, fill=ACCENT_GREEN)
    draw.text((80, 115), "Share Pass Cryptographically Issued", font=font_title, fill=TEXT_WHITE)
    draw.text(
        (80, 148),
        "Zero-Knowledge Key hashed via PBKDF2. Distribute key and QR to recipient.",
        font=font_sub,
        fill=TEXT_MUTED,
    )

    # Left Card: The Ephemeral Key Box
    draw_rounded_rect(draw, [80, 190, 580, 480], radius=10, fill=(15, 23, 42), outline=CARD_BORDER)

    draw.text((105, 210), "EPHEMERAL SHARE KEY (ONE-TIME)", font=font_badge, fill=ACCENT_CYAN)

    # Key Typewriter effect
    num_chars = min(len(token_target), max(1, (i * 2)))
    curr_token = token_target[:num_chars]
    cursor = "_" if (i % 4 < 2 and num_chars < len(token_target)) else ""

    draw_rounded_rect(draw, [105, 235, 555, 305], radius=8, fill=(11, 15, 23), outline=ACCENT_GREEN)
    draw.text((125, 250), curr_token + cursor, font=font_mono_large, fill=ACCENT_GREEN)

    # Security Badges
    draw.text((105, 325), "🛡️ Cryptographic Parameter Summary", font=font_bold, fill=TEXT_WHITE)
    badges = [
        "Plaintext Zero-Knowledge: Stored as Salted PBKDF2-HMAC-SHA256",
        "Document Encryption: AES-256-GCM AEAD (UUID Bound AAD)",
        "Session Lifespan: 15 Minutes (Strict server-side enforcement)",
        "Rate-Limiting Defense: 5 Failed Attempts -> Exponential Lockout",
    ]
    by = 350
    for b in badges:
        draw.text((105, by), f"• {b}", font=font_small, fill=TEXT_MUTED)
        by += 24

    # 1-Click Revoke button
    draw_rounded_rect(draw, [105, 435, 300, 465], radius=6, fill=(239, 68, 68, 40), outline=RED_REVOKE)
    draw.text((120, 442), "⚡ 1-Click Immediate Revoke", font=font_badge, fill=RED_REVOKE)

    # Right Card: The QR Code Display
    draw_rounded_rect(draw, [620, 190, WIDTH - 80, 480], radius=10, fill=(15, 23, 42), outline=CARD_BORDER)
    draw.text((645, 210), "ISOLATED RECIPIENT QR PROTOCOL", font=font_badge, fill=TEXT_MUTED)

    # Draw QR code with moving scanline
    scan_pos = (i % 12) / 12.0
    draw_qr_code(draw, 720, 245, size=180, scan_pos=scan_pos)

    draw.text((670, 440), "Recipient scans QR + enters 8-char key", font=font_sub, fill=TEXT_WHITE)

    frames.append(img)

# ==========================================
# SCENE 3: Recipient Unlocked & In-Memory Streaming (Frames 33-47)
# ==========================================
countdown_secs = [900 - s for s in range(15)]
for i in range(15):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, active_tab="Recipient Portal")

    draw_rounded_rect(draw, [50, 75, WIDTH - 50, HEIGHT - 35], radius=12, fill=CARD_BG, outline=CARD_BORDER)

    # Active portal banner
    draw.text((80, 95), "STEP 3 OF 3: RECIPIENT SESSION ACTIVE", font=font_badge, fill=ACCENT_GREEN)
    draw.text((80, 115), "In-Memory Decrypted Document Portal", font=font_title, fill=TEXT_WHITE)
    draw.text(
        (80, 148),
        "Documents decrypted directly into volatile RAM (io.BytesIO). Zero disk exposure.",
        font=font_sub,
        fill=TEXT_MUTED,
    )

    # Countdown Widget Header
    rem = countdown_secs[i]
    mins = rem // 60
    secs = rem % 60
    timer_str = f"{mins:02d}:{secs:02d}"

    draw_rounded_rect(draw, [WIDTH - 260, 95, WIDTH - 80, 155], radius=10, fill=(15, 23, 42), outline=ACCENT_GREEN)
    draw.text((WIDTH - 245, 105), "SESSION TIME REMAINING", font=font_badge, fill=TEXT_MUTED)
    draw.text((WIDTH - 245, 122), timer_str, font=font_heading, fill=ACCENT_GREEN)

    # Document Preview Window
    draw_rounded_rect(draw, [80, 190, WIDTH - 80, 480], radius=10, fill=(15, 23, 42), outline=CARD_BORDER)

    # Document Selector Tabs
    doc_tabs = ["Medical_Lab_Results_2025.pdf", "Passport_Identity_Scan.pdf"]
    dx = 100
    for dt in doc_tabs:
        is_active = dt == doc_tabs[0]
        col = (16, 185, 129, 40) if is_active else (25, 35, 55)
        border = ACCENT_GREEN if is_active else (45, 55, 75)
        draw_rounded_rect(draw, [dx, 205, dx + 260, 240], radius=6, fill=col, outline=border)
        draw.text((dx + 12, 215), dt[:26], font=font_badge, fill=TEXT_WHITE if is_active else TEXT_MUTED)
        dx += 275

    # Simulated In-Memory PDF Page
    draw_rounded_rect(draw, [100, 255, WIDTH - 100, 460], radius=8, fill=(24, 32, 47), outline=(45, 55, 72))

    # Document Preview Content Header
    draw.text((120, 275), "DIAGNOSTIC PATHOLOGY LABORATORY REPORT", font=font_bold, fill=TEXT_WHITE)
    draw.text(
        (120, 298), "Patient: [Protected User Identity]   |   Specimen ID: #88204-PX", font=font_sub, fill=TEXT_MUTED
    )
    draw.line([120, 325, WIDTH - 120, 325], fill=(45, 55, 72), width=1)

    # Preview Lines
    lines = [
        "Hematology Comprehensive Metabolic Panel: Normal (4.8 mEq/L)",
        "Platelet Count & Serum Glucose: Within Baseline Reference Range",
        "Cryptographic Digest Verification: SHA-256 Validated • Authenticated AES-256-GCM AEAD",
        "Delivery Header: Cache-Control: no-store, private • Content-Security-Policy: sandbox",
    ]
    ly = 340
    for line_text in lines:
        draw.text((120, ly), line_text, font=font_mono, fill=(203, 213, 225))
        ly += 22

    # Exit / Wipe session button
    draw_rounded_rect(draw, [WIDTH - 260, 415, WIDTH - 120, 448], radius=6, fill=(239, 68, 68, 30), outline=RED_REVOKE)
    draw.text((WIDTH - 245, 424), "Leave & Purge Session", font=font_badge, fill=RED_REVOKE)

    frames.append(img)

# ==========================================
# SCENE 4: Session Revoked / Purged (Frames 48-56)
# ==========================================
for i in range(10):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, active_tab="Share Passes")

    draw_rounded_rect(draw, [50, 75, WIDTH - 50, HEIGHT - 35], radius=12, fill=CARD_BG, outline=CARD_BORDER)

    # Revocation Alert Modal
    draw_rounded_rect(draw, [250, 140, WIDTH - 250, 430], radius=12, fill=(15, 23, 42), outline=RED_REVOKE, width=2)

    # Red lock symbol
    draw.ellipse([WIDTH // 2 - 30, 170, WIDTH // 2 + 30, 230], fill=(239, 68, 68, 40), outline=RED_REVOKE, width=2)
    draw.text((WIDTH // 2 - 8, 188), "✕", font=font_heading, fill=RED_REVOKE)

    # Message
    draw.text((WIDTH // 2 - 140, 255), "Share Pass Revoked & Purged", font=font_heading, fill=TEXT_WHITE)
    draw.text(
        (WIDTH // 2 - 210, 290),
        "This ephemeral session has been immediately severed by the owner.",
        font=font_sub,
        fill=TEXT_MUTED,
    )
    draw.text(
        (WIDTH // 2 - 230, 315),
        "In-memory buffers cleared. Future access attempts return HTTP 404.",
        font=font_sub,
        fill=TEXT_MUTED,
    )

    # Structured Audit Badge
    draw_rounded_rect(
        draw, [WIDTH // 2 - 200, 355, WIDTH // 2 + 200, 395], radius=6, fill=(11, 15, 23), outline=(51, 65, 85)
    )
    draw.text((WIDTH // 2 - 180, 368), "AUDIT EVENT LOGGED: pass_revoked_by_owner", font=font_mono, fill=GOLD_WARN)

    frames.append(img)

# Save animated GIF
out_path = r".github\assets\passli-ephemeral-workflow.gif"
frames[0].save(out_path, save_all=True, append_images=frames[1:], duration=int(1000 / FPS), loop=0, optimize=True)

print(f"Generated {out_path}: {len(frames)} frames, {os.path.getsize(out_path)} bytes")
