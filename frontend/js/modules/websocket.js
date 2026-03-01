/**
 * WebSocket Module
 * Handles real-time job updates via WebSocket
 */

import { CONFIG, STATE } from './config.js';
import { showToast } from './toast.js';
import { addNotification } from './notifications.js';

// WebSocket state
let jobWebSocket = null;
let wsReconnectAttempts = 0;
let wsReconnectTimer = null;
let wsCurrentJobId = null;
const WS_MAX_RECONNECT_ATTEMPTS = 5;
const WS_BASE_RECONNECT_DELAY = 1000; // 1 second

// Callback for updating connectivity UI
let updateConnectivityCallback = null;

export function setConnectivityCallback(callback) {
    updateConnectivityCallback = callback;
}

// Callback for loading jobs after update
let loadJobsCallback = null;
let viewJobDetailsCallback = null;

export function setJobCallbacks(loadJobs, viewDetails) {
    loadJobsCallback = loadJobs;
    viewJobDetailsCallback = viewDetails;
}

/**
 * Connect to WebSocket for job updates
 */
export function connectJobWebSocket(jobId) {
    // Close existing connection and clear reconnect timer
    disconnectJobWebSocket();

    wsCurrentJobId = jobId;
    wsReconnectAttempts = 0;

    createWebSocketConnection(jobId);
}

/**
 * Create WebSocket connection
 */
function createWebSocketConnection(jobId) {
    // Determine WebSocket URL
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/jobs/${jobId}`;

    try {
        jobWebSocket = new WebSocket(wsUrl);

        jobWebSocket.onopen = () => {
            console.log(`[WebSocket] Connected to job ${jobId}`);
            wsReconnectAttempts = 0; // Reset on successful connection
            showToast('info', 'Live Updates', 'Connected to real-time job updates', 2000);
            if (updateConnectivityCallback) {
                updateConnectivityCallback('websocket', 'healthy', null, 'Connected');
            }
        };

        jobWebSocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleJobUpdate(data);
            } catch (e) {
                console.error('[WebSocket] Parse error:', e);
            }
        };

        jobWebSocket.onerror = (error) => {
            console.warn('[WebSocket] Connection error');
        };

        jobWebSocket.onclose = (event) => {
            console.log('[WebSocket] Connection closed', event.code, event.reason);
            jobWebSocket = null;
            if (updateConnectivityCallback) {
                updateConnectivityCallback('websocket', 'degraded', null, 'Disconnected');
            }

            // Don't reconnect if intentionally closed or job completed
            if (event.code === 1000 || !wsCurrentJobId) {
                return;
            }

            // Attempt reconnection with exponential backoff
            if (wsReconnectAttempts < WS_MAX_RECONNECT_ATTEMPTS) {
                wsReconnectAttempts++;
                const delay = WS_BASE_RECONNECT_DELAY * Math.pow(2, wsReconnectAttempts - 1);
                console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${wsReconnectAttempts}/${WS_MAX_RECONNECT_ATTEMPTS})`);

                wsReconnectTimer = setTimeout(() => {
                    if (wsCurrentJobId === jobId) {
                        createWebSocketConnection(jobId);
                    }
                }, delay);
            } else {
                console.warn('[WebSocket] Max reconnection attempts reached, falling back to polling');
                showToast('warning', 'Connection Lost', 'Live updates unavailable. Using periodic refresh.', 4000);
                addNotification('warning', 'WebSocket Disconnected', 'Real-time updates are unavailable');
            }
        };
    } catch (error) {
        console.warn('[WebSocket] Failed to connect:', error);
        if (updateConnectivityCallback) {
            updateConnectivityCallback('websocket', 'unhealthy', null, 'Failed');
        }
    }
}

/**
 * Disconnect WebSocket
 */
export function disconnectJobWebSocket() {
    if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = null;
    }
    if (jobWebSocket) {
        wsCurrentJobId = null; // Prevent reconnection
        jobWebSocket.close(1000, 'Intentional disconnect');
        jobWebSocket = null;
        if (updateConnectivityCallback) {
            updateConnectivityCallback('websocket', 'degraded', null, 'Disconnected');
        }
    }
}

/**
 * Handle job update from WebSocket
 */
function handleJobUpdate(data) {
    // Update progress bar
    const progressBar = document.getElementById('job-progress-bar');
    const progressText = document.getElementById('job-progress-text');

    if (data.progress !== undefined && progressBar) {
        progressBar.style.width = `${data.progress}%`;
    }

    if (data.message && progressText) {
        progressText.textContent = data.message;
    }

    // If job completed or failed, refresh and close WebSocket
    if (data.status === 'completed' || data.status === 'failed') {
        if (jobWebSocket) {
            jobWebSocket.close();
            jobWebSocket = null;
        }

        if (loadJobsCallback) {
            loadJobsCallback().then(() => {
                if (STATE.selectedJobId && viewJobDetailsCallback) {
                    viewJobDetailsCallback(STATE.selectedJobId);
                }
            });
        }

        if (data.status === 'completed') {
            showToast('success', 'Job Completed', 'Your optimization job has finished!');
        } else {
            showToast('error', 'Job Failed', data.error || 'The job encountered an error');
        }
    }
}

/**
 * Get WebSocket connection status
 */
export function getWebSocketStatus() {
    if (jobWebSocket && jobWebSocket.readyState === WebSocket.OPEN) {
        return 'healthy';
    }
    return 'degraded';
}

/**
 * Get WebSocket status label
 */
export function getWebSocketLabel() {
    if (jobWebSocket && jobWebSocket.readyState === WebSocket.OPEN) {
        return 'Connected';
    }
    return 'Idle';
}

// Export WebSocket instance for status checks
export function getWebSocket() {
    return jobWebSocket;
}
