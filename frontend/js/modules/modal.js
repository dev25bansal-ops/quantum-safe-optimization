/**
 * Modal Module
 * Handles preview modal functionality
 */

import { showToast } from './toast.js';

// Forward declaration for submitJob
let submitJobCallback = null;

export function setSubmitJobCallback(callback) {
    submitJobCallback = callback;
}

/**
 * Initialize modal functionality
 */
export function initModal() {
    const modal = document.getElementById('preview-modal');

    modal?.querySelector('.modal-close')?.addEventListener('click', () => {
        modal.classList.remove('active');
    });

    modal?.querySelector('.copy-json')?.addEventListener('click', () => {
        const json = document.getElementById('preview-json').textContent;
        navigator.clipboard.writeText(json);
        showToast('success', 'Copied', 'JSON copied to clipboard');
    });

    modal?.querySelector('.submit-from-preview')?.addEventListener('click', async () => {
        modal.classList.remove('active');
        if (submitJobCallback) await submitJobCallback();
    });

    // Close on backdrop click
    modal?.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });
}
