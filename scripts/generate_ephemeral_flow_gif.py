"""
Deterministic Python Pillow generator for Passli Ephemeral Share Pass Protocol Walkthrough GIF.
Produces high-craft, anti-ai-slop animated walkthrough with exact 58 distinct frames.
Cross-platform compatible across Windows, Linux CI, and macOS.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Canvas dimensions & animation constants
WIDTH = 1100
HEIGHT = 580
FPS = 8
FRAME_DURATION_MS = int(1000 / FPS)  # 125ms per frame

# Passli Palette (True RGB values, avoiding RGBA on RGB mode)
BG_CANVAS = (11, 15, 23)  # #0B0F17 Deep obsidian
BG_SURFACE = (17, 24, 39)  # #111827 Dark slate
CARD_BG = (24, 33, 50)  # #182132 Elevated container
BORDER_HAIRLINE = (31, 41, 55)  # #1F2937 Border
BORDER_SUBTLE = (45, 55, 72)  # #2D3748 Border light

ACCENT_GREEN = (16, 185, 129)  # #10B981 Emerald
GREEN_BG = (16, 50, 42)  # Emerald background tint
ACCENT_CYAN = (6, 182, 212)  # #06B6D4 Electric cyan
CYAN_BG = (12, 45, 60)  # Cyan background tint
RED_REVOKE = (239, 68, 68)  # #EF4444 Ruby red
RED_BG = (55, 20, 25)  # Red background tint
GOLD_WARN = (245, 158, 11)  # #F59E0B Warning amber

TEXT_WHITE = (248, 250, 252)  # #F8FAFC
TEXT_MUTED = (148, 163, 184)  # #94A3B8
TEXT_DIM = (100, 116, 139)  # #64748B
TEXT_REVOKE = (254, 226, 226)  # High-contrast light pink for revoke buttons


def get_font(size, bold=False, mono=False):
    """Cross-platform font loader with fallback."""
    font_candidates = []
    if bold:
        font_candidates = [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "DejaVuSans-Bold.ttf",
            "Arial Bold.ttf",
        ]
    elif mono:
        font_candidates = [
            "C:/Windows/Fonts/consola.ttf",
            "C:/Windows/Fonts/cour.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
            "DejaVuSansMono.ttf",
            "Courier New.ttf",
        ]
    else:
        font_candidates = [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "DejaVuSans.ttf",
            "Arial.ttf",
        ]

    for cand in font_candidates:
        try:
            return ImageFont.truetype(cand, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


# Fonts
font_title = get_font(24, bold=True)
font_heading = get_font(18, bold=True)
font_sub = get_font(14, bold=False)
font_bold = get_font(14, bold=True)
font_mono_large = get_font(30, mono=True)
font_mono = get_font(13, mono=True)
font_badge = get_font(12, bold=True)
font_small = get_font(12, bold=False)


def draw_rounded_rect(draw, bbox, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline, width=width)


def draw_check_icon(draw, cx, cy, size=12, color=ACCENT_GREEN, width=2):
    """Draws a crisp geometric checkmark without font glyph dependencies."""
    draw.line([cx - size * 0.4, cy, cx - size * 0.1, cy + size * 0.35], fill=color, width=width)
    draw.line([cx - size * 0.1, cy + size * 0.35, cx + size * 0.45, cy - size * 0.35], fill=color, width=width)


def draw_x_icon(draw, cx, cy, size=14, color=RED_REVOKE, width=2):
    """Draws a crisp geometric 'X' mark."""
    draw.line([cx - size * 0.5, cy - size * 0.5, cx + size * 0.5, cy + size * 0.5], fill=color, width=width)
    draw.line([cx - size * 0.5, cy + size * 0.5, cx + size * 0.5, cy - size * 0.5], fill=color, width=width)


def draw_lock_icon(draw, cx, cy, size=14, color=ACCENT_CYAN):
    """Draws a crisp padlock icon."""
    body_w = size
    body_h = size * 0.75
    # Shackle
    draw.arc([cx - body_w * 0.35, cy - size * 0.7, cx + body_w * 0.35, cy], start=180, end=0, fill=color, width=2)
    # Body
    draw_rounded_rect(draw, [cx - body_w * 0.5, cy - 1, cx + body_w * 0.5, cy - 1 + body_h], radius=3, fill=color)
    # Keyhole
    draw.ellipse([cx - 2, cy + 3, cx + 2, cy + 7], fill=BG_CANVAS)


def draw_shield_icon(draw, cx, cy, size=16, color=ACCENT_GREEN):
    """Draws a geometric shield mark."""
    sx, sy = cx - size * 0.5, cy - size * 0.5
    pts = [
        (sx + size * 0.5, sy),
        (sx + size, sy + size * 0.22),
        (sx + size, sy + size * 0.65),
        (sx + size * 0.5, sy + size),
        (sx, sy + size * 0.65),
        (sx, sy + size * 0.22),
    ]
    draw.polygon(pts, fill=GREEN_BG, outline=color, width=2)
    draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=color)


def draw_lightning_icon(draw, cx, cy, size=12, color=RED_REVOKE):
    """Draws a crisp lightning bolt."""
    pts = [
        (cx + 2, cy - size * 0.5),
        (cx - size * 0.3, cy + 1),
        (cx, cy + 1),
        (cx - 2, cy + size * 0.5),
        (cx + size * 0.3, cy - 1),
        (cx, cy - 1),
    ]
    draw.polygon(pts, fill=color)


def draw_header(draw, active_tab="Share Passes"):
    """Draws top navigation bar."""
    draw.rectangle([0, 0, WIDTH, 54], fill=(15, 23, 42))
    draw.line([0, 54, WIDTH, 54], fill=BORDER_HAIRLINE, width=1)

    # Shield mark icon
    draw_shield_icon(draw, 36, 27, size=22, color=ACCENT_GREEN)

    # Brand Text
    draw.text((56, 15), "Passli", font=font_heading, fill=TEXT_WHITE)
    draw.text((120, 19), "Cryptographic Document Vault", font=font_sub, fill=TEXT_MUTED)

    # Tabs
    tabs = ["Dashboard", "Documents", "Share Passes", "Audit Log"]
    tx = 440
    for t in tabs:
        is_active = t == active_tab or (active_tab.startswith("Share") and t == "Share Passes")
        col = TEXT_WHITE if is_active else TEXT_DIM
        draw.text((tx, 18), t, font=font_sub, fill=col)
        if is_active:
            tw = int(draw.textlength(t, font=font_sub))
            draw.line([tx, 53, tx + tw, 53], fill=ACCENT_GREEN, width=2)
        tx += 130

    # User status pill
    draw_rounded_rect(draw, [WIDTH - 175, 12, WIDTH - 24, 42], radius=15, fill=(30, 41, 59), outline=BORDER_SUBTLE)
    draw.ellipse([WIDTH - 165, 20, WIDTH - 151, 34], fill=ACCENT_GREEN)
    draw.text((WIDTH - 142, 19), "qa_vault_user", font=font_badge, fill=TEXT_WHITE)


def draw_qr_code(draw, x, y, size=150, scan_pos=None):
    """Draws high-contrast QR code with animated cyan laser line."""
    draw_rounded_rect(draw, [x, y, x + size, y + size], radius=8, fill=(255, 255, 255), outline=(203, 213, 225))

    # Outer positioning markers
    def marker(mx, my):
        draw.rectangle([mx, my, mx + 28, my + 28], fill=(11, 15, 23))
        draw.rectangle([mx + 4, my + 4, mx + 24, my + 24], fill=(255, 255, 255))
        draw.rectangle([mx + 8, my + 8, mx + 20, my + 20], fill=(11, 15, 23))

    marker(x + 10, y + 10)
    marker(x + size - 38, y + 10)
    marker(x + 10, y + size - 38)

    # Deterministic patterned matrix
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
        draw.line([x + 6, scan_y - 1, x + size - 6, scan_y - 1], fill=(140, 240, 255), width=1)
        draw.line([x + 6, scan_y + 1, x + size - 6, scan_y + 1], fill=(140, 240, 255), width=1)


def generate_workflow_gif():
    frames = []

    # =========================================================================
    # SCENE 1: Owner Configures Pass (Frames 0-14, 15 frames)
    # Interactive selection with document check and button activation
    # =========================================================================
    for i in range(15):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_CANVAS)
        draw = ImageDraw.Draw(img)
        draw_header(draw, active_tab="Share Passes")

        # Main container card
        draw_rounded_rect(draw, [50, 75, WIDTH - 50, HEIGHT - 35], radius=12, fill=BG_SURFACE, outline=BORDER_HAIRLINE)

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

        # Animate selection of 3rd document at frame 6
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

            # Checkbox with geometric checkmark
            cb_fill = GREEN_BG if checked else (15, 23, 42)
            cb_border = ACCENT_GREEN if checked else TEXT_DIM
            draw_rounded_rect(draw, [96, dy + 18, 116, dy + 38], radius=4, fill=cb_fill, outline=cb_border)
            if checked:
                draw_check_icon(draw, 106, dy + 28, size=11, color=ACCENT_GREEN, width=2)

            # Doc Details
            draw.text((130, dy + 10), doc_name, font=font_bold, fill=TEXT_WHITE)
            draw.text((130, dy + 30), f"{cat}  •  {sha}", font=font_small, fill=TEXT_MUTED)
            dy += 65

        # Right Column: Expiration & Access Constraints
        draw.text((570, 185), "2. Time-To-Live & Access Policy", font=font_heading, fill=TEXT_WHITE)

        # TTL Pills (Proper high-contrast pre-blended colors)
        ttls = [("15 mins", True), ("30 mins", False), ("1 hour", False), ("24 hours", False), ("Single View", False)]
        px = 570
        py = 220
        for label, is_sel in ttls:
            pw = int(draw.textlength(label, font=font_badge)) + 26
            fill = GREEN_BG if is_sel else (30, 41, 59)
            border = ACCENT_GREEN if is_sel else BORDER_SUBTLE
            text_col = ACCENT_GREEN if is_sel else TEXT_MUTED
            draw_rounded_rect(draw, [px, py, px + pw, py + 34], radius=6, fill=fill, outline=border)
            draw.text((px + 13, py + 9), label, font=font_badge, fill=text_col)
            px += pw + 10
            if px > WIDTH - 120:
                px = 570
                py += 44

        # Permissions Box
        draw_rounded_rect(draw, [570, 280, WIDTH - 80, 370], radius=8, fill=(15, 23, 42), outline=BORDER_HAIRLINE)
        draw_lock_icon(draw, 595, 302, size=14, color=ACCENT_CYAN)
        draw.text((610, 292), "Permissions & Security Guarantees", font=font_bold, fill=TEXT_WHITE)
        draw.text((590, 318), "• In-Browser Decrypted Preview Stream: Enabled", font=font_sub, fill=ACCENT_CYAN)
        draw.text((590, 340), "• Raw File Download: Disabled (View-Only Mode)", font=font_sub, fill=TEXT_MUTED)

        # Dynamic Button with frame-specific state
        btn_w = 340
        btn_rect = [570, 400, 570 + btn_w, 448]
        if i < 11:
            btn_color = ACCENT_GREEN
            btn_txt = "Generate Ephemeral Share Pass →"
            txt_col = (11, 15, 23)
        elif i == 11:
            btn_color = (13, 148, 100)  # Active press state
            btn_txt = "Generate Ephemeral Share Pass →"
            txt_col = (11, 15, 23)
        else:
            btn_color = (5, 120, 85)  # Ingestion / hashing state
            btn_txt = f"Encrypting & Deriving Key ({i - 11}/3)..."
            txt_col = TEXT_WHITE

        draw_rounded_rect(draw, btn_rect, radius=8, fill=btn_color)
        tw = int(draw.textlength(btn_txt, font=font_bold))
        draw.text((570 + (btn_w - tw) // 2, 414), btn_txt, font=font_bold, fill=txt_col)

        # Subtle frame indicator / progress tick so every frame is unique
        draw.rectangle([WIDTH - 60, 85, WIDTH - 55, 87], fill=(15 + i * 2, 23, 42))

        frames.append(img)

    # =========================================================================
    # SCENE 2: Cryptographic Key & QR Generated (Frames 15-32, 18 frames)
    # Typewriter generation, moving laser scanline on QR
    # =========================================================================
    token_target = "7K9X-2M4P"
    for i in range(18):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_CANVAS)
        draw = ImageDraw.Draw(img)
        draw_header(draw, active_tab="Share Passes")

        draw_rounded_rect(draw, [50, 75, WIDTH - 50, HEIGHT - 35], radius=12, fill=BG_SURFACE, outline=BORDER_HAIRLINE)

        draw.text((80, 95), "STEP 2 OF 3", font=font_badge, fill=ACCENT_GREEN)
        draw.text((80, 115), "Share Pass Cryptographically Issued", font=font_title, fill=TEXT_WHITE)
        draw.text(
            (80, 148),
            "Zero-Knowledge Key hashed via PBKDF2. Distribute key and QR to recipient.",
            font=font_sub,
            fill=TEXT_MUTED,
        )

        # Left Card: Ephemeral Key Box
        draw_rounded_rect(draw, [80, 190, 580, 480], radius=10, fill=(15, 23, 42), outline=BORDER_HAIRLINE)
        draw.text((105, 210), "EPHEMERAL SHARE KEY (ONE-TIME)", font=font_badge, fill=ACCENT_CYAN)

        # Typewriter effect
        num_chars = min(len(token_target), max(1, (i * 2) if i < 5 else len(token_target)))
        curr_token = token_target[:num_chars]
        cursor = "_" if (i % 4 < 2 and num_chars < len(token_target)) else (" " if i % 2 == 0 else "")

        draw_rounded_rect(draw, [105, 235, 555, 305], radius=8, fill=(11, 15, 23), outline=ACCENT_GREEN)
        draw.text((125, 250), curr_token + cursor, font=font_mono_large, fill=ACCENT_GREEN)

        # Security Badges
        draw_shield_icon(draw, 115, 335, size=14, color=ACCENT_GREEN)
        draw.text((128, 326), "Cryptographic Parameter Summary", font=font_bold, fill=TEXT_WHITE)
        badges = [
            "Plaintext Zero-Knowledge: Stored as Salted PBKDF2-HMAC-SHA256",
            "Document Encryption: AES-256-GCM AEAD (UUID Bound AAD)",
            "Session Lifespan: 15 Minutes (Strict server-side enforcement)",
            "Rate-Limiting Defense: 5 Failed Attempts -> Exponential Lockout",
        ]
        by = 352
        for b in badges:
            draw.text((105, by), f"• {b}", font=font_small, fill=TEXT_MUTED)
            by += 24

        # 1-Click Revoke button (Proper dark red background, bright text)
        draw_rounded_rect(draw, [105, 435, 320, 465], radius=6, fill=RED_BG, outline=RED_REVOKE)
        draw_lightning_icon(draw, 120, 450, size=11, color=RED_REVOKE)
        draw.text((130, 442), "1-Click Immediate Revoke", font=font_badge, fill=TEXT_REVOKE)

        # Right Card: QR Code Display
        draw_rounded_rect(draw, [620, 190, WIDTH - 80, 480], radius=10, fill=(15, 23, 42), outline=BORDER_HAIRLINE)
        draw.text((645, 210), "ISOLATED RECIPIENT QR PROTOCOL", font=font_badge, fill=TEXT_MUTED)

        # Dynamic scanline position across frames
        scan_pos = (i % 12) / 12.0
        draw_qr_code(draw, 720, 245, size=180, scan_pos=scan_pos)

        draw.text((670, 442), "Recipient scans QR + enters 8-char key", font=font_sub, fill=TEXT_WHITE)

        frames.append(img)

    # =========================================================================
    # SCENE 3: Recipient Unlocked & In-Memory Streaming (Frames 33-47, 15 frames)
    # Live ticking timer (15:00 to 14:46) with decrypted document preview
    # =========================================================================
    countdown_start = 900  # 15 minutes = 900 seconds
    for i in range(15):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_CANVAS)
        draw = ImageDraw.Draw(img)
        draw_header(draw, active_tab="Recipient Portal")

        draw_rounded_rect(draw, [50, 75, WIDTH - 50, HEIGHT - 35], radius=12, fill=BG_SURFACE, outline=BORDER_HAIRLINE)

        # Active portal banner
        draw.text((80, 95), "STEP 3 OF 3: RECIPIENT SESSION ACTIVE", font=font_badge, fill=ACCENT_GREEN)
        draw.text((80, 115), "In-Memory Decrypted Document Portal", font=font_title, fill=TEXT_WHITE)
        draw.text(
            (80, 148),
            "Documents decrypted directly into volatile RAM (io.BytesIO). Zero disk exposure.",
            font=font_sub,
            fill=TEXT_MUTED,
        )

        # Live Countdown Widget with ticking seconds
        rem = countdown_start - i
        mins = rem // 60
        secs = rem % 60
        timer_str = f"{mins:02d}:{secs:02d}"

        draw_rounded_rect(draw, [WIDTH - 260, 95, WIDTH - 80, 155], radius=10, fill=(15, 23, 42), outline=ACCENT_GREEN)
        draw.text((WIDTH - 245, 105), "SESSION TIME REMAINING", font=font_badge, fill=TEXT_MUTED)
        draw.text((WIDTH - 245, 122), timer_str, font=font_heading, fill=ACCENT_GREEN)

        # Document Preview Window
        draw_rounded_rect(draw, [80, 190, WIDTH - 80, 480], radius=10, fill=(15, 23, 42), outline=BORDER_HAIRLINE)

        # Document Selector Tabs
        doc_tabs = ["Medical_Lab_Results_2025.pdf", "Passport_Identity_Scan.pdf"]
        dx = 100
        for dt in doc_tabs:
            is_active = dt == doc_tabs[0]
            col = GREEN_BG if is_active else (25, 35, 55)
            border = ACCENT_GREEN if is_active else (45, 55, 75)
            draw_rounded_rect(draw, [dx, 205, dx + 260, 240], radius=6, fill=col, outline=border)
            draw.text((dx + 12, 215), dt[:26], font=font_badge, fill=TEXT_WHITE if is_active else TEXT_MUTED)
            dx += 275

        # Simulated In-Memory PDF Page
        draw_rounded_rect(draw, [100, 255, WIDTH - 100, 460], radius=8, fill=(24, 32, 47), outline=(45, 55, 72))

        # Document Preview Content Header
        draw.text((120, 275), "DIAGNOSTIC PATHOLOGY LABORATORY REPORT", font=font_bold, fill=TEXT_WHITE)
        draw.text(
            (120, 298),
            "Patient: [Protected User Identity]   |   Specimen ID: #88204-PX",
            font=font_sub,
            fill=TEXT_MUTED,
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

        # Exit / Wipe session button (Proper dark red background, bright text)
        btn_leave_rect = [WIDTH - 260, 415, WIDTH - 110, 448]
        draw_rounded_rect(draw, btn_leave_rect, radius=6, fill=RED_BG, outline=RED_REVOKE)
        draw_x_icon(draw, WIDTH - 245, 431, size=11, color=RED_REVOKE, width=2)
        draw.text((WIDTH - 232, 423), "Leave & Purge Session", font=font_badge, fill=TEXT_REVOKE)

        frames.append(img)

    # =========================================================================
    # SCENE 4: Session Revoked / Purged (Frames 48-57, 10 frames)
    # Animated revocation alert modal with pulsing red border & logged audit stamp
    # =========================================================================
    for i in range(10):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_CANVAS)
        draw = ImageDraw.Draw(img)
        draw_header(draw, active_tab="Share Passes")

        draw_rounded_rect(draw, [50, 75, WIDTH - 50, HEIGHT - 35], radius=12, fill=BG_SURFACE, outline=BORDER_HAIRLINE)

        # Revocation Alert Modal (animated border pulse)
        border_width = 2 if i % 2 == 0 else 3
        draw_rounded_rect(
            draw, [250, 140, WIDTH - 250, 430], radius=12, fill=(15, 23, 42), outline=RED_REVOKE, width=border_width
        )

        # Red lock symbol with white geometric 'X'
        circle_pulse = 28 + (i % 3)
        draw.ellipse(
            [WIDTH // 2 - circle_pulse, 195 - circle_pulse, WIDTH // 2 + circle_pulse, 195 + circle_pulse],
            fill=RED_BG,
            outline=RED_REVOKE,
            width=2,
        )
        draw_x_icon(draw, WIDTH // 2, 195, size=22, color=TEXT_WHITE, width=3)

        # Revocation Message
        draw.text((WIDTH // 2 - 145, 255), "Share Pass Revoked & Purged", font=font_heading, fill=TEXT_WHITE)
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

        # Structured Audit Badge with changing timestamp ticks
        draw_rounded_rect(
            draw, [WIDTH // 2 - 210, 355, WIDTH // 2 + 210, 395], radius=6, fill=(11, 15, 23), outline=BORDER_SUBTLE
        )
        ms_tick = 120 + i * 15
        draw.text(
            (WIDTH // 2 - 195, 368),
            f"AUDIT EVENT LOGGED: pass_revoked_by_owner (+{ms_tick}ms)",
            font=font_mono,
            fill=GOLD_WARN,
        )

        frames.append(img)

    # Save animated GIF using cross-platform path
    out_path = Path(__file__).resolve().parent.parent / ".github" / "assets" / "passli-ephemeral-workflow.gif"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Save all frames
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=False,  # Keep all 58 frames distinct
    )

    print(f"Generated {out_path}: {len(frames)} frames, {out_path.stat().st_size} bytes")


if __name__ == "__main__":
    generate_workflow_gif()
