/**
 * Toast Notifications Module
 * Handles toast notification display and management
 */

/**
 * Show a toast notification
 * @param {string} type - 'success', 'error', 'warning', 'info'
 * @param {string} title - Toast title
 * @param {string} message - Toast message
 * @param {number} duration - Auto-dismiss duration in ms (default 5000)
 */
export function showToast(type, title, message, duration = 5000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type]}</span>
        <div class="toast-message">
            <strong>${title}</strong>
            <span>${message}</span>
        </div>
        <button class="toast-close">&times;</button>
    `;

    container.appendChild(toast);

    // Auto remove after duration
    const autoRemove = setTimeout(() => {
        toast.remove();
    }, duration);

    // Manual close
    toast.querySelector('.toast-close').addEventListener('click', () => {
        clearTimeout(autoRemove);
        toast.remove();
    });
}

// Make globally accessible
window.showToast = showToast;
