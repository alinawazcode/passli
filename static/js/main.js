/**
 * Passli — Stitch Cryptographic Precision Interactive Sandbox
 */

document.addEventListener('DOMContentLoaded', () => {
    initStitchSimulator();
    initVaultSearchShortcut();
});

function initVaultSearchShortcut() {
    const searchInput = document.querySelector('[data-testid="vault-search-input"]');
    if (!searchInput) {
        return;
    }

    document.addEventListener('keydown', (e) => {
        if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) {
            return;
        }

        const active = document.activeElement;
        const tag = active ? active.tagName.toLowerCase() : '';
        const isTyping = tag === 'input' || tag === 'textarea' || tag === 'select' ||
            Boolean(active && active.isContentEditable);

        if (isTyping || searchInput.disabled || searchInput.readOnly) {
            return;
        }

        e.preventDefault();
        searchInput.focus();
        searchInput.select();
    });
}

function initStitchSimulator() {
    const docCheckboxes = document.querySelectorAll('.sim-doc-checkbox');
    const expiryButtons = document.querySelectorAll('.expiry-btn');
    const generateBtn = document.getElementById('sim-generate-btn');
    const keyDisplay = document.getElementById('sim-key-text');
    const expiryDisplay = document.getElementById('sim-expiry-text');
    const docCountBadge = document.getElementById('sim-selected-count');
    const copyKeyBtn = document.getElementById('copy-key-btn');

    // Document Selection Count
    function updateSelectedDocs() {
        let count = 0;
        let sizeMB = 0;
        const sizes = [2.4, 1.1, 3.8];

        docCheckboxes.forEach((cb, idx) => {
            if (cb.checked) {
                count++;
                sizeMB += sizes[idx] || 1.0;
            }
        });

        if (docCountBadge) {
            docCountBadge.textContent = `${count} selected (${sizeMB.toFixed(1)} MB)`;
        }
    }

    docCheckboxes.forEach(cb => {
        cb.addEventListener('change', updateSelectedDocs);
    });

    // Expiration Selector
    let currentExpiry = '30 mins';
    expiryButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            expiryButtons.forEach(b => {
                b.className = 'expiry-btn py-1.5 text-center text-xs rounded border border-[#e2e8f0] bg-white text-[#475569] hover:bg-[#f8f9ff] font-medium transition';
            });
            btn.className = 'expiry-btn py-1.5 text-center text-xs rounded border border-[#0f172a] bg-[#0f172a] text-white font-semibold transition';
            currentExpiry = btn.getAttribute('data-val') || '30 mins';
            if (expiryDisplay) {
                expiryDisplay.textContent = currentExpiry;
            }
        });
    });

    // Copy Key Action
    if (copyKeyBtn && keyDisplay) {
        copyKeyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(keyDisplay.textContent.trim());
            const orig = copyKeyBtn.innerHTML;
            copyKeyBtn.innerHTML = '<span class="material-symbols-outlined text-[13px]">check</span> Copied!';
            setTimeout(() => {
                copyKeyBtn.innerHTML = orig;
            }, 1200);
        });
    }

    // Generate Key Simulation
    if (generateBtn && keyDisplay) {
        generateBtn.addEventListener('click', () => {
            const chars = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ';
            let key = '';
            for (let i = 0; i < 8; i++) {
                if (i === 4) key += '-';
                key += chars.charAt(Math.floor(Math.random() * chars.length));
            }
            keyDisplay.textContent = key;

            const origHtml = generateBtn.innerHTML;
            generateBtn.innerHTML = '<span class="material-symbols-outlined text-[16px]">check_circle</span> Pass & Key Generated!';
            generateBtn.disabled = true;

            setTimeout(() => {
                generateBtn.innerHTML = origHtml;
                generateBtn.disabled = false;
            }, 1200);
        });
    }
}
