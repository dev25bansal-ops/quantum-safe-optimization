/**
 * Connectivity Module
 * Handles API health checks and connectivity monitoring
 */

import { CONFIG, STATE } from './config.js';
import { getAuthHeaders, formatDate } from './utils.js';
import { showToast } from './toast.js';
import { getWebSocketStatus, getWebSocketLabel } from './websocket.js';
import { checkHealth, apiGet, pingApi } from './api.js';

// Forward declaration for loadJobs
let loadJobsCallback = null;

export function setConnectivityCallbacks(loadJobs) {
    loadJobsCallback = loadJobs;
}

/**
 * Initialize connectivity monitoring
 */
export function initConnectivity() {
    // Initial connectivity check
    checkApiStatus();

    // Refresh button handler
    document.getElementById('refresh-connectivity')?.addEventListener('click', refreshConnectivity);
}

/**
 * Initialize PQC status display
 */
export function initPqcStatus() {
    // Initial PQC status check
    refreshPqcStatus();

    // Refresh button handler
    document.getElementById('refresh-pqc-status')?.addEventListener('click', refreshPqcStatus);
}

/**
 * Check API health status
 */
export async function checkApiStatus() {
    const statusEl = document.getElementById('api-status');
    const lastCheckEl = document.getElementById('last-check');

    // Update last check time
    if (lastCheckEl) {
        lastCheckEl.textContent = new Date().toLocaleTimeString();
    }

    const startTime = Date.now();
    const result = await checkHealth();
    const latency = Date.now() - startTime;

    if (result.healthy) {
        STATE.isOnline = true;

        // Update overall status
        if (statusEl) {
            statusEl.className = 'status-indicator healthy';
            statusEl.querySelector('.status-text').textContent = 'Healthy';
        }

        // Update individual service statuses
        updateConnectivityItem('api', 'healthy', latency, 'Connected');
        updateConnectivityItem('database', result.database || 'healthy', null, result.database_version || 'Connected');
        updateConnectivityItem('redis', result.redis || 'healthy', null, result.redis_version || 'Connected');

        // WebSocket status
        updateConnectivityItem('websocket', getWebSocketStatus(), null, getWebSocketLabel());

        setOverallHealthBadge('healthy');
    } else {
        console.error('Health check failed:', result.error);
        STATE.isOnline = false;

        if (statusEl) {
            statusEl.className = 'status-indicator unhealthy';
            statusEl.querySelector('.status-text').textContent = 'Offline';
        }

        updateConnectivityItem('api', 'unhealthy', null, 'Unreachable');
        setOverallHealthBadge('unhealthy');
    }
}

/**
 * Update connectivity item display
 */
export function updateConnectivityItem(service, status, latency, label) {
    const item = document.getElementById(`connectivity-${service}`);
    if (!item) return;

    const indicator = item.querySelector('.status-indicator');
    const statusText = item.querySelector('.status-text');
    const latencyText = item.querySelector('.latency-text');

    if (indicator) {
        indicator.className = `status-indicator ${status}`;
    }
    if (statusText) {
        statusText.textContent = label || status;
    }
    if (latencyText && latency !== null) {
        latencyText.textContent = `${latency}ms`;
    }
}

/**
 * Set overall health badge
 */
export function setOverallHealthBadge(status) {
    const badge = document.getElementById('overall-health-badge');
    if (badge) {
        badge.className = `health-badge ${status}`;
        const text = badge.querySelector('.badge-text');
        if (text) {
            text.textContent = status === 'healthy' ? 'All Systems Operational' :
                status === 'degraded' ? 'Partial Degradation' : 'Service Disruption';
        }
    }
}

/**
 * Refresh connectivity status
 */
export async function refreshConnectivity() {
    const refreshBtn = document.getElementById('refresh-connectivity');
    if (refreshBtn) {
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    }

    await checkApiStatus();

    if (refreshBtn) {
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i>';
    }

    showToast('info', 'Refreshed', 'Connectivity status updated');
}

/**
 * Refresh PQC status
 */
