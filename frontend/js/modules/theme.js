/**
 * Theme Management Module
 * Handles dark/light theme switching
 */

import { STATE } from './config.js';
import { showToast } from './toast.js';

/**
 * Initialize theme from localStorage
 */
export function initTheme() {
    document.documentElement.setAttribute('data-theme', STATE.theme);
    updateThemeToggle();
}

/**
 * Toggle between dark and light themes
 */
export function toggleTheme() {
    STATE.theme = STATE.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('theme', STATE.theme);
    document.documentElement.setAttribute('data-theme', STATE.theme);
    updateThemeToggle();
    showToast('info', 'Theme Changed', `Switched to ${STATE.theme} mode`);
}

/**
 * Update the theme toggle button icon
 */
export function updateThemeToggle() {
    const toggleBtn = document.getElementById('theme-toggle');
    if (toggleBtn) {
        toggleBtn.innerHTML = STATE.theme === 'dark'
            ? '<i class="fas fa-sun"></i>'
            : '<i class="fas fa-moon"></i>';
        toggleBtn.title = `Switch to ${STATE.theme === 'dark' ? 'light' : 'dark'} mode`;
    }
}

// Make globally accessible
window.toggleTheme = toggleTheme;
