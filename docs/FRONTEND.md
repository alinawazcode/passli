# Passli Frontend Architecture & Motion Design System

This document outlines the frontend engineering standards, build tooling, motion tokens, and progressive enhancement guarantees for **Passli**.

---

## 🏛️ Stack Decision & Architectural Guarantees

Passli is a production-grade, zero-knowledge document vault. The frontend architecture is strictly **server-rendered Django 5** with zero JavaScript framework lock-in:

- **Server-Side Rendered (Django Templates)**: We do **NOT** use React, Next.js, or Vue. All views render semantic HTML5 via Django template inheritance (`base.html`), ensuring instant first-contentful paint, seamless CSRF handling, and zero client-side routing hydration failures.
- **Zero Node in Production**: Production environments (Docker, PythonAnywhere, AWS/GCP) build and run with zero Node.js runtime dependencies. All CSS assets are precompiled into committed static files (`static/css/app.css`), and all JS libraries are locally vendored.
- **Tailwind CSS v4 Standalone**: Styling is authored using Tailwind CSS v4 source at `static/src/app.css` and compiled into minified `static/css/app.css`.
- **Lightweight Vendored Interactivity (Alpine.js)**: Vendored locally at `static/js/vendor/alpine.min.js`. Used for lightweight micro-interactions without CDN or external script dependencies.
- **Cinematic Protocol Motion (GSAP + ScrollTrigger)**: Vendored locally at `static/js/vendor/gsap.min.js` and `static/js/vendor/ScrollTrigger.min.js` (see `static/js/vendor/LICENSE-GSAP.txt`). GSAP is deferred and loaded conditionally via `{% block extra_js %}` only on the landing page showpiece.

---

## 🛠️ Build Tooling & Rebuild Command

To compile Tailwind CSS during development:

### Using Globally Installed Tailwind CLI (npm):
```powershell
# Windows PowerShell
$env:NODE_PATH = "$(npm root -g)"
tailwindcss -i static/src/app.css -o static/css/app.css --minify

# Bash / Linux / macOS
export NODE_PATH="$(npm root -g)"
tailwindcss -i static/src/app.css -o static/css/app.css --minify
```

### Continuous Watch Mode (Development):
```powershell
$env:NODE_PATH = "$(npm root -g)"
tailwindcss -i static/src/app.css -o static/css/app.css --watch
```

### Standalone CLI Binary (Zero Node Installed):
Download the official standalone Tailwind CLI executable for your OS architecture:
```powershell
# Windows
.\tailwindcss.exe -i static/src/app.css -o static/css/app.css --minify

# Linux / macOS
./tailwindcss -i static/src/app.css -o static/css/app.css --minify
```

---

## ⚡ Motion System & Design Tokens

Passli defines a strict, non-hijacking motion system adhering to Hallmark and Unslop principles:

### Motion Tokens
| Token | Value | Purpose |
| :--- | :---: | :--- |
| `--duration-fast` | `120ms` | Instant button presses, toggles, icon micro-states |
| `--duration-base` | `200ms` | Card lifts, modal fade-ins, dropdown reveals |
| `--duration-slow` | `400ms` | Drawer slide-outs, bento panel expansions |
| `--duration-scroll` | `700ms+` | Pinned ScrollTrigger scrubbing on landing protocol |
| `--ease-out-expo` | `cubic-bezier(0.16, 1, 0.3, 1)` | Natural decelerating entrance |
| `--ease-in-out` | `cubic-bezier(0.4, 0, 0.2, 1)` | Symmetric state transitions |

### Motion Rules & Constraints
1. **Transform & Opacity Only**: Never animate layout properties (`width`, `height`, `margin`, `padding`, `top`, `left`). Animating transform and opacity guarantees 60fps GPU acceleration and keeps Cumulative Layout Shift (CLS) near `0`.
2. **Zero Smooth-Scroll Hijacking**: No Lenis, Locomotive, or mousewheel hijacking. Native OS scrolling is fully preserved.
3. **Strict Accessibility (`prefers-reduced-motion`)**:
   ```css
   @media (prefers-reduced-motion: reduce) {
     *, *::before, *::after {
       animation-duration: 0.01ms !important;
       transition-duration: 0.01ms !important;
       scroll-behavior: auto !important;
     }
   }
   ```
4. **Security Views Policy**: Recipient verification and portal views use subtle fade-in only. To preserve audit and verification integrity, **never animate countdown digits, Share Key text, error messages, or document preview frames**.

---

## 🛡️ Progressive Enhancement (No-JS Guarantee)

Passli guarantees that every critical feature functions without JavaScript:
1. `<html class="no-js">` is configured by default.
2. A synchronous inline script in `<head>` sets `.js` when JavaScript is supported:
   ```html
   <script>document.documentElement.classList.replace('no-js', 'js');</script>
   ```
3. Initial hidden/offset motion and tab hiding rules apply strictly under `.js`.
4. **Account Settings No-JS Fallback**: With JavaScript disabled, all three settings sections (Profile, Sign-in & Security, Activity) render completely stacked and accessible in the DOM. Zero inline `style="display:none"` is allowed.

---

## 📱 Mobile-First Recipient Architecture

The recipient flow (`/p/<uuid>/`) is designed mobile-first because physical QR passes are scanned from mobile smartphone cameras:
- **360px Viewport**: Compact vertical header, full-width high-contrast 8-character key input (`.key-input-display`), horizontal chip scroll navigation for multi-document passes.
- **768px Viewport (Tablet)**: Balanced touch-friendly padding, responsive dual-button layouts.
- **1280px+ Viewport (Desktop)**: Split dual-pane workstation view with sticky navigation sidebar and high-resolution watermarked viewer canvas.

---

## 🧪 Verification & Test Integrity

All 295 unit and Selenium automated tests enforce strict DOM contracts:
- **All 139 `data-testid` attributes** must be preserved across redesigns.
- **Character-for-Character String Parity**: Never modify asserted strings (e.g., `"Enter 8-Character Share Key"`, `"Invalid Share Key"`, `"Access Temporarily Locked"`, `"Usage Limit Reached"`, `"Session Securely Closed"`, `"Interactive Share Pass Generator"`).
- **Template Tag Integrity**: Preserving all `{% csrf_token %}`, form field names/IDs, and action endpoints.
