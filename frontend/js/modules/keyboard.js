/**
 * Keyboard Shortcuts Module
 * Handles keyboard shortcuts for navigation and actions
 */

import { navigateToSection } from './navigation.js';
import { showToast } from './toast.js';
import { toggleTheme } from './theme.js';

// Forward declaration for loadJobs
let loadJobsCallback = null;

export function setKeyboardCallbacks(loadJobs) {
    loadJobsCallback = loadJobs;
}

/**
 * Initialize keyboard shortcuts
 */
export function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Don't trigger shortcuts when typing in inputs
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
            // Escape to blur input
            if (e.key === 'Escape') {
                e.target.blur();
            }
            return;
        }

        // Don't trigger with modifier keys (except for Ctrl+K search)
        if (e.altKey || e.metaKey) return;

        // Ctrl+K or / for search focus
        if ((e.ctrlKey && e.key === 'k') || e.key === '/') {
            e.preventDefault();
            document.getElementById('search-input')?.focus();
            return;
        }

        // Skip if Ctrl is pressed for other keys
        if (e.ctrlKey) return;

        switch (e.key.toLowerCase()) {
            case 'n':
                // New job
                e.preventDefault();
                navigateToSection('new-job');
                break;

            case 'j':
                // Jobs list
                e.preventDefault();
                navigateToSection('jobs');
                break;

            case 'o':
                // Overview
                e.preventDefault();
                navigateToSection('overview');
                break;

            case 'r':
                // Refresh
                e.preventDefault();
                if (loadJobsCallback) loadJobsCallback(true);
                showToast('info', 'Refreshing', 'Reloading jobs...');
                break;

            case 't':
                // Toggle theme
                e.preventDefault();
                toggleTheme();
                break;

            case 's':
                // Settings
                e.preventDefault();
                navigateToSection('settings');
                break;

            case 'escape':
                // Close modals
                document.getElementById('auth-modal')?.classList.remove('active');
                document.getElementById('preview-modal')?.classList.remove('active');
                document.getElementById('notification-dropdown')?.classList.remove('active');
                document.getElementById('user-dropdown')?.classList.remove('active');
                document.getElementById('compare-modal')?.classList.remove('active');
                break;

            case '?':
                // Show keyboard shortcuts help
                e.preventDefault();
                showKeyboardShortcutsHelp();
                break;
        }
    });
}

/**
 * Show keyboard shortcuts help overlay
 */
export function showKeyboardShortcutsHelp() {
    const shortcuts = [
        { key: 'N', desc: 'New Job' },
        { key: 'J', desc: 'Jobs List' },
        { key: 'O', desc: 'Overview' },
        { key: 'S', desc: 'Settings' },
        { key: 'R', desc: 'Refresh Jobs' },
        { key: 'T', desc: 'Toggle Theme' },
        { key: '/', desc: 'Focus Search' },
        { key: 'Ctrl+K', desc: 'Focus Search' },
        { key: 'Esc', desc: 'Close Modals' },
        { key: '?', desc: 'Show This Help' }
    ];

    const helpHtml = shortcuts.map(s =>
        `<div class="shortcut-item"><kbd>${s.key}</kbd><span>${s.desc}</span></div>`
    ).join('');

    showToast('info', '⌨️ Keyboard Shortcuts', `
        <div class="shortcuts-grid">${helpHtml}</div>
    `);
}

/**
 * Toggle algorithm category (for collapsible sections)
 */
export function toggleAlgorithmCategory(categoryId) {
    const content = document.getElementById(categoryId);
    const icon = document.getElementById(`${categoryId}-icon`);

    if (content) {
        content.classList.toggle('expanded');
        if (icon) {
            icon.textContent = content.classList.contains('expanded') ? '▼' : '▶';
        }
    }
}

/**
 * Toggle problem details
 */
export function toggleProblemDetails(problemId) {
    const details = document.getElementById(`${problemId}-details`);
    if (details) {
        details.classList.toggle('expanded');
    }
}

/**
 * Toggle molecule details
 */
export function toggleMoleculeDetails(moleculeId) {
    const details = document.getElementById(`${moleculeId}-molecule`);
    if (details) {
        details.classList.toggle('expanded');
    }
}

// Make functions globally accessible
window.toggleAlgorithmCategory = toggleAlgorithmCategory;
window.toggleProblemDetails = toggleProblemDetails;
window.toggleMoleculeDetails = toggleMoleculeDetails;
