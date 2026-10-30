# Passli Visual Identity & Repository Assets

This directory contains the visual branding, architecture infographics, UI previews, and animated demonstration assets for the **Passli** open-source repository.

---

## 🎨 Asset Catalog

| Asset | File | Type | Resolution | Purpose |
| :--- | :--- | :---: | :---: | :--- |
| **Hero Banner** | [`passli-repo-banner.png`](passli-repo-banner.png) | Static Image (PNG) | 1376 × 768 (16:9) | Primary README header banner, social card, and project cover |
| **Ephemeral Flow Demo** | [`passli-ephemeral-workflow.gif`](passli-ephemeral-workflow.gif) | Animated GIF | 1100 × 580 (58 frames) | Interactive demonstration of pass creation, 8-char key hashing, QR protocol, live countdown, and 1-click revocation |
| **Vault Dashboard Preview** | [`passli-dashboard-preview.png`](passli-dashboard-preview.png) | Static Image (PNG) | 1376 × 768 (16:9) | High-fidelity UI mockup of the authenticated personal vault dashboard, telemetry, and document cards |
| **Cryptographic Pipeline** | [`passli-cryptographic-pipeline.png`](passli-cryptographic-pipeline.png) | Static Image (PNG) | 1376 × 768 (16:9) | Architecture diagram depicting AES-256-GCM AEAD ingestion and in-memory streaming decryption |

---

## 🛠️ Regeneration & Build Tools

The animated workflow demonstration (`passli-ephemeral-workflow.gif`) and dashboard UI preview (`passli-dashboard-preview.png`) are deterministically generated via Python Pillow tooling:

```bash
# Regenerate 58-frame animated ephemeral workflow demonstration GIF
python scripts/generate_ephemeral_flow_gif.py

# Regenerate pixel-perfect vault dashboard UI preview
python scripts/generate_dashboard_preview.py
```

### Design Standards & Palette
Assets adhere strictly to Passli's **anti-ai-slop** and **unslop-ui v2** engineering standards:
- **Background**: `#0B0F17` (Deep Obsidian) / `#111827` (Dark Slate)
- **Primary Accent**: `#10B981` (Emerald Green)
- **Secondary Accent**: `#06B6D4` (Electric Cyan)
- **Danger / Revoke**: `#EF4444` (Ruby Red)
- **Text Hierarchy**: `#F8FAFC` (Heading White), `#94A3B8` (Muted Slate), `#64748B` (Dim Slate)
- **Typography**: Clean humanist sans-serif and monospace technical displays
