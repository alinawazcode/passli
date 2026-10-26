/**
 * Passli Account Settings Module
 * Vanilla ES module handling client-side section switching, hash routing,
 * disclosure bottom sheet / inline panels, OTP input grid, and form controls.
 */

// Step 1: Mark progressive enhancement readiness
document.documentElement.classList.add('js-ready');

document.addEventListener('DOMContentLoaded', () => {
    initAlertDismiss();
    initSectionNavigation();
    initDisclosurePanels();
    initAvatarControls();
    initOtpInputs();
    initResendTimers();
    initPasswordToggles();
    initPasswordStrength();
    initRemoveAvatarDialog();
});

/**
 * 0. Flash Alert Dismiss Handler
 */
function initAlertDismiss() {
    document.querySelectorAll('[data-action="dismiss-alert"]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const alert = btn.closest('.settings-alert');
            if (alert) {
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-4px)';
                alert.style.transition = 'opacity 150ms ease, transform 150ms ease';
                setTimeout(() => alert.remove(), 150);
            }
        });
    });
}

/**
 * 1. Section Navigation & Legacy Hash Mapping
 * Maps:
 *   #profile -> Profile section
 *   #username -> Profile section (and opens username row)
 *   #security -> Security section
 *   #email -> Security section (and opens email row)
 *   #password -> Security section (and opens password row)
 *   #activity -> Activity section
 */
