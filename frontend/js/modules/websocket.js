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

// Activity feed callbacks
let activityFeedCallbacks = [];

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
* Register activity feed callback
*/
export function registerActivityCallback(callback) {
activityFeedCallbacks.push(callback);
}

/**
* Unregister activity feed callback
*/
export function unregisterActivityCallback(callback) {
activityFeedCallbacks = activityFeedCallbacks.filter(cb => cb !== callback);
}

/**
* Notify all activity callbacks
*/
function notifyActivityCallbacks(activity) {
activityFeedCallbacks.forEach(callback => {
try {
callback(activity);
} catch (e) {
console.error('[WebSocket] Activity callback error:', e);
}
});
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

// Add to activity feed
addActivityItem({
type: 'system',
title: 'WebSocket Connected',
description: `Live updates enabled for job ${jobId.substring(0, 8)}...`,
timestamp: new Date().toISOString()
});
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

addActivityItem({
type: 'system',
title: 'WebSocket Disconnected',
description: 'Max reconnection attempts reached',
timestamp: new Date().toISOString()
});
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

// Add progress to activity feed
if (data.progress !== undefined || data.message) {
addActivityItem({
type: 'job',
title: `Job Progress: ${data.progress || 0}%`,
description: data.message || 'Processing...',
timestamp: new Date().toISOString()
});
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
addActivityItem({
type: 'job',
title: 'Job Completed',
description: `Job ${wsCurrentJobId?.substring(0, 8) || 'unknown'} finished successfully`,
timestamp: new Date().toISOString()
});
} else {
showToast('error', 'Job Failed', data.error || 'The job encountered an error');
addActivityItem({
type: 'job',
title: 'Job Failed',
description: data.error || 'Unknown error',
timestamp: new Date().toISOString()
});
}
}
}

/**
* Add item to activity feed
*/
function addActivityItem(activity) {
// Add to STATE if available
if (STATE && Array.isArray(STATE.activity)) {
STATE.activity.unshift(activity);
// Keep only last 50 items
if (STATE.activity.length > 50) {
STATE.activity = STATE.activity.slice(0, 50);
}
}

// Notify all registered callbacks
notifyActivityCallbacks(activity);

// Update activity feed UI if visible
updateActivityFeedUI(activity);
}

/**
* Update activity feed UI
*/
function updateActivityFeedUI(activity) {
const feedEl = document.getElementById('activity-feed');
if (!feedEl) return;

// Remove empty state if exists
const emptyState = feedEl.querySelector('.activity-empty, .activity-loading, .empty-state');
if (emptyState) {
emptyState.remove();
}

// Create new activity item
const item = document.createElement('div');
item.className = `activity-item ${activity.type}`;
item.innerHTML = `
<div class="activity-icon">
<i class="fas ${getActivityIcon(activity.type)}"></i>
</div>
<div class="activity-content">
<span class="activity-title">${escapeHtml(activity.title)}</span>
<span class="activity-description">${escapeHtml(activity.description)}</span>
<span class="activity-time">${formatRelativeTime(activity.timestamp)}</span>
</div>
`;

// Add to beginning
feedEl.insertBefore(item, feedEl.firstChild);

// Keep only 20 visible items
const items = feedEl.querySelectorAll('.activity-item');
if (items.length > 20) {
items[items.length - 1].remove();
}
}

/**
* Get icon for activity type
*/
function getActivityIcon(type) {
const icons = {
job: 'fa-tasks',
key: 'fa-key',
system: 'fa-server',
webhook: 'fa-bolt',
user: 'fa-user'
};
return icons[type] || 'fa-circle';
}

/**
* Format relative time
*/
function formatRelativeTime(timestamp) {
const date = new Date(timestamp);
const now = new Date();
const diff = now - date;
const mins = Math.floor(diff / 60000);
const hours = Math.floor(diff / 3600000);

if (mins < 1) return 'Just now';
if (mins < 60) return `${mins}m ago`;
if (hours < 24) return `${hours}h ago`;
return date.toLocaleDateString();
}

/**
* Escape HTML
*/
function escapeHtml(text) {
if (!text) return '';
const div = document.createElement('div');
div.textContent = text;
return div.innerHTML;
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

/**
* Get recent activity
*/
export function getRecentActivity(limit = 10) {
return STATE?.activity?.slice(0, limit) || [];
}

// Make functions globally accessible
window.addActivityItem = addActivityItem;
window.getRecentActivity = getRecentActivity;
