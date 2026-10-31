"""
Passli — Professional Open-Source README Banner Generator
=========================================================
Produces a world-class, human-crafted repository identity banner at exactly 1376×768 PNG.

Design Philosophy (Anti-AI-Slop, High-Craft Engineering)
-------------------------------------------------------
- Built with Passli's authentic visual identity and official brand tokens:
    * Obsidian Void: #080C14
    * Deep Slate: #0E1526
    * Emerald Accent: #10B981
    * Cyan Accent: #06B6D4
    * Violet Accent: #8B5CF6
- Incorporates the official Passli vector-rendered cyber-shield mark (`passli-app-icon.png`)
- Clean typographic hierarchy with geometric alignment
- Hairline-bordered glassmorphic feature badges with dual-tone dot indicators
- Subtle technical telemetry (crosshairs, coordinate labels, status bar)
- 2x supersampled anti-aliased rendering (2752×1536 -> 1376×768 Lanczos)
- 100% deterministic, zero network/server dependency, pure Pillow
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Brand Color Tokens
# ---------------------------------------------------------------------------
BG_OBSIDIAN = (8, 12, 20)          # #080C14 Base background
BG_PANEL = (14, 21, 38)            # #0E1526 Inner frame background
BG_CHIP = (17, 24, 39)             # #111827 Chip fill
BORDER_MUTED = (30, 41, 59)        # #1E293B Subtle hairline border
BORDER_HIGHLIGHT = (51, 65, 85)    # #334155 Frame highlight border

COLOR_EMERALD = (16, 185, 129)     # #10B981 Brand Primary
COLOR_CYAN = (6, 182, 212)         # #06B6D4 Brand Secondary
COLOR_VIOLET = (139, 92, 246)      # #8B5CF6 Crypto / AAD
COLOR_AMBER = (245, 158, 11)       # #F59E0B Ephemeral timer
COLOR_TEXT_WHITE = (248, 250, 252) # #F8FAFC Heading White
COLOR_TEXT_MUTED = (148, 163, 184) # #94A3B8 Secondary Text
COLOR_TEXT_DIM = (100, 116, 139)   # #64748B Dim labels

# Output dimensions enforced by test_repo_visual_identity
OUT_W, OUT_H = 1376, 768
SCALE = 2
CANVAS_W, CANVAS_H = OUT_W * SCALE, OUT_H * SCALE

ASSETS_DIR = Path(".github/assets")
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
BRAND_ICON_PATH = Path("static/img/brand/passli-app-icon.png")


# ---------------------------------------------------------------------------
# Font Discovery
# ---------------------------------------------------------------------------
def _pick_font(candidates: list[str]) -> str | None:
    for c in candidates:
        if Path(c).exists():
            return c
    return None


FONT_BOLD = _pick_font([
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
])
FONT_SEMIBOLD = _pick_font([
    "C:/Windows/Fonts/seguisb.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
])
FONT_REGULAR = _pick_font([
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/calibri.ttf",
])
FONT_MONO = _pick_font([
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/cascadiacode.ttf",
    "C:/Windows/Fonts/cour.ttf",
])


def get_font(path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if path and Path(path).exists():
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Drawing Utilities
# ---------------------------------------------------------------------------
def draw_radial_ambient_glow(canvas: Image.Image, cx: int, cy: int, max_radius: int) -> None:
    """Renders a soft, diffuse ambient glow centered behind the main brand mark."""
    glow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow_layer)

    steps = 45
    for i in range(steps, 0, -1):
        ratio = i / steps
        r = int(max_radius * ratio)
        alpha = int(22 * (1.0 - math.pow(ratio, 0.7)))
        if ratio < 0.4:
            color = (6, 182, 212, alpha)
        elif ratio < 0.7:
            color = (99, 102, 241, alpha)
        else:
            color = (16, 185, 129, alpha)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    canvas.alpha_composite(glow_layer)


def draw_cyber_grid(draw: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int, step: int = 48) -> None:
    """Subtle matrix grid with micro-dots at intersections."""
    grid_color = (18, 26, 44)
    dot_color = (30, 42, 68)

    for x in range(x0, x1, step):
        draw.line([x, y0, x, y1], fill=grid_color, width=1)
    for y in range(y0, y1, step):
        draw.line([x0, y, x1, y], fill=grid_color, width=1)

    for x in range(x0, x1, step):
        for y in range(y0, y1, step):
            draw.rectangle([x - 1, y - 1, x + 1, y + 1], fill=dot_color)


def draw_tech_crosshair(draw: ImageDraw.ImageDraw, cx: int, cy: int, arm: int = 12, color=BORDER_HIGHLIGHT) -> None:
    """Draws a refined + crosshair marker."""
    draw.line([cx - arm, cy, cx + arm, cy], fill=color, width=2)
    draw.line([cx, cy - arm, cx, cy + arm], fill=color, width=2)


def draw_pill_badge(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    accent_color: tuple[int, int, int],
) -> int:
    """Draws a modern, pill-shaped badge with a glowing active dot and hairline border."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    dot_radius = 4 * SCALE
    dot_gap = 10 * SCALE
    pad_x = 18 * SCALE
    pad_y = 9 * SCALE

    pill_w = pad_x * 2 + dot_radius * 2 + dot_gap + text_w
    pill_h = text_h + pad_y * 2
    x0 = cx - pill_w // 2
    y0 = cy - pill_h // 2
    x1 = x0 + pill_w
    y1 = y0 + pill_h

    draw.rounded_rectangle([x0, y0, x1, y1], radius=pill_h // 2, fill=BG_CHIP, outline=BORDER_MUTED, width=SCALE)

    dot_cx = x0 + pad_x + dot_radius
    dot_cy = cy
    draw.ellipse(
        [dot_cx - dot_radius - 2, dot_cy - dot_radius - 2, dot_cx + dot_radius + 2, dot_cy + dot_radius + 2],
        fill=None,
        outline=(*accent_color, 90),
        width=1,
    )
    draw.ellipse(
        [dot_cx - dot_radius, dot_cy - dot_radius, dot_cx + dot_radius, dot_cy + dot_radius],
        fill=accent_color,
    )

    text_x = dot_cx + dot_radius + dot_gap
    text_y = cy - text_h // 2 - 1
    draw.text((text_x, text_y), text, font=font, fill=COLOR_TEXT_WHITE)

    return pill_w


# ---------------------------------------------------------------------------
# Main Banner Generation
# ---------------------------------------------------------------------------
def generate_identity_banner() -> Path:
    print(f"Generating professional open-source banner ({CANVAS_W}x{CANVAS_H} supersampled -> {OUT_W}x{OUT_H})...")

    banner_rgba = Image.new("RGBA", (CANVAS_W, CANVAS_H), (*BG_OBSIDIAN, 255))
    draw = ImageDraw.Draw(banner_rgba)

    f_kicker = get_font(FONT_MONO, 13 * SCALE)
    f_title = get_font(FONT_BOLD, 74 * SCALE)
    f_tagline = get_font(FONT_SEMIBOLD, 22 * SCALE)
    f_subtext = get_font(FONT_REGULAR, 15 * SCALE)
    f_badge = get_font(FONT_MONO, 12 * SCALE)
    f_telemetry = get_font(FONT_MONO, 11 * SCALE)

    pad_outer_x = 44 * SCALE
    pad_outer_y = 36 * SCALE
    frame_x0 = pad_outer_x
    frame_y0 = pad_outer_y
    frame_x1 = CANVAS_W - pad_outer_x
    frame_y1 = CANVAS_H - pad_outer_y
    frame_radius = 20 * SCALE

    # 1. Subtle Cyber Matrix Grid within the main frame
    draw_cyber_grid(draw, frame_x0 + 16, frame_y0 + 16, frame_x1 - 16, frame_y1 - 16, step=44 * SCALE)

    # 2. Main Framed Card
    draw.rounded_rectangle(
        [frame_x0, frame_y0, frame_x1, frame_y1],
        radius=frame_radius,
        fill=(*BG_PANEL, 210),
        outline=BORDER_MUTED,
        width=SCALE,
    )

    # Top highlight border accent
    draw.line(
        [frame_x0 + frame_radius, frame_y0, frame_x1 - frame_radius, frame_y0],
        fill=BORDER_HIGHLIGHT,
        width=SCALE,
    )

    # 3. Technical Corner Crosshairs
    crosshair_margin = 18 * SCALE
    draw_tech_crosshair(draw, frame_x0 + crosshair_margin, frame_y0 + crosshair_margin, arm=7 * SCALE)
    draw_tech_crosshair(draw, frame_x1 - crosshair_margin, frame_y0 + crosshair_margin, arm=7 * SCALE)
    draw_tech_crosshair(draw, frame_x0 + crosshair_margin, frame_y1 - crosshair_margin, arm=7 * SCALE)
    draw_tech_crosshair(draw, frame_x1 - crosshair_margin, frame_y1 - crosshair_margin, arm=7 * SCALE)

    # 4. Top Telemetry Kicker Bar
    kicker_y = frame_y0 + 38 * SCALE
    kicker_text = "PASSLI SECURITY PROTOCOL // OPEN-SOURCE DOCUMENT VAULT & EPHEMERAL SHARING"
    kicker_bbox = draw.textbbox((0, 0), kicker_text, font=f_kicker)
    kicker_w = kicker_bbox[2] - kicker_bbox[0]
    draw.text((CANVAS_W // 2 - kicker_w // 2, kicker_y), kicker_text, font=f_kicker, fill=COLOR_CYAN)

    draw.line(
        [CANVAS_W // 2 - 320 * SCALE, kicker_y + 22 * SCALE, CANVAS_W // 2 + 320 * SCALE, kicker_y + 22 * SCALE],
        fill=BORDER_MUTED,
        width=1,
    )

    # 5. Ambient Glow behind the Official Brand Mark
    icon_center_x = CANVAS_W // 2
    icon_center_y = int(frame_y0 + 175 * SCALE)
    draw_radial_ambient_glow(banner_rgba, icon_center_x, icon_center_y, max_radius=190 * SCALE)
    draw = ImageDraw.Draw(banner_rgba)

    # 6. Official Passli Cyber-Shield App Icon
    if BRAND_ICON_PATH.exists():
        raw_icon = Image.open(BRAND_ICON_PATH).convert("RGBA")
        target_icon_size = 196 * SCALE
        icon_resized = raw_icon.resize((target_icon_size, target_icon_size), Image.Resampling.LANCZOS)
        icon_paste_x = icon_center_x - target_icon_size // 2
        icon_paste_y = icon_center_y - target_icon_size // 2
        banner_rgba.alpha_composite(icon_resized, (icon_paste_x, icon_paste_y))
        draw = ImageDraw.Draw(banner_rgba)

    # 7. Wordmark "Passli"
    title_text = "Passli"
    title_bbox = draw.textbbox((0, 0), title_text, font=f_title)
    title_w = title_bbox[2] - title_bbox[0]
    title_h = title_bbox[3] - title_bbox[1]
    title_y = int(icon_center_y + 115 * SCALE)
    title_x = CANVAS_W // 2 - title_w // 2
    draw.text((title_x, title_y), title_text, font=f_title, fill=COLOR_TEXT_WHITE)

    # 8. Primary Tagline
    tagline_text = "Cryptographic Document Vault  *  Ephemeral Sharing Platform"
    tagline_bbox = draw.textbbox((0, 0), tagline_text, font=f_tagline)
    tagline_w = tagline_bbox[2] - tagline_bbox[0]
    tagline_y = title_y + title_h + 16 * SCALE
    draw.text((CANVAS_W // 2 - tagline_w // 2, tagline_y), tagline_text, font=f_tagline, fill=COLOR_EMERALD)

    # 9. Descriptive Mission Pitch
    subtext = "Zero-knowledge recipient sharing, AES-256-GCM encryption at rest & time-gated ephemeral passes"
    subtext_bbox = draw.textbbox((0, 0), subtext, font=f_subtext)
    subtext_w = subtext_bbox[2] - subtext_bbox[0]
    subtext_y = tagline_y + 36 * SCALE
    draw.text((CANVAS_W // 2 - subtext_w // 2, subtext_y), subtext, font=f_subtext, fill=COLOR_TEXT_MUTED)

    # 10. Feature Badges Row (4 Glassmorphic Hairline Chips)
    badges = [
        ("AES-256-GCM AEAD", COLOR_EMERALD),
        ("PBKDF2-HMAC-SHA256", COLOR_CYAN),
        ("Zero Disk Decryption", COLOR_VIOLET),
        ("Time-Gated QR Passes", COLOR_AMBER),
    ]

    badge_y = subtext_y + 54 * SCALE
    gap = 14 * SCALE

    badge_widths = []
    for text, _ in badges:
        bb = draw.textbbox((0, 0), text, font=f_badge)
        tw = bb[2] - bb[0]
        pill_w = (18 * SCALE) * 2 + (4 * SCALE) * 2 + (10 * SCALE) + tw
        badge_widths.append(pill_w)

    total_badges_w = sum(badge_widths) + gap * (len(badges) - 1)
    cur_x = CANVAS_W // 2 - total_badges_w // 2

    for (text, accent), w in zip(badges, badge_widths):
        badge_cx = cur_x + w // 2
        draw_pill_badge(draw, badge_cx, badge_y, text, f_badge, accent)
        cur_x += w + gap

    # 11. Bottom Architectural Status Bar
    bar_y = frame_y1 - 38 * SCALE
    draw.line(
        [frame_x0 + 24 * SCALE, bar_y - 12 * SCALE, frame_x1 - 24 * SCALE, bar_y - 12 * SCALE],
        fill=BORDER_MUTED,
        width=1,
    )

    left_meta = "STATUS: PRODUCTION READY // REPO: GITHUB.COM/ALINAWAZCODE/PASSLI"
    draw.text((frame_x0 + 28 * SCALE, bar_y), left_meta, font=f_telemetry, fill=COLOR_TEXT_DIM)

    right_meta = "PYTHON 3.12 * DJANGO 5.1 * ZERO PERSISTED PLAINTEXT * MIT LICENSE"
    rm_bbox = draw.textbbox((0, 0), right_meta, font=f_telemetry)
    rm_w = rm_bbox[2] - rm_bbox[0]
    draw.text((frame_x1 - 28 * SCALE - rm_w, bar_y), right_meta, font=f_telemetry, fill=COLOR_TEXT_DIM)

    # ---------------------------------------------------------------------------
    # Downsample via Lanczos to target 1376x768
    # ---------------------------------------------------------------------------
    final_rgb = banner_rgba.convert("RGB")
    final_output = final_rgb.resize((OUT_W, OUT_H), Image.Resampling.LANCZOS)

    out_file = ASSETS_DIR / "passli-repo-banner.png"
    final_output.save(str(out_file), "PNG", optimize=True)
    file_size_kb = out_file.stat().st_size / 1024
    print(f"SUCCESS: Saved {out_file} ({OUT_W}x{OUT_H}, {file_size_kb:.1f} KB)")
    return out_file


if __name__ == "__main__":
    generate_identity_banner()