function initSectionNavigation() {
    const sections = Array.from(document.querySelectorAll('.settings-section'));
    const menuItems = Array.from(document.querySelectorAll('.settings-menu-item'));
    const tabPills = Array.from(document.querySelectorAll('.settings-tab-pill'));

    if (!sections.length) return;

    function getTargetSectionAndPanel(hash) {
        const clean = (hash || '').replace('#', '').toLowerCase();
        if (clean === 'username') {
            return { sectionId: 'profile', panelId: 'panel-username' };
        }
        if (clean === 'email') {
            return { sectionId: 'security', panelId: 'panel-email' };
        }
        if (clean === 'password') {
            return { sectionId: 'security', panelId: 'panel-password' };
        }
        if (clean === 'security') {
            return { sectionId: 'security', panelId: null };
        }
        if (clean === 'activity') {
            return { sectionId: 'activity', panelId: null };
        }
        return { sectionId: 'profile', panelId: null };
    }

    function switchSection(targetSectionId, options = {}) {
        sections.forEach(section => {
            const isMatch = section.id === targetSectionId;
            section.classList.toggle('active', isMatch);
            if (!isMatch && options.closePanels !== false) {
                // Close any open panels in other sections
                section.querySelectorAll('.settings-panel').forEach(p => {
                    p.setAttribute('hidden', '');
                });
                section.querySelectorAll('[aria-expanded="true"]').forEach(btn => {
                    btn.setAttribute('aria-expanded', 'false');
                });
            }
        });

        // Update Desktop Menu
        menuItems.forEach(item => {
            const href = (item.getAttribute('href') || '').replace('#', '');
            const isMatch = href === targetSectionId;
            item.classList.toggle('active', isMatch);
            item.setAttribute('aria-current', isMatch ? 'page' : 'false');
        });

        // Update Mobile Tab Pills
        tabPills.forEach(pill => {
            const href = (pill.getAttribute('href') || '').replace('#', '');
            const isMatch = href === targetSectionId;
            pill.classList.toggle('active', isMatch);
            pill.setAttribute('aria-current', isMatch ? 'page' : 'false');
            if (isMatch) {
                const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                pill.scrollIntoView({
                    behavior: prefersReducedMotion ? 'auto' : 'smooth',
                    inline: 'center',
                    block: 'nearest'
                });
            }
        });

        if (options.updateHash !== false) {
            if (window.location.hash !== `#${targetSectionId}`) {
                history.pushState(null, '', `#${targetSectionId}`);
            }
        }
    }

    // Attach click listeners
    const allNavButtons = [...menuItems, ...tabPills];
    allNavButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const href = btn.getAttribute('href');
            if (!href) return;
            const { sectionId } = getTargetSectionAndPanel(href);
            switchSection(sectionId, { updateHash: true });
        });
    });

    // Check on load: Did server specify an open panel, inline errors, or flash alerts?
    let serverOpenPanel = document.querySelector('.settings-panel[data-server-open="true"], .settings-panel:has(.settings-error:not(:empty))');

    // Inspect danger flash alerts to connect redirected server rejections with their corresponding panel & fields
    const dangerAlerts = Array.from(document.querySelectorAll('.settings-alert-danger'));
    dangerAlerts.forEach(alertElem => {
        const txt = (alertElem.textContent || '').trim();
        // 1. Profile display name error
        if (txt.includes('Could not update profile')) {
            serverOpenPanel = document.getElementById('panel-display-name');
            if (serverOpenPanel) {
                serverOpenPanel.setAttribute('data-server-open', 'true');
                const dnInput = document.getElementById('profile-display-name');
                let dnErr = document.getElementById('profile-display-name-error');
                if (dnInput && !dnErr) {
                    dnErr = document.createElement('span');
                    dnErr.className = 'settings-error';
                    dnErr.id = 'profile-display-name-error';
                    dnErr.setAttribute('role', 'alert');
                    dnErr.innerHTML = '<svg class="settings-icon-sm" aria-hidden="true"><use href="/static/img/icons/settings-sprite.svg#icon-clock"></use></svg> Display name cannot exceed 50 characters.';
                    dnInput.insertAdjacentElement('afterend', dnErr);
                    dnInput.setAttribute('aria-invalid', 'true');
                    dnInput.setAttribute('aria-describedby', 'profile-display-name-error');
                }
            }
        }
        // 2. Current password error in username change
        if (txt.toLowerCase().includes('password') && (txt.toLowerCase().includes('incorrect') || txt.toLowerCase().includes('wrong'))) {
            const pwdInput = document.getElementById('settings-username-password');
            let pwdErr = document.getElementById('username-password-error');
            if (pwdInput && !pwdErr) {
                pwdErr = document.createElement('span');
                pwdErr.className = 'settings-error';
                pwdErr.id = 'username-password-error';
                pwdErr.setAttribute('role', 'alert');
                pwdErr.innerHTML = `<svg class="settings-icon-sm" aria-hidden="true"><use href="/static/img/icons/settings-sprite.svg#icon-clock"></use></svg> ${txt}`;
                pwdInput.insertAdjacentElement('afterend', pwdErr);
                pwdInput.setAttribute('aria-invalid', 'true');
                pwdInput.setAttribute('aria-describedby', 'username-password-error');
            }
        }
        // 3. New username error
        if (txt.toLowerCase().includes('username') || txt.includes('@')) {
            const unInput = document.getElementById('settings-new-username');
            let unErr = document.getElementById('new-username-error');
            if (unInput && !unErr) {
                unErr = document.createElement('span');
                unErr.className = 'settings-error';
                unErr.id = 'new-username-error';
                unErr.setAttribute('role', 'alert');
                unErr.innerHTML = `<svg class="settings-icon-sm" aria-hidden="true"><use href="/static/img/icons/settings-sprite.svg#icon-clock"></use></svg> ${txt}`;
                unInput.insertAdjacentElement('afterend', unErr);
                unInput.setAttribute('aria-invalid', 'true');
                unInput.setAttribute('aria-describedby', 'new-username-error');
            }
        }
    });

    if (serverOpenPanel) {
        const parentSection = serverOpenPanel.closest('.settings-section');
        if (parentSection) {
            switchSection(parentSection.id, { closePanels: false, updateHash: false });
            serverOpenPanel.removeAttribute('hidden');
            const toggleBtn = document.querySelector(`[aria-controls="${serverOpenPanel.id}"]`);
            if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'true');
            const invalidField = serverOpenPanel.querySelector('[aria-invalid="true"], input:not([type="hidden"]), select, textarea');
            if (invalidField) {
                invalidField.focus();
            }
            return;
        }
    }

    // Otherwise inspect URL hash
    const initialHash = window.location.hash;
    const { sectionId, panelId } = getTargetSectionAndPanel(initialHash);
    switchSection(sectionId, { updateHash: false });

    if (panelId) {
        const targetPanel = document.getElementById(panelId);
        if (targetPanel) {
            targetPanel.removeAttribute('hidden');
            const toggleBtn = document.querySelector(`[aria-controls="${panelId}"]`);
            if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'true');
        }
    }

    // Listen to external hashchange and popstate (browser back/forward navigation)
    function handleHistoryNav() {
        const { sectionId: newSec, panelId: newPan } = getTargetSectionAndPanel(window.location.hash);
        switchSection(newSec, { updateHash: false });
        if (newPan) {
            const p = document.getElementById(newPan);
            if (p) {
                p.removeAttribute('hidden');
                const tb = document.querySelector(`[aria-controls="${newPan}"]`);
                if (tb) tb.setAttribute('aria-expanded', 'true');
            }
        }
    }
    window.addEventListener('hashchange', handleHistoryNav);
    window.addEventListener('popstate', handleHistoryNav);
}

