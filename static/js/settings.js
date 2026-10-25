document.documentElement.classList.add('js-ready');

document.addEventListener('DOMContentLoaded', () => {
    initNavigationTabs();
    initAvatarUploader();
    initOtpInputs();
    initResendTimer();
    initPasswordToggles();
    initPasswordStrength();
});

function initNavigationTabs() {
    const navItems = document.querySelectorAll('.settings-nav-item');
    if (!navItems.length) return;

    function activateTab(targetId) {
        if (!targetId) return;
        const hash = targetId.startsWith('#') ? targetId : `#${targetId}`;
        
        navItems.forEach(item => {
            const isMatch = item.getAttribute('href') === hash;
            item.classList.toggle('active', isMatch);
            item.setAttribute('aria-current', isMatch ? 'true' : 'false');
        });
    }

    // Read current hash on page load
    if (window.location.hash) {
        activateTab(window.location.hash);
    }

    // Listen to hash changes
    window.addEventListener('hashchange', () => {
        activateTab(window.location.hash);
    });

    // Smooth scroll for nav items
    navItems.forEach(link => {
        link.addEventListener('click', (e) => {
            const targetId = link.getAttribute('href');
            if (targetId && targetId.startsWith('#')) {
                const targetCard = document.querySelector(targetId);
                if (targetCard) {
                    targetCard.scrollIntoView({ behavior: 'smooth' });
                }
            }
        });
    });
}

function initAvatarUploader() {
    const fileInput = document.getElementById('avatar-file-input');
    const chooseBtn = document.getElementById('btn-choose-avatar');
    const previewImg = document.getElementById('avatar-preview-img');
    const fallbackInitial = document.getElementById('avatar-fallback-initial');
    const uploadForm = document.getElementById('avatar-upload-form');
    const errorContainer = document.getElementById('avatar-client-error');

    if (!fileInput || !chooseBtn) return;

    chooseBtn.addEventListener('click', (e) => {
        e.preventDefault();
        fileInput.click();
    });

    fileInput.addEventListener('change', () => {
        const file = fileInput.files && fileInput.files[0];
        if (!file) return;

        // Clear previous error
        if (errorContainer) {
            errorContainer.textContent = '';
            errorContainer.style.display = 'none';
        }

        // Validate client size limit: 2 MB
        const maxBytes = 2 * 1024 * 1024;
        if (file.size > maxBytes) {
            fileInput.value = '';
            if (errorContainer) {
                errorContainer.textContent = 'Selected image exceeds the 2 MB limit.';
                errorContainer.style.display = 'block';
            }
            return;
        }

        // Validate MIME type
        const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
        if (!allowedTypes.includes(file.type)) {
            fileInput.value = '';
            if (errorContainer) {
                errorContainer.textContent = 'Please choose a JPEG, PNG, or WebP image.';
                errorContainer.style.display = 'block';
            }
            return;
        }

        // Client-side preview
        const reader = new FileReader();
        reader.onload = (e) => {
            if (previewImg) {
                previewImg.src = e.target.result;
                previewImg.style.display = 'block';
                if (fallbackInitial) fallbackInitial.style.display = 'none';
            }
            // Auto submit or highlight upload action
            if (uploadForm) {
                uploadForm.submit();
            }
        };
        reader.readAsDataURL(file);
    });
}

function initOtpInputs() {
    function bindOtpGroup(containerId, fallbackInputId) {
        const container = document.getElementById(containerId);
        const fallbackInput = document.getElementById(fallbackInputId);
        if (!container || !fallbackInput) return;

        const boxes = Array.from(container.querySelectorAll('.settings-otp-box'));
        if (boxes.length !== 6) return;

        function syncToFallback() {
            const fullVal = boxes.map(b => b.value.trim()).join('');
            fallbackInput.value = fullVal;
            boxes.forEach(b => {
                b.classList.toggle('filled', b.value.length > 0);
            });
        }

        boxes.forEach((box, index) => {
            box.addEventListener('input', () => {
                const val = box.value.replace(/[^0-9]/g, '');
                box.value = val ? val[0] : '';
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
                const pasteData = (e.clipboardData || window.clipboardData).getData('text');
                const cleanDigits = pasteData.replace(/[^0-9]/g, '').slice(0, 6);
                if (!cleanDigits) return;

                cleanDigits.split('').forEach((digit, i) => {
                    if (boxes[i]) {
                        boxes[i].value = digit;
                    }
                });
                syncToFallback();
                const focusIndex = Math.min(cleanDigits.length, 5);
                boxes[focusIndex].focus();
            });

            box.addEventListener('focus', () => {
                box.select();
            });
        });
    }

    bindOtpGroup('email-otp-boxes-container', 'email-otp-combined-input');
    bindOtpGroup('password-otp-boxes-container', 'password-otp-combined-input');
}