export async function refreshPqcStatus() {
    const container = document.getElementById('pqc-status-grid');
    if (!container) return;

    try {
        const data = await apiGet('/security/pqc/status');
        updatePqcStatusDisplay(data);
    } catch (error) {
        // Show demo data for authenticated demo users or on network error
        if (error.message.includes('Session expired') || error.message.includes('401') ||
            error.message.includes('Failed to fetch') || error.name === 'TypeError') {
            if (STATE.isAuthenticated) {
                updatePqcStatusDisplay(getDemoPqcStatus());
            } else {
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-lock"></i>
                        <p>Sign in to view PQC status</p>
                    </div>
                `;
            }
        } else {
            console.error('Failed to load PQC status:', error);
        }
    }
}

/**
 * Update PQC status display
 */
function updatePqcStatusDisplay(data) {
    const kemStatus = document.getElementById('mlkem-status');
    const dsaStatus = document.getElementById('mldsa-status');
    const cipherStatus = document.getElementById('cipher-status');

    if (kemStatus) {
        kemStatus.className = `pqc-status-item ${data.kem?.enabled ? 'active' : 'inactive'}`;
        kemStatus.querySelector('.algo-name').textContent = data.kem?.algorithm || 'ML-KEM-768';
        kemStatus.querySelector('.algo-status').textContent = data.kem?.enabled ? 'Active' : 'Inactive';
    }

    if (dsaStatus) {
        dsaStatus.className = `pqc-status-item ${data.dsa?.enabled ? 'active' : 'inactive'}`;
        dsaStatus.querySelector('.algo-name').textContent = data.dsa?.algorithm || 'ML-DSA-65';
        dsaStatus.querySelector('.algo-status').textContent = data.dsa?.enabled ? 'Active' : 'Inactive';
    }

    if (cipherStatus) {
        cipherStatus.className = `pqc-status-item ${data.cipher?.enabled ? 'active' : 'inactive'}`;
        cipherStatus.querySelector('.algo-name').textContent = data.cipher?.algorithm || 'AES-256-GCM';
        cipherStatus.querySelector('.algo-status').textContent = data.cipher?.enabled ? 'Active' : 'Inactive';
    }
}

/**
 * Get demo PQC status
 */
function getDemoPqcStatus() {
    return {
        kem: { algorithm: 'ML-KEM-768', enabled: true },
        dsa: { algorithm: 'ML-DSA-65', enabled: true },
        cipher: { algorithm: 'AES-256-GCM', enabled: true }
    };
}

/**
 * Update backend status indicators
 */
export function updateBackendStatus(backendName, status) {
    const indicator = document.querySelector(`[data-backend="${backendName}"] .status-dot`);
    if (indicator) {
        indicator.className = `status-dot ${status}`;
    }
}

/**
 * Initialize offline detection
 */
export function initOfflineDetection() {
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Initial check
    if (!navigator.onLine) {
        handleOffline();
    }
}

/**
 * Handle offline event
 */
function handleOffline() {
    STATE.wasOffline = true;
    const banner = document.getElementById('offline-banner');
    const statusText = document.getElementById('offline-status');

    if (banner) {
        banner.style.display = 'flex';
        if (statusText) statusText.textContent = 'Waiting for connection...';
    }

    showToast('warning', 'Offline', 'You are currently offline');
}

/**
 * Handle online event
 */
function handleOnline() {
    const banner = document.getElementById('offline-banner');
    const statusText = document.getElementById('offline-status');

    if (banner) {
        if (statusText) statusText.textContent = 'Reconnected!';
        setTimeout(() => {
            banner.style.display = 'none';
        }, 2000);
    }

    if (STATE.wasOffline) {
        showToast('success', 'Back Online', 'Connection restored');
        STATE.wasOffline = false;
        if (loadJobsCallback) loadJobsCallback(true);
    }
}

/**
 * Manual connection check
 */
export async function checkConnection() {
    const statusText = document.getElementById('offline-status');
    if (statusText) statusText.textContent = 'Checking...';

    const isOnline = await pingApi();
    if (isOnline) {
        handleOnline();
    } else {
        if (statusText) statusText.textContent = 'Still offline...';
    }
}

// Make functions globally accessible
window.checkApiStatus = checkApiStatus;
window.refreshConnectivity = refreshConnectivity;
window.refreshPqcStatus = refreshPqcStatus;
window.checkConnection = checkConnection;
