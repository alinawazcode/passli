"""
Passli — Professional README Banner Generator
===============================================
Produces a crisp, open-source-grade identity banner at exactly 1376×768 PNG.

Design philosophy
-----------------
- Dark, precision palette (Deep Obsidian #0B0F17 base)
- Centered geometric shield mark — drawn with pure Pillow polygons, no raster art
- Clean typographic hierarchy: wordmark → tagline → feature chips
- Hairline-border chips, no neon glow traps, no AI slop
- Anti-aliasing via 2× supersample → downscale

Standalone: no Django server, no Selenium required.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Brand tokens
# ---------------------------------------------------------------------------
BG_DEEP = (11, 15, 23)          # #0B0F17  Deep Obsidian
BG_CARD = (17, 24, 39)          # #111827  Dark Slate
ACCENT_GREEN = (16, 185, 129)   # #10B981  Emerald
ACCENT_CYAN = (6, 182, 212)     # #06B6D4  Electric Cyan
ACCENT_PURPLE = (139, 92, 246)  # #8B5CF6  Violet
TEXT_HEAD = (248, 250, 252)     # #F8FAFC  Heading White
TEXT_MUTED = (148, 163, 184)    # #94A3B8  Muted Slate
BORDER = (30, 41, 59)           # Subtle separator

# Output dimensions (test requires exactly this)
OUT_W, OUT_H = 1376, 768

# Supersample scale (render at 2× then lanczos-down for anti-aliasing)
SS = 2
W, H = OUT_W * SS, OUT_H * SS

ASSETS_DIR = Path(".github/assets")
ASSETS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------
FONT_CANDIDATES_BOLD = [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
]
FONT_CANDIDATES_REGULAR = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/calibri.ttf",
]
FONT_CANDIDATES_LIGHT = [
    "C:/Windows/Fonts/segoeuil.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
FONT_CANDIDATES_MONO = [
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/cour.ttf",
    "C:/Windows/Fonts/lucon.ttf",
]


def _first_available(candidates: list[str]) -> str | None:
    for p in candidates:
        if Path(p).exists():
            return p
    return None


def load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = _first_available(candidates)
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def hex_points(cx: float, cy: float, r: float, rotation_deg: float = 0.0) -> list[tuple[float, float]]:
    """Return the 6 vertices of a regular hexagon."""
    pts = []
    for i in range(6):
        angle = math.radians(rotation_deg + 60 * i - 90)
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return pts


def shield_points(cx: float, cy: float, w: float, h: float) -> list[tuple[float, float]]:
    """Heraldic shield outline — flat top, pointed bottom, gentle inward curves at waist."""
    hw = w / 2
    # Key control points (approximated with polygon vertices for Pillow)
    top_left = (cx - hw, cy)
    top_right = (cx + hw, cy)
    # Shoulder curve — step in gently
    sh_l = (cx - hw, cy + h * 0.40)
    sh_r = (cx + hw, cy + h * 0.40)
    # Waist narrows
    wa_l = (cx - hw * 0.75, cy + h * 0.58)
    wa_r = (cx + hw * 0.75, cy + h * 0.58)
    # Lower flanks
    fl_l = (cx - hw * 0.50, cy + h * 0.76)
    fl_r = (cx + hw * 0.50, cy + h * 0.76)
    # Tip
    tip = (cx, cy + h)
    return [top_left, top_right, sh_r, wa_r, fl_r, tip, fl_l, wa_l, sh_l, top_left]


def draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float, float, float],
    radius: float,
    fill=None,
    outline=None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


# ---------------------------------------------------------------------------
# Core drawing
# ---------------------------------------------------------------------------

def draw_subtle_grid(draw: ImageDraw.ImageDraw, step: int = 80) -> None:
    """Ultra-subtle dot-grid background texture."""
    dot_color = (18, 24, 36)
    for y in range(0, H, step):
        for x in range(0, W, step):
            draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=dot_color)


def draw_shield(draw: ImageDraw.ImageDraw, cx: float, cy: float, size: float) -> None:
    """
    Professional heraldic shield — primary brand mark.
    Composed of:
      - Outer shield silhouette in emerald with hairline stroke
      - Inner shield inset (depth effect)
      - Keyhole glyph centred inside
      - Thin decorative horizontal rule at shoulder
    """
    # ── Outer shield ──────────────────────────────────────────────────────
    sw, sh = size, size * 1.18
    pts_outer = shield_points(cx, cy, sw, sh)
    draw.polygon(pts_outer, fill=(14, 165, 117, 180), outline=ACCENT_GREEN, width=SS * 2)

    # ── Inner shield (inset) ───────────────────────────────────────────────
    inset = size * 0.10
    pts_inner = shield_points(cx, cy + inset * 0.3, sw - inset * 2, sh - inset * 2.2)
    draw.polygon(pts_inner, fill=None, outline=(16, 185, 129, 100), width=SS)

    # ── Decorative shoulder rule ───────────────────────────────────────────
    rule_y = cy + sh * 0.38
    rule_x0 = cx - sw * 0.52
    rule_x1 = cx + sw * 0.52
    draw.line([rule_x0, rule_y, rule_x1, rule_y], fill=(16, 185, 129, 120), width=SS)

    # ── Keyhole ───────────────────────────────────────────────────────────
    # Circle (upper disc of keyhole)
    kr = size * 0.13
    kcy = cy + sh * 0.38
    draw.ellipse(
        [cx - kr, kcy - kr, cx + kr, kcy + kr],
        fill=BG_DEEP,
        outline=ACCENT_GREEN,
        width=SS * 2,
    )
    # Rectangular stem (lower half)
    ks_w = kr * 0.65
    ks_h = size * 0.22
    draw.rounded_rectangle(
        [cx - ks_w, kcy, cx + ks_w, kcy + ks_h],
        radius=SS * 2,
        fill=BG_DEEP,
        outline=ACCENT_GREEN,
        width=SS * 2,
    )


def draw_wordmark(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    font_bold: ImageFont.FreeTypeFont,
) -> None:
    """'Passli' wordmark with the 'i' dot replaced by the accent green."""
    draw.text((x, y), "Passli", font=font_bold, fill=TEXT_HEAD)


def centered_text(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
) -> None:
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    draw.text((cx - tw / 2, cy - th / 2), text, font=font, fill=fill)


def draw_chip(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    text: str,
    font: ImageFont.FreeTypeFont,
    accent: tuple,
) -> float:
    """Draws a feature chip centred at (cx, cy). Returns chip width."""
    pad_x = SS * 16
    pad_y = SS * 7
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    chip_w = tw + pad_x * 2
    chip_h = th + pad_y * 2
    x0 = cx - chip_w / 2
    y0 = cy - chip_h / 2
    draw.rounded_rectangle(
        [x0, y0, x0 + chip_w, y0 + chip_h],
        radius=chip_h / 2,
        fill=BG_CARD,
        outline=accent,
        width=SS,
    )
    draw.text((x0 + pad_x, y0 + pad_y), text, font=font, fill=accent)
    return chip_w


def draw_divider_line(draw: ImageDraw.ImageDraw, y: float, width: float = 240) -> None:
    x0 = W / 2 - width
    x1 = W / 2 + width
    draw.line([x0, y, x1, y], fill=BORDER, width=SS)


def draw_bottom_bar(draw: ImageDraw.ImageDraw, font_small: ImageFont.FreeTypeFont) -> None:
    """Subtle bottom bar — domain + tagline."""
    bar_h = SS * 38
    y0 = H - bar_h
    draw.rectangle([0, y0, W, H], fill=(13, 18, 27))
    # Left: domain
    draw.text((SS * 32, y0 + SS * 10), "passli.dev", font=font_small, fill=ACCENT_GREEN)
    # Right: licence / stack
    right_text = "Django 5 · Python 3.12 · AES-256-GCM"
    bb = draw.textbbox((0, 0), right_text, font=font_small)
    rw = bb[2] - bb[0]
    draw.text((W - rw - SS * 32, y0 + SS * 10), right_text, font=font_small, fill=TEXT_MUTED)


# ---------------------------------------------------------------------------
# Accent geometry — corner fragments
# ---------------------------------------------------------------------------

def draw_corner_accents(draw: ImageDraw.ImageDraw) -> None:
    """Four hairline L-brackets in the corners for a technical feel."""
    arm = SS * 28
    t = SS * 2
    color = (30, 48, 64)
    margin = SS * 20
    corners = [
        # top-left
        [(margin, margin, margin + arm, margin + t), (margin, margin, margin + t, margin + arm)],
        # top-right
        [(W - margin - arm, margin, W - margin, margin + t), (W - margin - t, margin, W - margin, margin + arm)],
        # bottom-left
        [(margin, H - margin - t, margin + arm, H - margin), (margin, H - margin - arm, margin + t, H - margin)],
        # bottom-right
        [(W - margin - arm, H - margin - t, W - margin, H - margin), (W - margin - t, H - margin - arm, W - margin, H - margin)],
    ]
    for pair in corners:
        for rect in pair:
            draw.rectangle(rect, fill=color)


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render_banner() -> None:
    print(f"Rendering banner at {W}x{H} (2x supersample -> {OUT_W}x{OUT_H}) ...")

    img = Image.new("RGB", (W, H), BG_DEEP)
    draw = ImageDraw.Draw(img, "RGBA")

    # ── Background texture ────────────────────────────────────────────────
    draw_subtle_grid(draw, step=64)
    draw_corner_accents(draw)

    # Faint horizontal gradient strip behind shield (depth cue)
    for i in range(200):
        alpha = int(18 * (1 - i / 200))
        draw.line([0, H // 2 - 100 + i, W, H // 2 - 100 + i], fill=(*ACCENT_GREEN, alpha), width=1)

    # ── Load fonts ────────────────────────────────────────────────────────
    f_wordmark = load_font(FONT_CANDIDATES_BOLD, SS * 68)
    f_tagline = load_font(FONT_CANDIDATES_LIGHT, SS * 22)
    f_chip = load_font(FONT_CANDIDATES_MONO, SS * 16)
    f_small = load_font(FONT_CANDIDATES_REGULAR, SS * 17)

    # ── Shield mark ───────────────────────────────────────────────────────
    shield_cx = W / 2
    shield_cy = H * 0.34
    shield_size = SS * 92
    draw_shield(draw, shield_cx, shield_cy, shield_size)

    # ── Wordmark ──────────────────────────────────────────────────────────
    wm_y = H * 0.575
    centered_text(draw, W / 2, wm_y, "Passli", f_wordmark, TEXT_HEAD)

    # Green underline accent beneath wordmark
    bb = draw.textbbox((0, 0), "Passli", font=f_wordmark)
    wm_w = bb[2] - bb[0]
    ul_y = wm_y + (bb[3] - bb[1]) / 2 + SS * 6
    draw.line(
        [W / 2 - wm_w / 2, ul_y, W / 2 + wm_w / 2, ul_y],
        fill=ACCENT_GREEN,
        width=SS * 2,
    )

    # ── Tagline ───────────────────────────────────────────────────────────
    tagline = "Cryptographic Document Vault  ·  Ephemeral Sharing"
    centered_text(draw, W / 2, H * 0.685, tagline, f_tagline, TEXT_MUTED)

    # ── Feature chips ─────────────────────────────────────────────────────
    chips = [
        ("AES-256-GCM", ACCENT_GREEN),
        ("PBKDF2-SHA256", ACCENT_CYAN),
        ("Zero Disk Decrypt", ACCENT_PURPLE),
        ("Django 5", TEXT_MUTED),
    ]
    total_chip_w = 0
    gap = SS * 18
    chip_widths = []
    for text, _ in chips:
        bb = draw.textbbox((0, 0), text, font=f_chip)
        cw = (bb[2] - bb[0]) + SS * 32 + SS * 2  # rough
        chip_widths.append(cw)
        total_chip_w += cw + gap
    total_chip_w -= gap

    cx_cursor = W / 2 - total_chip_w / 2
    chip_y = H * 0.81
    for i, (text, accent) in enumerate(chips):
        draw_chip(draw, cx_cursor + chip_widths[i] / 2, chip_y, text, f_chip, accent)
        cx_cursor += chip_widths[i] + gap

    # ── Bottom bar ────────────────────────────────────────────────────────
    draw_bottom_bar(draw, f_small)

    # ── Downscale to output dimensions ────────────────────────────────────
    out_img = img.resize((OUT_W, OUT_H), Image.Resampling.LANCZOS)

    out_path = ASSETS_DIR / "passli-repo-banner.png"
    out_img.save(str(out_path), "PNG", optimize=True)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"Saved {out_path}  ({OUT_W}x{OUT_H}, {size_kb:.1f} KB)")


if __name__ == "__main__":
    render_banner()
