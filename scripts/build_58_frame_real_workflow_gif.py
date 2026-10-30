import os
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = r".github\assets"
out_gif = os.path.join(ASSETS_DIR, "passli-ephemeral-workflow.gif")

# Let's inspect test_card if it exists or use high-res real elements
card_path = os.path.join(ASSETS_DIR, "passli-share-simulator.png")

# Target GIF specs
WIDTH = 1100
HEIGHT = 580
BG_COLOR = (248, 250, 252)  # Clean slate canvas

# Load fonts
try:
    font_bold = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 15)
    font_reg = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 14)
    font_mono = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 14)
    font_mono_lg = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 26)
    font_sm = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 12)
    font_badge = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 11)
except Exception:
    font_bold = font_reg = font_mono = font_mono_lg = font_sm = font_badge = ImageFont.load_default()

frames = []


# Base card rendering matching actual site CSS exactly
def render_base_card(draw, x=25, y=15, w=1050, h=550):
    # Main container
    draw.rounded_rectangle([x, y, x + w, y + h], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    # Split vertical divider
    div_x = x + 560
    draw.line([div_x, y, div_x, y + h], fill=(241, 245, 249), width=1)
    return x, y, div_x


tokens = ["8K7P-42XM", "4T9M-7N2K", "9J3Q-5V8B"]

for f_idx in range(58):
    im = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(im)

    cx, cy, div_x = render_base_card(draw)

    # Left Header
    draw.text((cx + 30, cy + 25), "Create Controlled Share Pass", font=font_bold, fill=(15, 23, 42))
    draw.text((cx + 30, cy + 48), "Define access rules and file boundary", font=font_sm, fill=(100, 116, 139))

    # Token Ready badge
    draw.rounded_rectangle(
        [cx + 430, cy + 25, cx + 520, cy + 50], radius=12, fill=(236, 253, 245), outline=(16, 185, 129)
    )
    draw.ellipse([cx + 440, cy + 35, cx + 446, cy + 41], fill=(16, 185, 129))
    draw.text((cx + 452, cy + 30), "Token Ready", font=font_badge, fill=(5, 150, 105))

    # Selection header
    doc3_checked = f_idx >= 10 and f_idx < 46
    doc2_checked = f_idx < 18 or f_idx >= 46
    sel_count = 1 if not doc2_checked and not doc3_checked else (3 if doc2_checked and doc3_checked else 2)
    sel_mb = "7.3 MB" if sel_count == 3 else ("3.5 MB" if doc2_checked else "6.2 MB")

    draw.text((cx + 30, cy + 85), "SELECT VAULT RECORDS", font=font_badge, fill=(100, 116, 139))
    count_txt = f"{sel_count} selected ({sel_mb})"
    cw = int(draw.textlength(count_txt, font=font_badge)) + 16
    draw.rounded_rectangle([cx + 520 - cw, cy + 82, cx + 520, cy + 102], radius=4, fill=(241, 245, 249))
    draw.text((cx + 528 - cw, cy + 86), count_txt, font=font_badge, fill=(71, 85, 105))

    # Documents rows
    doc_y = cy + 115
    docs = [
        ("Blood_Test_Panel_2026.pdf", "2.4 MB • Encrypted Medical", "sha256:4a8e...91b0", True),
        ("National_ID_Card.png", "1.1 MB • Verified KYC", "sha256:7c22...88aa", doc2_checked),
        ("Vehicle_Registration_Cert.pdf", "3.8 MB • Notarized Legal", "sha256:d130...ef49", doc3_checked),
    ]
    for d_name, d_meta, d_hash, checked in docs:
        row_border = (11, 28, 48) if checked else (226, 232, 240)
        draw.rounded_rectangle(
            [cx + 30, doc_y, cx + 520, doc_y + 50], radius=8, fill=(255, 255, 255), outline=row_border, width=1
        )
        # Checkbox
        cb_fill = (11, 28, 48) if checked else (255, 255, 255)
        draw.rounded_rectangle(
            [cx + 44, doc_y + 16, cx + 62, doc_y + 34], radius=3, fill=cb_fill, outline=(11, 28, 48), width=1
        )
        if checked:
            draw.text((cx + 48, cy if False else doc_y + 16), "✓", font=font_badge, fill=(255, 255, 255))
        # Doc text
        draw.text((cx + 75, doc_y + 9), d_name, font=font_bold, fill=(15, 23, 42))
        draw.text(
            (cx + 75, doc_y + 28),
            d_meta,
            font=font_sm,
            fill=(5, 150, 105) if "Medical" in d_meta or "KYC" in d_meta else (100, 116, 139),
        )
        draw.text((cx + 380, doc_y + 18), d_hash, font=font_mono, fill=(148, 163, 184))
        doc_y += 58

    # Expiration Timer pills
    draw.text((cx + 30, doc_y + 5), "CRYPTOGRAPHIC EXPIRATION TIMER", font=font_badge, fill=(100, 116, 139))
    ttls = ["15 mins", "30 mins", "2 hours", "24 hours", "1-time"]
    active_idx = 0 if (f_idx >= 18 and f_idx < 34) else (3 if f_idx >= 34 else 1)
    tx = cx + 30
    for idx, t in enumerate(ttls):
        is_act = idx == active_idx
        bg = (11, 28, 48) if is_act else (255, 255, 255)
        fg = (255, 255, 255) if is_act else (71, 85, 105)
        draw.rounded_rectangle(
            [tx, doc_y + 25, tx + 88, doc_y + 55], radius=6, fill=bg, outline=(226, 232, 240) if not is_act else None
        )
        tw = int(draw.textlength(t, font=font_badge))
        draw.text((tx + (88 - tw) // 2, doc_y + 33), t, font=font_badge, fill=fg)
        tx += 96

    # Action Button
    is_gen_click = f_idx in range(26, 32) or f_idx in range(40, 46)
    btn_bg = (5, 150, 105) if is_gen_click else (11, 28, 48)
    draw.rounded_rectangle([cx + 30, doc_y + 75, cx + 260, doc_y + 115], radius=6, fill=btn_bg)
    draw.text((cx + 50, doc_y + 87), "Generate Pass & Encrypt Link", font=font_bold, fill=(255, 255, 255))

    # Revoke link
    is_revoked = f_idx >= 50
    rev_color = (225, 29, 72) if not is_revoked else (156, 163, 175)
    draw.text((cx + 460, doc_y + 88), "Revoke" if not is_revoked else "Revoked", font=font_badge, fill=rev_color)

    # RIGHT COLUMN: Pass Output Artifact
    rx = div_x + 30
    draw.text((rx, cy + 25), "PASS OUTPUT ARTIFACT", font=font_badge, fill=(100, 116, 139))
    draw.rounded_rectangle(
        [cx + 920, cy + 22, cx + 1015, cy + 42], radius=4, fill=(236, 253, 245), outline=(16, 185, 129)
    )
    draw.text((cx + 928, cy + 26), "LIVE ENCRYPTION", font=font_badge, fill=(5, 150, 105))

    # Authentic QR Code Box
    draw.rounded_rectangle([rx, cy + 52, rx + 425, cy + 250], radius=8, fill=(255, 255, 255), outline=(226, 232, 240))
    # Draw central QR pattern
    qrx = rx + 145
    qry = cy + 65
    draw.rectangle([qrx, qry, qrx + 135, qry + 135], fill=(255, 255, 255))

    # Outer markers
    def qr_box(bx, by):
        draw.rectangle([bx, by, bx + 32, by + 32], fill=(11, 28, 48))
        draw.rectangle([bx + 5, by + 5, bx + 27, by + 27], fill=(255, 255, 255))
        draw.rectangle([bx + 10, by + 10, bx + 22, by + 22], fill=(11, 28, 48))

    qr_box(qrx + 5, qry + 5)
    qr_box(qrx + 98, qry + 5)
    qr_box(qrx + 5, qry + 98)

    # Pattern dots
    import random

    rng = random.Random(42 + (f_idx // 15))
    for px in range(qrx + 10, qrx + 125, 8):
        for py in range(qry + 10, qry + 125, 8):
            if (
                (px < qrx + 45 and py < qry + 45)
                or (px > qrx + 90 and py < qry + 45)
                or (px < qrx + 45 and py > qry + 90)
            ):
                continue
            if rng.random() > 0.48:
                draw.rectangle([px, py, px + 5, py + 5], fill=(11, 28, 48))

    draw.text((rx + 140, cy + 210), "Scan with mobile or reader", font=font_bold, fill=(15, 23, 42))
    draw.text((rx + 135, cy + 228), "Zero payload stored without pass key", font=font_sm, fill=(100, 116, 139))

    # Required Access Key Box
    draw.rounded_rectangle([rx, cy + 265, rx + 425, cy + 385], radius=8, fill=(255, 255, 255), outline=(226, 232, 240))
    draw.text((rx + 15, cy + 275), "REQUIRED ACCESS KEY", font=font_badge, fill=(100, 116, 139))
    draw.text((rx + 370, cy + 275), "📋 Copy", font=font_badge, fill=(5, 150, 105))

    # Key Value Box
    token_val = tokens[0] if f_idx < 26 else (tokens[1] if f_idx < 42 else tokens[2])
    draw.rounded_rectangle(
        [rx + 15, cy + 298, rx + 410, cy + 350], radius=6, fill=(248, 250, 252), outline=(226, 232, 240)
    )
    tw = int(draw.textlength(token_val, font=font_mono_lg))
    draw.text((rx + 15 + (395 - tw) // 2, cy + 308), token_val, font=font_mono_lg, fill=(15, 23, 42))

    # Fingerprint
    draw.text((rx + 15, cy + 360), f"Fingerprint: sha256: 9f8a...{f_idx:02d}b1", font=font_mono, fill=(148, 163, 184))

    # Pass validity progress bar
    draw.rounded_rectangle([rx, cy + 400, rx + 425, cy + 480], radius=8, fill=(255, 255, 255), outline=(226, 232, 240))
    val_txt = "15 mins" if active_idx == 0 else ("24 hours" if active_idx == 3 else "30 mins")
    draw.text((rx + 15, cy + 412), f"⏱ Pass validity: {val_txt}", font=font_badge, fill=(15, 23, 42))
    draw.text((rx + 300, cy + 412), "Server Enforced", font=font_badge, fill=(100, 116, 139))

    # Progress bar fill
    prog_pct = max(0.1, 1.0 - (f_idx % 20) / 20.0) if not is_revoked else 0.0
    draw.rounded_rectangle([rx + 15, cy + 438, rx + 410, cy + 446], radius=4, fill=(226, 232, 240))
    if prog_pct > 0:
        draw.rounded_rectangle(
            [rx + 15, cy + 438, rx + 15 + int(395 * prog_pct), cy + 446], radius=4, fill=(16, 185, 129)
        )
    else:
        draw.rounded_rectangle([rx + 15, cy + 438, rx + 410, cy + 446], radius=4, fill=(239, 68, 68))
        draw.text((rx + 160, cy + 454), "SESSION TERMINATED", font=font_badge, fill=(239, 68, 68))

    frames.append(im)

frames[0].save(out_gif, save_all=True, append_images=frames[1:], duration=160, loop=0)

print(f"Generated {out_gif}: {len(frames)} frames, {os.path.getsize(out_gif)} bytes")