/**
 * 2. Disclosure Panels & Mobile Bottom Sheet Controller
 */
function initDisclosurePanels() {
    const panels = Array.from(document.querySelectorAll('.settings-panel'));
    const toggleButtons = Array.from(document.querySelectorAll('[data-action="toggle-panel"]'));
    const backdrop = document.querySelector('.settings-sheet-backdrop');

    // Hide any panels not explicitly marked open on load
    panels.forEach(p => {
        const hasVisibleError = Array.from(p.querySelectorAll('.settings-error:not(:empty)')).some(err => !err.hasAttribute('hidden'));
        if (p.getAttribute('data-server-open') !== 'true' && !hasVisibleError) {
            p.setAttribute('hidden', '');
        }
    });

    function isMobileView() {
        return window.innerWidth < 640;
    }

    function openPanel(panel, triggerBtn) {
        // Close any other open panels in document
        panels.forEach(other => {
            if (other !== panel) {
                other.setAttribute('hidden', '');
                const otherBtn = document.querySelector(`[aria-controls="${other.id}"]`);
                if (otherBtn) otherBtn.setAttribute('aria-expanded', 'false');
            }
        });

        panel.removeAttribute('hidden');
        if (triggerBtn) {
            triggerBtn.setAttribute('aria-expanded', 'true');
        }

        if (isMobileView()) {
            document.body.classList.add('settings-sheet-open');
            panel.setAttribute('role', 'dialog');
            panel.setAttribute('aria-modal', 'true');
        } else {
            panel.removeAttribute('role');
            panel.removeAttribute('aria-modal');
        }

        // Focus first input
        const firstInput = panel.querySelector('input:not([type="hidden"]), button:not(.settings-sheet-drag-handle)');
        if (firstInput) {
            firstInput.focus();
        }
    }

    function closePanel(panel, returnFocusToTrigger = true) {
        panel.setAttribute('hidden', '');
        document.body.classList.remove('settings-sheet-open');
        panel.removeAttribute('role');
        panel.removeAttribute('aria-modal');

        const triggerBtn = document.querySelector(`[aria-controls="${panel.id}"]`);
        if (triggerBtn) {
            triggerBtn.setAttribute('aria-expanded', 'false');
            if (returnFocusToTrigger) {
                triggerBtn.focus();
            }
        }
    }

    toggleButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const panelId = btn.getAttribute('aria-controls');
            if (!panelId) return;
            const panel = document.getElementById(panelId);
            if (!panel) return;

            const isCurrentlyOpen = !panel.hasAttribute('hidden');
            if (isCurrentlyOpen) {
                closePanel(panel);
            } else {
                openPanel(panel, btn);
            }
        });
    });

    // Wire up panel internal "Cancel" buttons
    document.querySelectorAll('[data-action="close-panel"]').forEach(cancelBtn => {
        cancelBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const panel = cancelBtn.closest('.settings-panel');
            if (panel) closePanel(panel, true);
        });
    });

    // Click on mobile backdrop closes open sheet
    if (backdrop) {
        backdrop.addEventListener('click', () => {
            const openPan = document.querySelector('.settings-panel:not([hidden])');
            if (openPan) closePanel(openPan, true);
        });
    }

    // Escape closes untouched panel/sheet (unless a native dialog is currently open)
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const openDialog = document.querySelector('dialog[open]');
            if (openDialog) {
                // Let the native dialog handle its own Escape dismissal
                return;
            }
            const openPan = document.querySelector('.settings-panel:not([hidden])');
            if (openPan) {
                closePanel(openPan, true);
            }
        }
    });

    // Make mobile rows tappable to open matching panel
    document.querySelectorAll('.settings-row[data-panel-id]').forEach(row => {
        row.addEventListener('click', (e) => {
            if (!isMobileView()) return;
            // Don't trigger if user clicked directly on a button or link inside row
            if (e.target.closest('button, a, input')) return;
            const panelId = row.getAttribute('data-panel-id');
            const panel = document.getElementById(panelId);
            const triggerBtn = row.querySelector('[data-action="toggle-panel"]');
            if (panel && triggerBtn) {
                openPanel(panel, triggerBtn);
            }
        });
    });
}