function initResendTimer() {
    function bindTimer(buttonId, textId) {
        const resendBtn = document.getElementById(buttonId);
        const timerText = document.getElementById(textId);
        if (!resendBtn || !timerText) return;

        let cooldownSeconds = parseInt(resendBtn.getAttribute('data-cooldown') || '0', 10);
        if (isNaN(cooldownSeconds) || cooldownSeconds <= 0) return;

        resendBtn.disabled = true;
        timerText.textContent = `Resend in ${cooldownSeconds}s`;

        const timer = setInterval(() => {
            cooldownSeconds -= 1;
            if (cooldownSeconds <= 0) {
                clearInterval(timer);
                resendBtn.disabled = false;
                timerText.textContent = 'Resend Code';
                resendBtn.removeAttribute('data-cooldown');
            } else {
                timerText.textContent = `Resend in ${cooldownSeconds}s`;
            }
        }, 1000);
    }

    bindTimer('btn-resend-email-otp', 'resend-email-timer-text');
    bindTimer('btn-resend-password-otp', 'resend-pwd-timer-text');
}

function initPasswordToggles() {
    const toggleButtons = document.querySelectorAll('.settings-password-toggle');
    toggleButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const wrapper = btn.closest('.settings-password-field-wrapper');
            if (!wrapper) return;
            const input = wrapper.querySelector('input');
            const icon = btn.querySelector('.material-symbols-outlined');
            if (!input) return;

            if (input.type === 'password') {
                input.type = 'text';
                if (icon) icon.textContent = 'visibility_off';
                btn.setAttribute('aria-label', 'Hide password');
            } else {
                input.type = 'password';
                if (icon) icon.textContent = 'visibility';
                btn.setAttribute('aria-label', 'Show password');
            }
        });
    });
}

function initPasswordStrength() {
    function setupStrengthMeter(inputId, barId, hintId) {
        const input = document.getElementById(inputId);
        const bar = document.getElementById(barId);
        const hint = document.getElementById(hintId);
        if (!input || !bar || !hint) return;

        input.addEventListener('input', () => {
            const val = input.value;
            if (!val) {
                bar.className = 'settings-strength-bar';
                hint.textContent = 'Strength hint: Enter password (hint only; server validators enforce policy)';
                return;
            }

            let score = 0;
            if (val.length >= 8) score += 1;
            if (val.length >= 12) score += 1;
            if (/[a-z]/.test(val) && /[A-Z]/.test(val)) score += 1;
            if (/[0-9]/.test(val) && /[^a-zA-Z0-9]/.test(val)) score += 1;

            bar.className = 'settings-strength-bar';
            if (score <= 1) {
                bar.classList.add('weak');
                hint.textContent = 'Strength hint: Weak (hint only; server validators enforce policy)';
            } else if (score === 2) {
                bar.classList.add('fair');
                hint.textContent = 'Strength hint: Fair (hint only; server validators enforce policy)';
            } else if (score === 3) {
                bar.classList.add('good');
                hint.textContent = 'Strength hint: Good (hint only; server validators enforce policy)';
            } else {
                bar.classList.add('strong');
                hint.textContent = 'Strength hint: Strong (hint only; server validators enforce policy)';
            }
        });
    }

    setupStrengthMeter('settings-new-password', 'strength-bar-normal', 'strength-hint-normal');
    setupStrengthMeter('settings-otp-new-password', 'strength-bar-otp', 'strength-hint-otp');
}


