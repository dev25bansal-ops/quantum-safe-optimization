/**
 * Utility Functions Module
 * Common helper functions used across the application
 */

/**
 * XSS Protection - Sanitize user input before rendering
 */
export function escapeHtml(unsafe) {
    if (unsafe == null) return '';
    return String(unsafe)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/**
 * Debounce function for input handlers
 */
export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

/**
 * Format date to relative time or locale string
 */
export function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    // Show relative time for recent jobs
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Format time in short format (HH:MM)
 */
export function formatTimeShort(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/**
 * Get icon for problem type
 */
export function getTypeIcon(type) {
    const icons = {
        'QAOA': '<i class="fas fa-layer-group"></i>',
        'VQE': '<i class="fas fa-atom"></i>',
        'ANNEALING': '<i class="fas fa-bolt"></i>'
    };
    return icons[type] || '<i class="fas fa-cog"></i>';
}

/**
 * Get icon for job status
 */
export function getStatusIcon(status) {
    const icons = {
        'pending': '<i class="fas fa-clock"></i>',
        'running': '<i class="fas fa-spinner fa-spin"></i>',
        'completed': '<i class="fas fa-check-circle"></i>',
        'failed': '<i class="fas fa-times-circle"></i>'
    };
    return icons[status] || '';
}

/**
 * Get auth headers for API requests
 */
export function getAuthHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    // Check both storage types for backwards compatibility
    const token = sessionStorage.getItem('authToken') || localStorage.getItem('authToken');
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}