/**
 * 3. Avatar Upload & Instant Preview
 */
function initAvatarControls() {
    const fileInput = document.getElementById('avatar-file-input');
    const chooseBtn = document.getElementById('btn-choose-avatar');
    const rowPreviewImg = document.getElementById('avatar-preview-img');
    const rowFallbackInitial = document.getElementById('avatar-fallback-initial');
    const panelPreviewImg = document.getElementById('avatar-panel-preview');
    const panelFallbackInitial = document.getElementById('avatar-panel-initial');
    const pendingActions = document.getElementById('avatar-pending-actions');
    const cancelFileBtn = document.getElementById('btn-cancel-avatar-file');
    const errorContainer = document.getElementById('avatar-client-error');

    if (!fileInput || !chooseBtn) return;

    // Cache original state for cancel restoration
    const originalRowSrc = rowPreviewImg ? rowPreviewImg.getAttribute('src') : '';
    const hadInitialAvatar = rowPreviewImg && originalRowSrc && !rowPreviewImg.hasAttribute('hidden');

    function resetFileSelection() {
        fileInput.value = '';
        if (errorContainer) {
            errorContainer.textContent = '';
            errorContainer.setAttribute('hidden', '');
        }
        if (pendingActions) {
            pendingActions.setAttribute('hidden', '');
        }
        // Restore previews to initial persisted state
        if (hadInitialAvatar) {
            if (rowPreviewImg) {
                rowPreviewImg.src = originalRowSrc;
                rowPreviewImg.removeAttribute('hidden');
            }
            if (rowFallbackInitial) rowFallbackInitial.setAttribute('hidden', '');
            if (panelPreviewImg) {
                panelPreviewImg.src = originalRowSrc;
                panelPreviewImg.removeAttribute('hidden');
            }
            if (panelFallbackInitial) panelFallbackInitial.setAttribute('hidden', '');
        } else {
            if (rowPreviewImg) {
                rowPreviewImg.src = '';
                rowPreviewImg.setAttribute('hidden', '');
            }
            if (rowFallbackInitial) rowFallbackInitial.removeAttribute('hidden');
            if (panelPreviewImg) {
                panelPreviewImg.src = '';
                panelPreviewImg.setAttribute('hidden', '');
            }
            if (panelFallbackInitial) panelFallbackInitial.removeAttribute('hidden');
        }
    }

    chooseBtn.addEventListener('click', (e) => {
        e.preventDefault();
        fileInput.click();
    });

    if (cancelFileBtn) {
        cancelFileBtn.addEventListener('click', (e) => {
            e.preventDefault();
            resetFileSelection();
        });
    }

    fileInput.addEventListener('change', () => {
        const file = fileInput.files && fileInput.files[0];
        if (!file) {
            resetFileSelection();
            return;
        }

        if (errorContainer) {
            errorContainer.textContent = '';
            errorContainer.setAttribute('hidden', '');
        }

        const maxBytes = 2 * 1024 * 1024;
        if (file.size > maxBytes) {
            resetFileSelection();
            if (errorContainer) {
                errorContainer.textContent = 'Selected image exceeds the 2 MB limit.';
                errorContainer.removeAttribute('hidden');
            }
            return;
        }

        const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
        if (!allowedTypes.includes(file.type)) {
            resetFileSelection();
            if (errorContainer) {
                errorContainer.textContent = 'Please choose a JPEG, PNG, or WebP image.';
                errorContainer.removeAttribute('hidden');
            }
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            const dataUrl = e.target.result;
            if (rowPreviewImg) {
                rowPreviewImg.src = dataUrl;
                rowPreviewImg.removeAttribute('hidden');
            }
            if (rowFallbackInitial) {
                rowFallbackInitial.setAttribute('hidden', '');
            }
            if (panelPreviewImg) {
                panelPreviewImg.src = dataUrl;
                panelPreviewImg.removeAttribute('hidden');
            }
            if (panelFallbackInitial) {
                panelFallbackInitial.setAttribute('hidden', '');
            }
            if (pendingActions) {
                pendingActions.removeAttribute('hidden');
            }
        };
        reader.readAsDataURL(file);
    });
}

