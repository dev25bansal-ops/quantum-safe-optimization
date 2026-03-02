/**
 * API Module
 * Centralized API client with error handling and retry logic
 */

import { CONFIG, STATE } from './config.js';
import { getAuthHeaders } from './utils.js';
import { showToast } from './toast.js';

/**
 * Make API request with retry logic
 */
export async function apiRequest(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${CONFIG.apiUrl}${endpoint}`;

    const defaultOptions = {
        headers: getAuthHeaders(),
        ...options
    };

    // Add content-type for POST/PUT/PATCH requests with body
    if (options.body && !defaultOptions.headers['Content-Type']) {
        defaultOptions.headers['Content-Type'] = 'application/json';
    }

    let lastError = null;

    for (let attempt = 1; attempt <= CONFIG.maxRetries; attempt++) {
        try {
            const response = await fetch(url, defaultOptions);

            // Handle 401 specifically
            if (response.status === 401) {
                sessionStorage.removeItem('authToken');
                localStorage.removeItem('authToken');
                STATE.isAuthenticated = false;
                STATE.user = null;
                throw new Error('Session expired. Please sign in again.');
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();

        } catch (error) {
            lastError = error;

            // Don't retry on auth errors or client errors
            if (error.message.includes('Session expired') ||
                error.message.includes('HTTP 4')) {
                throw error;
            }

            // Wait before retrying (exponential backoff)
            if (attempt < CONFIG.maxRetries) {
                await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 100));
            }
        }
    }

    throw lastError || new Error('Request failed after retries');
}

/**
 * GET request helper
 */
export async function apiGet(endpoint) {
    return apiRequest(endpoint, { method: 'GET' });
}

/**
 * POST request helper
 */
export async function apiPost(endpoint, data) {
    return apiRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify(data)
    });
}

/**
 * PUT request helper
 */
export async function apiPut(endpoint, data) {
    return apiRequest(endpoint, {
        method: 'PUT',
        body: JSON.stringify(data)
    });
}

/**
 * DELETE request helper
 */
export async function apiDelete(endpoint) {
    return apiRequest(endpoint, { method: 'DELETE' });
}

/**
 * PATCH request helper
 */
export async function apiPatch(endpoint, data) {
    return apiRequest(endpoint, {
        method: 'PATCH',
        body: JSON.stringify(data)
    });
}

/**
 * Health check
 */
export async function checkHealth() {
    try {
        const response = await fetch(`${CONFIG.apiBase}/health`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        });

        if (response.ok) {
            const data = await response.json();
            STATE.isOnline = true;
            return { healthy: true, ...data };
        }

        return { healthy: false, error: `HTTP ${response.status}` };
    } catch (error) {
        STATE.isOnline = false;
        return { healthy: false, error: error.message };
    }
}

/**
 * Check API availability (simple ping)
 */
export async function pingApi() {
    try {
        const response = await fetch(`${CONFIG.apiBase}/health`, {
            method: 'HEAD',
            cache: 'no-store'
        });
        return response.ok;
    } catch {
        return false;
    }
}
