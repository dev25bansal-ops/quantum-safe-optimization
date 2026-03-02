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
    // D-Wave credentials - server-side only (Azure Key Vault)
    const dwaveApiKey = document.getElementById('dwave-api-key');
    if (dwaveApiKey) {
        dwaveApiKey.value = ''; // Never load from localStorage
        dwaveApiKey.addEventListener('change', async (e) => {
            // Send to server for secure storage instead of localStorage
            await saveCredentialToServer('dwave', 'api_token', e.target.value);
        });
    }

    // IBM Quantum token - server-side only (Azure Key Vault)
    const ibmToken = document.getElementById('ibm-quantum-token');
    if (ibmToken) {
        ibmToken.value = ''; // Never load from localStorage
        ibmToken.addEventListener('change', async (e) => {
            // Send to server for secure storage instead of localStorage
            await saveCredentialToServer('ibm', 'api_token', e.target.value);
        });
    }

    // AWS Braket region - server-side only (Azure Key Vault)
    const awsRegion = document.getElementById('aws-braket-region');
    if (awsRegion) {
        awsRegion.value = 'us-east-1'; // Default, never load from localStorage
        awsRegion.addEventListener('change', async (e) => {
            // Send to server for secure storage instead of localStorage
            await saveCredentialToServer('aws', 'region', e.target.value, { region: e.target.value });
        });
    }
}

/**
 * Save a single credential securely to server (Azure Key Vault)
 */
async function saveCredentialToServer(provider, credentialType, value, metadata = null) {
    const token = localStorage.getItem('authToken');
    if (!token) {
        showToast('error', 'Authentication Required', 'Please sign in to save backend credentials');
        return;
    }

    try {
        const response = await fetch('/api/v1/credentials', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                provider: provider,
                credential_type: credentialType,
                value: value,
                metadata: metadata
            })
        });

        if (response.ok) {
            showToast('success', 'Credentials Saved',
                `${provider} ${credentialType} stored securely in Azure Key Vault`);
        } else {
            throw new Error('Failed to save credentials');
        }
    } catch (error) {
        console.error('Failed to save credentials:', error);
        showToast('error', 'Credentials Error', 'Failed to save credentials securely');
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