/**
 * 4. Remove Photo Native Dialog Confirmation
 */
function initRemoveAvatarDialog() {
    const triggerBtn = document.getElementById('btn-remove-avatar-trigger');
    const dialog = document.getElementById('remove-avatar-dialog');
    const cancelBtn = document.getElementById('btn-dialog-cancel-remove');

    if (!triggerBtn || !dialog) return;

    triggerBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (typeof dialog.showModal === 'function') {
            dialog.showModal();
        } else {
            // Fallback for older browsers
            if (window.confirm('Are you sure you want to remove your avatar?')) {
                const form = document.getElementById('avatar-remove-form');
                if (form) form.submit();
            }
        }
    });

    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            dialog.close();
        });
    }
}

/**
 * 5. 6-Cell OTP Grid Handler
 */
function initOtpInputs() {
    function bindOtpGroup(containerId, fallbackInputId) {
        const container = document.getElementById(containerId);
        const fallbackInput = document.getElementById(fallbackInputId);
        if (!container || !fallbackInput) return;

        const boxes = Array.from(container.querySelectorAll('.settings-otp-box'));
        if (boxes.length !== 6) return;

        function syncToFallback() {
            fallbackInput.value = boxes.map(b => b.value.trim()).join('');
        }

        boxes.forEach((box, index) => {
            box.addEventListener('input', () => {
                const clean = box.value.replace(/[^0-9]/g, '');
                box.value = clean ? clean[0] : '';
                syncToFallback();
                if (box.value && index < 5) {
                    boxes[index + 1].focus();
                    boxes[index + 1].select();
                }
            });

            box.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace') {
                    if (!box.value && index > 0) {
                        boxes[index - 1].focus();
                        boxes[index - 1].value = '';
                        syncToFallback();
                        e.preventDefault();
                    } else if (box.value) {
                        box.value = '';
                        syncToFallback();
                        e.preventDefault();
                    }
                } else if (e.key === 'ArrowLeft' && index > 0) {
                    boxes[index - 1].focus();
                    boxes[index - 1].select();
                    e.preventDefault();
                } else if (e.key === 'ArrowRight' && index < 5) {
                    boxes[index + 1].focus();
                    boxes[index + 1].select();
                    e.preventDefault();
                }
            });

            box.addEventListener('paste', (e) => {
                e.preventDefault();
                const text = (e.clipboardData || window.clipboardData).getData('text');
                const digits = text.replace(/[^0-9]/g, '').slice(0, 6);
                if (!digits) return;

                digits.split('').forEach((d, i) => {
                    if (boxes[i]) boxes[i].value = d;
                });
                syncToFallback();
                const nextIdx = Math.min(digits.length, 5);
                boxes[nextIdx].focus();
            });

            box.addEventListener('focus', () => box.select());
        });
    }

    bindOtpGroup('email-otp-boxes-container', 'email-otp-combined-input');
    bindOtpGroup('password-otp-boxes-container', 'password-otp-combined-input');
}

