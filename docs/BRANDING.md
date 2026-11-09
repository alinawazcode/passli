# Passli Visual Identity & Brand Design System

This guide establishes the visual identity, brand guidelines, color tokens, and asset specifications for the **Passli** open-source repository and application suite.

---

## 🛡️ Brand Philosophy & Design System

Passli adheres strictly to **human-crafted, anti-AI-slop design principles** (referencing `LeoStehlik/no-slop-ui` and `unslop-ui v2` standards) and the **Hallmark** precision design system:
- **Zero AI Clichés**: No generic cybernetic hands, glowing purple/magenta radial traps, artificial clip-art, or floating cartoon locks. Real protocol UI and actual cryptographic mechanisms provide the visual substance.
- **Precision Dark Obsidian Palette**: Standardized across the entire application suite (`#0B0F17`, `#0F172A`, `#111827`, `#131B2A`) with high-contrast text (`#F8FAFC`, `#94A3B8`) and surgical emerald (`#10B981`) and cyan (`#38BDF8`) accents.
- **Hairline Borders & Surface Hierarchy**: Refined 1px translucent borders (`rgba(255, 255, 255, 0.08)`) and multi-layered surface elevation cards without muddy gradients.
- **Accessible WCAG AA Contrast**: Body copy contrast exceeds 18:1 against canvas; interactive emerald controls exceed 8.2:1 against surface containers, ensuring high legibility in healthcare and enterprise settings.
- **Authentic Engineering Artifacts**: Accurate wire formats, cryptographic flows, and real product UI elements.

---

## 🎨 Color Palette & Design Tokens

| Token Name | Hex Code | HSL / RGBA | Role / Usage |
| :--- | :---: | :---: | :--- |
| **`--bg-canvas`** | `#0B0F17` | `hsl(220, 35%, 7%)` | Primary dark background / page canvas |
| **`--bg-surface`** | `#111827` | `hsl(222, 47%, 11%)` | Surface cards, dialogs, and panels |
| **`--bg-card`** | `#131B2A` | `hsl(217, 37%, 12%)` | Secondary elevated containers and table rows |
| **`--bg-surface-elevated`**| `#1E293B` | `hsl(217, 33%, 17%)` | Hover states, popovers, active items |
| **`--border-hairline`** | `#1F2937` | `rgba(255, 255, 255, 0.08)` | 1px clean card and component hairline borders |
| **`--border-medium`** | `#374151` | `rgba(255, 255, 255, 0.16)` | Inputs, active outlines, divider lines |
| **`--accent-emerald`** | `#10B981` | `hsl(160, 84%, 39%)` | Primary brand accent, verified status, active states |
| **`--accent-cyan`** | `#06B6D4` | `hsl(189, 94%, 43%)` | Secondary accent, interactive badges, active QR scanner |
| **`--danger-red`** | `#EF4444` | `hsl(0, 84%, 60%)` | 1-Click Revocation, session destruction, lockouts |
| **`--warning-amber`** | `#F59E0B` | `hsl(38, 92%, 50%)` | Security alerts, OTP expiration warnings |
| **`--text-primary`** | `#F8FAFC` | `hsl(210, 40%, 98%)` | High-contrast headers and primary text |
| **`--text-secondary`**| `#94A3B8` | `hsl(215, 20%, 65%)` | Subtitles, helper text, and metadata |
| **`--text-muted`** | `#64748B` | `hsl(215, 16%, 47%)` | Captions, timestamps, disabled indicators |

---

## 🔤 Typography & Font System

Passli implements a dual-typeface typographic system:
1. **Primary Interface (`Geist`)**: Used for headings, navigation, form labels, and UI controls. Clean, neutral grotesque letterforms optimized for dense data tables.
2. **Cryptographic & Data (`JetBrains Mono`)**: Used for Share Keys, SHA-256 digests, IP addresses, TTL countdown timers, and pass IDs. Tabular numbers (`font-variant-numeric: tabular-nums`) eliminate layout jitter during count-downs.

---

## 🗂️ Brand Assets & File Hierarchy

### 1. Vector Logos & Marks (`static/img/brand/`)
- [`passli-logo.svg`](../static/img/brand/passli-logo.svg): Primary horizontal logotype for dark backgrounds.
- [`passli-logo-light.svg`](../static/img/brand/passli-logo-light.svg): High-contrast logotype variant for light backgrounds.
- [`passli-mark.svg`](../static/img/brand/passli-mark.svg): Standalone geometric shield & vault keyhole brand mark.
- [`passli-app-icon.png`](../static/img/brand/passli-app-icon.png): 512 × 512 high-resolution raster app icon for mobile homescreens and PWA.

### 2. Repository Visual Identity Assets (`.github/assets/`)
- [`passli-repo-banner.png`](../.github/assets/passli-repo-banner.png): 1376 × 768 (16:9) Repository Hero Banner.
- [`passli-ephemeral-workflow.gif`](../.github/assets/passli-ephemeral-workflow.gif): 1100 × 580 (58-frame animated demonstration of the Share Pass protocol).
- [`passli-dashboard-preview.png`](../.github/assets/passli-dashboard-preview.png): 1376 × 768 (16:9) Personal Vault Dashboard UI Preview framed in modern browser window.
- [`passli-vault-documents.png`](../.github/assets/passli-vault-documents.png): 1376 × 768 (16:9) Encrypted Document Vault browser with filter pills and SHA-256 cards.
- [`passli-cryptographic-pipeline.png`](../.github/assets/passli-cryptographic-pipeline.png): 1376 × 768 (16:9) Systems architecture diagram of AES-256-GCM AEAD storage and streaming.

---

## 📐 Asset Generation Tooling

Passli includes deterministic Python automation to regenerate visual identity assets and animated workflow demonstrations:

```powershell
# Regenerate 58-frame animated ephemeral workflow demonstration GIF
python scripts/generate_ephemeral_flow_gif.py

# Regenerate pixel-perfect vault dashboard UI preview
python scripts/generate_dashboard_preview.py
```

All static diagrams and banners are engineered in 16:9 widescreen format, optimized under 1 MB to guarantee rapid CDN delivery across GitHub without proxy timeouts.
