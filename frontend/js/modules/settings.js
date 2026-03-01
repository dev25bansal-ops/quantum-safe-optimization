/**
 * Settings Module
 * Handles application settings management
 */

import { CONFIG, updateConfig } from './config.js';
import { showToast } from './toast.js';

/**
 * Initialize settings handlers
 */
export function initSettings() {
    // Load settings on page load
    loadSettings();

    // API URL change handler
    const apiInput = document.getElementById('api-url');
    if (apiInput) {
        apiInput.addEventListener('change', (e) => {
            const newUrl = e.target.value.trim();
            if (newUrl) {
                localStorage.setItem('apiUrl', newUrl);
                updateConfig('apiUrl', newUrl);
                showToast('info', 'API URL Updated', 'Click "Save Settings" to apply');
            }
        });
    }

    // Auto-refresh toggle
    const autoRefreshToggle = document.getElementById('auto-refresh');
    if (autoRefreshToggle) {
        autoRefreshToggle.addEventListener('change', (e) => {
            localStorage.setItem('autoRefresh', e.target.checked);
        });
    }

    // Notifications toggle
    const notificationsToggle = document.getElementById('enable-notifications');
    if (notificationsToggle) {
        notificationsToggle.addEventListener('change', (e) => {
            localStorage.setItem('enableNotifications', e.target.checked);
            if (e.target.checked && 'Notification' in window) {
                Notification.requestPermission();
            }
        });
    }

    // Debug mode toggle
    const debugToggle = document.getElementById('debug-mode');
    if (debugToggle) {
        debugToggle.addEventListener('change', (e) => {
            localStorage.setItem('debugMode', e.target.checked);
            if (e.target.checked) {
                console.info('[Debug] Debug mode enabled');
            }
        });
    }

    // Save settings button
    document.getElementById('save-settings')?.addEventListener('click', saveSettings);

    // Reset settings button
    document.getElementById('reset-settings')?.addEventListener('click', resetSettings);

    // Backend credential handlers
    initBackendCredentials();
}

/**
 * Load settings from localStorage
 */
function loadSettings() {
    const apiInput = document.getElementById('api-url');
    const autoRefreshToggle = document.getElementById('auto-refresh');
    const notificationsToggle = document.getElementById('enable-notifications');
    const debugToggle = document.getElementById('debug-mode');
    const pageSizeSelect = document.getElementById('page-size');

    if (apiInput) {
        apiInput.value = localStorage.getItem('apiUrl') || CONFIG.apiUrl;
    }

    if (autoRefreshToggle) {
        autoRefreshToggle.checked = localStorage.getItem('autoRefresh') !== 'false';
    }

    if (notificationsToggle) {
        notificationsToggle.checked = localStorage.getItem('enableNotifications') !== 'false';
    }

    if (debugToggle) {
        debugToggle.checked = localStorage.getItem('debugMode') === 'true';
    }

    if (pageSizeSelect) {
        pageSizeSelect.value = localStorage.getItem('pageSize') || '10';
    }
}

/**
 * Save settings to localStorage
 */
function saveSettings() {
    const apiInput = document.getElementById('api-url');
    const autoRefreshToggle = document.getElementById('auto-refresh');
    const notificationsToggle = document.getElementById('enable-notifications');
    const debugToggle = document.getElementById('debug-mode');
    const pageSizeSelect = document.getElementById('page-size');

    if (apiInput?.value) {
        const newUrl = apiInput.value.trim();
        localStorage.setItem('apiUrl', newUrl);
        updateConfig('apiUrl', newUrl);
    }

    if (autoRefreshToggle) {
        localStorage.setItem('autoRefresh', autoRefreshToggle.checked);
    }

    if (notificationsToggle) {
        localStorage.setItem('enableNotifications', notificationsToggle.checked);
    }

    if (debugToggle) {
        localStorage.setItem('debugMode', debugToggle.checked);
    }

    if (pageSizeSelect) {
        localStorage.setItem('pageSize', pageSizeSelect.value);
    }

    showToast('success', 'Settings Saved', 'Your preferences have been saved');
}

/**
 * Reset settings to defaults
 */
function resetSettings() {
    if (!confirm('Are you sure you want to reset all settings to defaults?')) return;

    // Clear settings from localStorage
    localStorage.removeItem('apiUrl');
    localStorage.removeItem('autoRefresh');
    localStorage.removeItem('enableNotifications');
    localStorage.removeItem('debugMode');
    localStorage.removeItem('pageSize');
    localStorage.removeItem('theme');

    // Reload settings UI
    loadSettings();

    // Reset CONFIG
    updateConfig('apiUrl', `${window.location.origin}/api/v1`);

    showToast('info', 'Settings Reset', 'All settings have been reset to defaults');
}

/**
 * Initialize backend credential handlers
 */
function initBackendCredentials() {
    // D-Wave credentials
    const dwaveApiKey = document.getElementById('dwave-api-key');
    if (dwaveApiKey) {
        dwaveApiKey.value = localStorage.getItem('dwaveApiKey') || '';
        dwaveApiKey.addEventListener('change', (e) => {
            localStorage.setItem('dwaveApiKey', e.target.value);
        });
    }

    // IBM Quantum token
    const ibmToken = document.getElementById('ibm-quantum-token');
    if (ibmToken) {
        ibmToken.value = localStorage.getItem('ibmQuantumToken') || '';
        ibmToken.addEventListener('change', (e) => {
            localStorage.setItem('ibmQuantumToken', e.target.value);
        });
    }

    // AWS Braket region
    const awsRegion = document.getElementById('aws-braket-region');
    if (awsRegion) {
        awsRegion.value = localStorage.getItem('awsBraketRegion') || 'us-east-1';
        awsRegion.addEventListener('change', (e) => {
            localStorage.setItem('awsBraketRegion', e.target.value);
        });
    }
}

/**
 * Apply default settings (called on app init if no settings exist)
 */
export function applyDefaultSettings() {
    // Set default page size if not configured
    if (!localStorage.getItem('pageSize')) {
        localStorage.setItem('pageSize', '10');
    }

    // Set default auto-refresh to true
    if (!localStorage.getItem('autoRefresh')) {
        localStorage.setItem('autoRefresh', 'true');
    }

    // Set default notifications to true
    if (!localStorage.getItem('enableNotifications')) {
        localStorage.setItem('enableNotifications', 'true');
    }
}