/**
 * 6. OTP Resend Timers
 */
function initResendTimers() {
    function bindTimer(buttonId, textId) {
        const btn = document.getElementById(buttonId);
        const text = document.getElementById(textId);
        if (!btn || !text) return;

        let wait = parseInt(btn.getAttribute('data-cooldown') || '0', 10);
        if (isNaN(wait) || wait <= 0) return;

        btn.disabled = true;
        text.textContent = `Resend in ${wait}s`;

        const interval = setInterval(() => {
            wait -= 1;
            if (wait <= 0) {
                clearInterval(interval);
                btn.disabled = false;
                text.textContent = 'Resend Code';
                btn.removeAttribute('data-cooldown');
            } else {
                text.textContent = `Resend in ${wait}s`;
            }
        }, 1000);
    }

    bindTimer('btn-resend-email-otp', 'resend-email-timer-text');
    bindTimer('btn-resend-password-otp', 'resend-pwd-timer-text');
}

/**
 * 7. Password Visibility Toggles
 */
function initPasswordToggles() {
    const buttons = document.querySelectorAll('.settings-password-toggle-btn');
    buttons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const wrapper = btn.closest('.settings-password-wrapper');
            if (!wrapper) return;
            const input = wrapper.querySelector('input');
            if (!input) return;

            const isPassword = input.type === 'password';
            input.type = isPassword ? 'text' : 'password';
            btn.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
        });
    });
}

/**
 * 8. Password Strength Indicator
 */
function initPasswordStrength() {
    function setupStrength(inputId, meterId, hintId) {
        const input = document.getElementById(inputId);
        const meter = document.getElementById(meterId);
        const hint = document.getElementById(hintId);
        if (!input || !meter) return;

        const segments = Array.from(meter.querySelectorAll('.settings-strength-segment'));

        input.addEventListener('input', () => {
            const val = input.value;
            segments.forEach(s => {
                s.className = 'settings-strength-segment';
            });

            if (!val) {
                if (hint) hint.textContent = 'Enter a password to evaluate strength.';
                return;
            }

            let score = 0;
            if (val.length >= 8) score += 1;
            if (val.length >= 12) score += 1;
            if (/[a-z]/.test(val) && /[A-Z]/.test(val)) score += 1;
            if (/[0-9]/.test(val) && /[^a-zA-Z0-9]/.test(val)) score += 1;

            for (let i = 0; i < score; i++) {
                if (segments[i]) {
                    if (score === 1) segments[i].classList.add('active-weak');
                    else if (score === 2) segments[i].classList.add('active-fair');
                    else if (score === 3) segments[i].classList.add('active-good');
                    else segments[i].classList.add('active-strong');
                }
            }

            if (hint) {
                if (score <= 1) hint.textContent = 'Weak password';
                else if (score === 2) hint.textContent = 'Fair password';
                else if (score === 3) hint.textContent = 'Good password';
                else hint.textContent = 'Strong password';
            }
        });
    }

    setupStrength('settings-new-password', 'strength-meter-normal', 'strength-hint-normal');
    setupStrength('settings-otp-new-password', 'strength-meter-otp', 'strength-hint-otp');
}
