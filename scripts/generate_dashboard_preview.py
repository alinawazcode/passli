"""
Generate high-fidelity, pixel-perfect preview of Passli Personal Vault Dashboard.
Adheres strictly to Passli anti-ai-slop design system, true domain taxonomy,
and 16:9 widescreen format (1376 x 768).
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Canvas dimensions (16:9)
WIDTH = 1376
HEIGHT = 768

# Passli Design System Tokens
BG_CANVAS = (11, 15, 23)  # #0B0F17 Deep Obsidian
BG_SURFACE = (17, 24, 39)  # #111827 Dark Slate Surface
BG_CARD = (24, 33, 50)  # #182132 Card Container
BORDER_HAIRLINE = (31, 41, 55)  # #1F2937 Hairline Border
BORDER_SUBTLE = (45, 55, 72)  # #2D3748 Elevated Border

ACCENT_EMERALD = (16, 185, 129)  # #10B981 Primary Brand Emerald
EMERALD_BG = (16, 50, 42)  # Subtle emerald container tint
ACCENT_CYAN = (6, 182, 212)  # #06B6D4 Electric Cyan
CYAN_BG = (12, 45, 60)  # Subtle cyan container tint
DANGER_RED = (239, 68, 68)  # #EF4444 Revocation Red
RED_BG = (55, 20, 25)  # Subtle red container tint
WARN_AMBER = (245, 158, 11)  # #F59E0B Warning Amber

TEXT_PRIMARY = (248, 250, 252)  # #F8FAFC Heading White
TEXT_SECONDARY = (148, 163, 184)  # #94A3B8 Muted Slate
TEXT_DIM = (100, 116, 139)  # #64748B Dim Slate


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


def draw_rounded_rect(draw, bbox, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline, width=width)


def draw_shield_logo(draw, sx, sy, size=24):
    """Draws Passli geometric shield mark."""
    pts = [
        (sx + size * 0.5, sy),
        (sx + size, sy + size * 0.22),
        (sx + size, sy + size * 0.65),
        (sx + size * 0.5, sy + size),
        (sx, sy + size * 0.65),
        (sx, sy + size * 0.22),
    ]
    draw.polygon(pts, fill=EMERALD_BG, outline=ACCENT_EMERALD, width=2)
    # Keyhole
    cx, cy = sx + size * 0.5, sy + size * 0.42
    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=ACCENT_EMERALD)
    draw.polygon([(cx - 2, cy), (cx + 2, cy), (cx + 3, cy + 6), (cx - 3, cy + 6)], fill=ACCENT_EMERALD)


def draw_check_icon(draw, cx, cy, size=12, color=ACCENT_EMERALD):
    draw.line([cx - size * 0.4, cy, cx - size * 0.1, cy + size * 0.35], fill=color, width=2)
    draw.line([cx - size * 0.1, cy + size * 0.35, cx + size * 0.45, cy - size * 0.35], fill=color, width=2)


def draw_qr_code(draw, x, y, size=110):
    """Draws a clean, crisp QR code graphic."""
    draw_rounded_rect(draw, [x, y, x + size, y + size], radius=6, fill=(255, 255, 255), outline=(226, 232, 240))

    # 3 Outer positioning markers
    def marker(mx, my):
        draw.rectangle([mx, my, mx + 24, my + 24], fill=(11, 15, 23))
        draw.rectangle([mx + 3, my + 3, mx + 21, my + 21], fill=(255, 255, 255))
        draw.rectangle([mx + 6, my + 6, mx + 18, my + 18], fill=(11, 15, 23))

    marker(x + 8, y + 8)
    marker(x + size - 32, y + 8)
    marker(x + 8, y + size - 32)

    # Deterministic patterned matrix
    import random

    rng = random.Random(1337)
    step = 5
    for gx in range(x + 10, x + size - 10, step):
        for gy in range(y + 10, y + size - 10, step):
            if (
                (gx < x + 34 and gy < y + 34)
                or (gx > x + size - 36 and gy < y + 34)
                or (gx < x + 34 and gy > y + size - 36)
            ):
                continue
            if rng.random() > 0.46:
                draw.rectangle([gx, gy, gx + 3, gy + 3], fill=(15, 23, 42))


def generate_dashboard():
    font_brand = get_font(20, bold=True)
    font_title = get_font(22, bold=True)
    font_body = get_font(13, bold=False)
    font_bold = get_font(13, bold=True)
    font_badge = get_font(11, bold=True)
    font_mono = get_font(11, mono=True)
    font_stat_val = get_font(28, bold=True)

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_CANVAS)
    draw = ImageDraw.Draw(img)

    # 1. Subtle Background Grid Texture
    for gx in range(0, WIDTH, 48):
        draw.line([gx, 0, gx, HEIGHT], fill=(15, 21, 32), width=1)
    for gy in range(0, HEIGHT, 48):
        draw.line([0, gy, WIDTH, gy], fill=(15, 21, 32), width=1)

    # 2. Top Header Navigation Bar
    draw.rectangle([0, 0, WIDTH, 56], fill=(15, 23, 42))
    draw.line([0, 56, WIDTH, 56], fill=BORDER_HAIRLINE, width=1)

    draw_shield_logo(draw, 32, 16, size=24)
    draw.text((64, 16), "Passli", font=font_brand, fill=TEXT_PRIMARY)
    draw.text((130, 20), "Cryptographic Document Vault", font=font_body, fill=TEXT_SECONDARY)

    # Nav Tabs
    tabs = [("Dashboard", True), ("Documents", False), ("Share Passes", False), ("Audit Log", False)]
    tx = 480
    for t_name, is_active in tabs:
        col = TEXT_PRIMARY if is_active else TEXT_DIM
        draw.text((tx, 19), t_name, font=font_body, fill=col)
        if is_active:
            tw = int(draw.textlength(t_name, font=font_body))
            draw.line([tx, 55, tx + tw, 55], fill=ACCENT_EMERALD, width=2)
        tx += 130

    # User Profile Avatar Badge
    draw_rounded_rect(draw, [WIDTH - 190, 10, WIDTH - 32, 46], radius=18, fill=(30, 41, 59), outline=BORDER_SUBTLE)
    draw.ellipse([WIDTH - 182, 16, WIDTH - 158, 40], fill=EMERALD_BG, outline=ACCENT_EMERALD)
    draw.text((WIDTH - 173, 20), "A", font=font_badge, fill=ACCENT_EMERALD)
    draw.text((WIDTH - 150, 20), "ali_nawaz", font=font_bold, fill=TEXT_PRIMARY)

    # 3. Security Status Strip
    draw_rounded_rect(draw, [32, 70, WIDTH - 32, 102], radius=6, fill=BG_SURFACE, outline=BORDER_HAIRLINE)
    status_items = [
        ("Vault Storage: AES-256-GCM AEAD", ACCENT_EMERALD),
        ("Key Derivation: PBKDF2-HMAC-SHA256 (100k iter)", ACCENT_CYAN),
        ("Ephemeral Protocol: Zero-Knowledge TTL Enforced", ACCENT_EMERALD),
        ("Audit Feed: Immutable DB Row Logging", (168, 85, 247)),
    ]
    sx = 50
    for s_text, dot_col in status_items:
        draw.ellipse([sx, 83, sx + 8, 91], fill=dot_col)
        draw.text((sx + 16, 79), s_text, font=font_mono, fill=TEXT_SECONDARY)
        sx += 320

    # 4. Metrics Stats Grid (4 Cards)
    stat_cards = [
        ("VAULT RECORDS", "12", "Encrypted personal files", ACCENT_CYAN),
        ("ACTIVE PASSES", "3", "Live time-gated access passes", ACCENT_EMERALD),
        ("TOTAL SHARES", "28", "Historical verified sessions", (168, 85, 247)),
        ("STORAGE METRICS", "18.4 MB", "of 512 MB vault quota used", (245, 158, 11)),
    ]
    card_w = (WIDTH - 64 - 36) // 4
    for idx, (label, val, sub, accent) in enumerate(stat_cards):
        cx = 32 + idx * (card_w + 12)
        draw_rounded_rect(draw, [cx, 116, cx + card_w, 206], radius=10, fill=BG_SURFACE, outline=BORDER_HAIRLINE)
        draw.text((cx + 18, 128), label, font=font_mono, fill=TEXT_DIM)
        draw.text((cx + 18, 146), val, font=font_stat_val, fill=accent)
        draw.text((cx + 18, 182), sub, font=font_body, fill=TEXT_SECONDARY)

        # Progress bar for storage
        if "STORAGE" in label:
            draw_rounded_rect(draw, [cx + 18, 175, cx + card_w - 18, 180], radius=2, fill=(30, 41, 59))
            draw_rounded_rect(draw, [cx + 18, 175, cx + 18 + int((card_w - 36) * 0.18), 180], radius=2, fill=accent)

    # 5. Main Content Split: Vault Records (Left 68%) + Active Ephemeral Passes Bento (Right 32%)
    split_x = int((WIDTH - 64) * 0.67) + 32
    left_w = split_x - 32 - 12
    right_x = split_x
    right_w = WIDTH - 32 - right_x

    # --- LEFT PANEL: Personal Vault Records ---
    draw_rounded_rect(draw, [32, 220, 32 + left_w, HEIGHT - 24], radius=10, fill=BG_SURFACE, outline=BORDER_HAIRLINE)
    draw.text((50, 236), "Encrypted Vault Records", font=font_title, fill=TEXT_PRIMARY)
    draw.text(
        (50, 264),
        "Protected with client-isolated AES-256-GCM AEAD encryption and SHA-256 integrity verification.",
        font=font_body,
        fill=TEXT_SECONDARY,
    )

    # Action buttons on top right of left panel
    btn_up_x = 32 + left_w - 240
    draw_rounded_rect(draw, [btn_up_x, 236, btn_up_x + 105, 270], radius=6, fill=(30, 41, 59), outline=BORDER_SUBTLE)
    draw.text((btn_up_x + 12, 244), "↑ Upload", font=font_bold, fill=TEXT_PRIMARY)

    draw_rounded_rect(draw, [btn_up_x + 115, 236, 32 + left_w - 18, 270], radius=6, fill=ACCENT_EMERALD)
    draw.text((btn_up_x + 126, 244), "+ New Pass", font=font_bold, fill=(11, 15, 23))

    # Document Grid Cards (2 columns x 3 rows)
    records = [
        ("Bloodwork_Metabolic_2025.pdf", "Medical Records", "1.4 MB", "8f4a3e...29b1", ACCENT_EMERALD),
        ("Passport_Identity_Scan.pdf", "Personal & Identity", "2.8 MB", "3c9e71...5402", ACCENT_CYAN),
        ("Vehicle_Title_Registration.pdf", "Vehicle & Asset", "3.1 MB", "e7a104...8d12", (245, 158, 11)),
        ("University_Degree_Honors.pdf", "Education & Degrees", "4.2 MB", "9b2d88...11c4", (168, 85, 247)),
        ("Employment_Contract_2024.pdf", "Professional", "840 KB", "5f1c42...77a8", (59, 130, 246)),
        ("Residential_Lease_Agreement.pdf", "Personal & Identity", "1.9 MB", "a4e619...92d0", ACCENT_CYAN),
    ]

    grid_cols = 2
    item_w = (left_w - 36 - 16) // 2
    item_h = 115

    for i, (fname, cat, fsize, sha, tag_col) in enumerate(records):
        row = i // grid_cols
        col = i % grid_cols
        rx = 50 + col * (item_w + 14)
        ry = 300 + row * (item_h + 12)

        draw_rounded_rect(draw, [rx, ry, rx + item_w, ry + item_h], radius=8, fill=BG_CARD, outline=BORDER_HAIRLINE)

        # Category Tag Badge
        tw = int(draw.textlength(cat, font=font_badge)) + 16
        draw_rounded_rect(
            draw, [rx + 14, ry + 12, rx + 14 + tw, ry + 30], radius=4, fill=(15, 23, 42), outline=BORDER_SUBTLE
        )
        draw.text((rx + 22, ry + 15), cat, font=font_badge, fill=tag_col)

        # File Size
        draw.text((rx + item_w - 65, ry + 15), fsize, font=font_mono, fill=TEXT_DIM)

        # File Name
        draw.text((rx + 14, ry + 40), fname, font=font_bold, fill=TEXT_PRIMARY)

        # Security Status line
        draw_check_icon(draw, rx + 20, ry + 70, size=10, color=ACCENT_EMERALD)
        draw.text((rx + 28, ry + 64), "AES-256-GCM Validated", font=font_mono, fill=ACCENT_EMERALD)
        draw.text((rx + item_w - 110, ry + 64), f"SHA: {sha}", font=font_mono, fill=TEXT_DIM)

        # Mini actions row
        draw.line([rx + 14, ry + 86, rx + item_w - 14, ry + 86], fill=BORDER_HAIRLINE, width=1)
        draw.text((rx + 14, ry + 93), "Preview Stream", font=font_badge, fill=ACCENT_CYAN)
        draw.text((rx + 115, ry + 93), "Download", font=font_badge, fill=TEXT_SECONDARY)
        draw.text((rx + item_w - 45, ry + 93), "Delete", font=font_badge, fill=TEXT_DIM)

    # --- RIGHT PANEL: Active Ephemeral Share Passes (Bento) ---
    draw_rounded_rect(
        draw, [right_x, 220, right_x + right_w, HEIGHT - 24], radius=10, fill=BG_SURFACE, outline=BORDER_HAIRLINE
    )
    draw.text((right_x + 18, 236), "Active Share Passes", font=font_title, fill=TEXT_PRIMARY)
    draw.text((right_x + 18, 264), "Time-gated zero-knowledge sessions.", font=font_body, fill=TEXT_SECONDARY)

    # Featured Active Pass Card
    px = right_x + 18
    py = 295
    pw = right_w - 36
    draw_rounded_rect(draw, [px, py, px + pw, py + 265], radius=8, fill=BG_CARD, outline=BORDER_SUBTLE)

    # Pass Title & Badge
    draw.text((px + 14, py + 14), "Clinic KYC Verification", font=font_bold, fill=TEXT_PRIMARY)
    draw_rounded_rect(
        draw, [px + pw - 90, py + 12, px + pw - 14, py + 30], radius=4, fill=EMERALD_BG, outline=ACCENT_EMERALD
    )
    draw.text((px + pw - 82, py + 15), "ACTIVE", font=font_badge, fill=ACCENT_EMERALD)

    # Live TTL Countdown Badge
    draw_rounded_rect(draw, [px + 14, py + 38, px + 175, py + 62], radius=6, fill=(15, 23, 42), outline=BORDER_HAIRLINE)
    draw.ellipse([px + 24, py + 47, px + 30, py + 53], fill=ACCENT_EMERALD)
    draw.text((px + 36, py + 43), "TTL: 14m 22s remaining", font=font_mono, fill=ACCENT_EMERALD)

    # QR Code Card
    draw_qr_code(draw, px + 14, py + 72, size=115)

    # Key derivation & security details beside QR
    kx = px + 142
    draw.text((kx, py + 74), "SHARE KEY (PBKDF2):", font=font_badge, fill=TEXT_DIM)
    draw_rounded_rect(draw, [kx, py + 92, px + pw - 14, py + 124], radius=6, fill=(11, 15, 23), outline=ACCENT_EMERALD)
    draw.text((kx + 12, py + 99), "7K9X-2M4P", font=get_font(15, bold=True, mono=True), fill=ACCENT_EMERALD)

    draw.text((kx, py + 134), "• 2 Documents Bundled", font=font_body, fill=TEXT_SECONDARY)
    draw.text((kx, py + 152), "• View-Only (No DL)", font=font_body, fill=TEXT_SECONDARY)
    draw.text((kx, py + 170), "• Single Recipient Auth", font=font_body, fill=TEXT_SECONDARY)

    # 1-Click Revoke button
    draw_rounded_rect(draw, [px + 14, py + 208, px + pw - 14, py + 246], radius=6, fill=RED_BG, outline=DANGER_RED)
    # Draw lightning bolt
    lb_cx = px + pw // 2 - 82
    lb_cy = py + 227
    draw.polygon(
        [
            (lb_cx + 2, lb_cy - 7),
            (lb_cx - 4, lb_cy),
            (lb_cx - 1, lb_cy),
            (lb_cx - 3, lb_cy + 7),
            (lb_cx + 4, lb_cy - 1),
            (lb_cx + 1, lb_cy - 1),
        ],
        fill=(254, 226, 226),
    )
    draw.text((lb_cx + 10, py + 218), "1-Click Instant Revoke", font=font_bold, fill=(254, 226, 226))

    # Second Active Pass (Summary Bar)
    py2 = py + 278
    draw_rounded_rect(draw, [px, py2, px + pw, py2 + 75], radius=8, fill=BG_CARD, outline=BORDER_HAIRLINE)
    draw.text((px + 14, py2 + 12), "Employer KYC Background Check", font=font_bold, fill=TEXT_PRIMARY)
    draw.text((px + 14, py2 + 34), "TTL: 1h 45m  •  1 File  •  Key: 9A3F-...", font=font_mono, fill=TEXT_DIM)
    draw_rounded_rect(draw, [px + pw - 75, py2 + 14, px + pw - 14, py2 + 42], radius=4, fill=RED_BG, outline=DANGER_RED)
    draw.text((px + pw - 63, py2 + 20), "Revoke", font=font_badge, fill=(254, 226, 226))

    # Save Image
    out_path = Path(__file__).resolve().parent.parent / ".github" / "assets" / "passli-dashboard-preview.png"
    img.save(out_path, format="PNG", optimize=True)
    print(f"Generated pristine dashboard preview at {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    generate_dashboard()
