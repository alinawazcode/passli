/**
 * Passli — High-Performance Landing Page Interactive Sandbox
 * Provides zero-lag client-side telemetry, instant state changes,
 * dynamic scannable QR generation, and smooth navigation.
 */

(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    initSandbox();
    initSmoothAnchors();
  });

  function initSandbox() {
    const presetPills = document.querySelectorAll('.preset-pill');
    const docToggles = document.querySelectorAll('.doc-toggle');
    const passcodeToggle = document.getElementById('passcodeToggle');
    const generateBtn = document.getElementById('sandboxGenerateBtn');
    const revokeBtn = document.getElementById('sandboxRevokeBtn');

    const hudStatusBadge = document.getElementById('hudStatusBadge');
    const hudStatusText = document.getElementById('hudStatusText');
    const hudLinkValue = document.getElementById('hudLinkValue');
    const hudExpiryVal = document.getElementById('hudExpiryVal');
    const hudFilesVal = document.getElementById('hudFilesVal');
    const hudPinVal = document.getElementById('hudPinVal');
    const hudLogMessage = document.getElementById('hudLogMessage');

    const hudQrContainer = document.getElementById('hudQrContainer');
    const hudQrCanvas = document.getElementById('hudQrCanvas');
    const hudQrRevokedOverlay = document.getElementById('hudQrRevokedOverlay');
    const hudQrStatus = document.getElementById('hudQrStatus');

    if (!hudStatusBadge) return;

    let qrInstance = null;

    // Helper: Render Dynamic QR Code (using QRCode.js or SVG Fallback)
    function renderQr(url) {
      if (!hudQrCanvas) return;

      if (window.QRCode) {
        try {
          if (!qrInstance) {
            hudQrCanvas.innerHTML = '';
            qrInstance = new window.QRCode(hudQrCanvas, {
              text: url,
              width: 96,
              height: 96,
              colorDark: '#121826',
              colorLight: '#f8f9fb',
              correctLevel: window.QRCode.CorrectLevel.M
            });
          } else {
            qrInstance.clear();
            qrInstance.makeCode(url);
          }
          return;
        } catch (err) {
          console.warn('QRCode library error, using SVG fallback:', err);
        }
      }

      renderSvgQrFallback(hudQrCanvas, url);
    }

    // High-fidelity SVG Fallback Generator
    function renderSvgQrFallback(container, url) {
      if (!container) return;
      const size = 25;
      let hash = 0;
      for (let i = 0; i < url.length; i++) {
        hash = ((hash << 5) - hash) + url.charCodeAt(i);
        hash |= 0;
      }

      let rects = '';
      function drawFinder(x, y) {
        rects += '<rect x="' + x + '" y="' + y + '" width="28" height="28" rx="2" fill="var(--color-ink)"/>';
        rects += '<rect x="' + (x + 4) + '" y="' + (y + 4) + '" width="20" height="20" fill="var(--color-paper-2)"/>';
        rects += '<rect x="' + (x + 8) + '" y="' + (y + 8) + '" width="12" height="12" rx="1" fill="var(--color-accent)"/>';
      }

      drawFinder(2, 2);
      drawFinder(70, 2);
      drawFinder(2, 70);

      // Alignment Pattern at bottom right
      rects += '<rect x="68" y="68" width="20" height="20" rx="2" fill="var(--color-ink)"/>';
      rects += '<rect x="72" y="72" width="12" height="12" fill="var(--color-paper-2)"/>';
      rects += '<rect x="76" y="76" width="4" height="4" fill="var(--color-ink)"/>';

      let seed = Math.abs(hash);
      for (let r = 0; r < size; r++) {
        for (let c = 0; c < size; c++) {
          if ((r < 8 && c < 8) || (r < 8 && c >= 17) || (r >= 17 && c < 8)) continue;
          if (r >= 17 && r <= 22 && c >= 17 && c <= 22) continue;

          if (r === 6 || c === 6) {
            if ((r + c) % 2 === 0) {
              rects += '<rect x="' + (c * 4) + '" y="' + (r * 4) + '" width="4" height="4" fill="var(--color-ink)"/>';
            }
            continue;
          }

          seed = (seed * 9301 + 49297) % 233280;
          if ((seed / 233280) > 0.48) {
            const isAccent = (seed % 7 === 0);
            const fill = isAccent ? 'var(--color-accent)' : 'var(--color-ink)';
            rects += '<rect x="' + (c * 4) + '" y="' + (r * 4) + '" width="4" height="4" fill="' + fill + '"/>';
          }
        }
      }

      container.innerHTML = '<svg viewBox="0 0 100 100" width="96" height="96" aria-label="Ephemeral Pass QR Code"><rect width="100" height="100" fill="var(--color-paper-2)"/>' + rects + '</svg>';
    }

    // Initial render of default link
    const initialUrl = hudLinkValue ? hudLinkValue.textContent.trim() : 'https://passli.dev/p/8a3f910b2ce4';
    renderQr(initialUrl);

    // 1. Expiration Preset Selection
    presetPills.forEach(function (pill) {
      pill.addEventListener('click', function () {
        presetPills.forEach(function (p) { p.classList.remove('is-active'); });
        pill.classList.add('is-active');
        if (hudExpiryVal) {
          hudExpiryVal.textContent = pill.textContent.trim();
        }
        appendLog('Expiry window set to ' + pill.textContent.trim());
      });
    });

    // 2. Attached Documents Counter
    docToggles.forEach(function (toggle) {
      toggle.addEventListener('change', updateAttachedCount);
    });

    function updateAttachedCount() {
      let count = 0;
      docToggles.forEach(function (t) { if (t.checked) count++; });
      if (hudFilesVal) {
        hudFilesVal.textContent = count + (count === 1 ? ' Record Attached' : ' Records Attached');
      }
      appendLog('Updated bundle: ' + count + ' records selected');
    }

    // 3. Passcode Requirement Toggle
    if (passcodeToggle && hudPinVal) {
      passcodeToggle.addEventListener('change', function () {
        if (passcodeToggle.checked) {
          hudPinVal.textContent = 'Yes (8K7P-42XM)';
          appendLog('Cryptographic 8-character passcode requirement enabled');
        } else {
          hudPinVal.textContent = 'None (Direct Token Access)';
          appendLog('Passcode removed: token alone unlocks ephemeral session');
        }
      });
    }

    // 4. Regenerate Token Action
    if (generateBtn) {
      generateBtn.addEventListener('click', function () {
        const randomHex = Math.random().toString(16).substring(2, 14);
        const newUrl = 'https://passli.dev/p/' + randomHex;
        if (hudLinkValue) {
          hudLinkValue.textContent = newUrl;
        }

        // Generate and update the QR code
        renderQr(newUrl);

        // Reset status to valid / active
        hudStatusBadge.classList.remove('is-revoked');
        if (hudQrContainer) {
          hudQrContainer.classList.remove('is-revoked');
        }
        if (hudQrRevokedOverlay) {
          hudQrRevokedOverlay.classList.remove('is-active');
        }
        if (hudStatusText) {
          hudStatusText.textContent = 'Ready: Valid Token';
        }
        if (hudQrStatus) {
          hudQrStatus.textContent = 'token_status: active';
        }

        appendLog('Regenerated token: pass_' + randomHex.substring(0, 8) + '...');
      });
    }

    // 5. Revocation Simulation
    if (revokeBtn) {
      revokeBtn.addEventListener('click', function () {
        hudStatusBadge.classList.add('is-revoked');
        if (hudQrContainer) {
          hudQrContainer.classList.add('is-revoked');
        }
        if (hudQrRevokedOverlay) {
          hudQrRevokedOverlay.classList.add('is-active');
        }
        if (hudStatusText) {
          hudStatusText.textContent = 'Revoked: Access Severed';
        }
        if (hudQrStatus) {
          hudQrStatus.textContent = 'token_status: revoked';
        }
        appendLog('SECURITY ALERT: Token revoked by vault owner. 410 Gone enforced.');
      });
    }

    function appendLog(msg) {
      if (hudLogMessage) {
        hudLogMessage.textContent = '[TELEMETRY] ' + msg;
      }
    }
  }

  function initSmoothAnchors() {
    const anchors = document.querySelectorAll('a[href^="#"]');
    anchors.forEach(function (anchor) {
      anchor.addEventListener('click', function (e) {
        const targetId = this.getAttribute('href').substring(1);
        if (!targetId) return;
        const targetElement = document.getElementById(targetId);
        if (targetElement) {
          e.preventDefault();
          targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
          if (window.history && window.history.pushState) {
            history.pushState(null, '', '#' + targetId);
          }
        }
      });
    });
  }
})();
