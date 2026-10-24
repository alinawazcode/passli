/**
 * Passli Account Settings Vanilla ES Module
 * Progressive enhancement for avatar preview, tab routing, and responsive interactions.
 */

document.addEventListener('DOMContentLoaded', () => {
    initNavigationTabs();
    initAvatarUploader();
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
