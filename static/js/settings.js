/**
 * Passli Account Settings Vanilla ES Module
 * Progressive enhancement for avatar preview, tab routing, and responsive interactions.
 */

document.documentElement.classList.add('js-ready');

document.addEventListener('DOMContentLoaded', () => {
    initNavigationTabs();
    initAvatarUploader();
    initOtpInputs();
    initResendTimer();
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
    const container = document.getElementById('email-otp-boxes-container');
    const fallbackInput = document.getElementById('email-otp-combined-input');
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

function initResendTimer() {
    const resendBtn = document.getElementById('btn-resend-email-otp');
    const timerText = document.getElementById('resend-email-timer-text');
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

