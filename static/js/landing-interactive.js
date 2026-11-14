/**
 * Passli — High-Performance Landing Page Interactive Sandbox
 * Provides zero-lag client-side telemetry, instant state changes,
 * and smooth navigation.
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

    if (!hudStatusBadge) return;

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
          hudPinVal.textContent = 'Yes (4819-2041)';
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

        // Reset status to valid
        hudStatusBadge.classList.remove('is-revoked');
        if (hudStatusText) {
          hudStatusText.textContent = 'Ready: Valid Token';
        }

        appendLog('Regenerated token: pass_' + randomHex.substring(0, 8) + '...');
      });
    }

    // 5. Revocation Simulation
    if (revokeBtn) {
      revokeBtn.addEventListener('click', function () {
        hudStatusBadge.classList.add('is-revoked');
        if (hudStatusText) {
          hudStatusText.textContent = 'Revoked: Access Severed';
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
