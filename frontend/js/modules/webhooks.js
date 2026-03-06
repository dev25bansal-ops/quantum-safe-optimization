/**
 * Enhanced Webhooks Module
 * Handles webhook statistics, history/logs viewer, HMAC signature verification
 */

import { CONFIG, STATE } from './config.js';
import { escapeHtml, formatDate, formatTimeShort, getAuthHeaders } from './utils.js';
import { apiGet, apiPost, apiDelete } from './api.js';
import { showToast } from './toast.js';

let webhookState = {
    history: [],
    selectedWebhook: null,
    filters: {
        status: 'all',
        event: 'all',
        dateRange: '7d'
    }
};

const WEBHOOK_EVENTS = [
    'job.submitted',
    'job.started',
    'job.completed',
    'job.failed',
    'job.cancelled',
    'job.progress',
    'key.generated',
    'key.rotated',
    'key.revoked'
];

/**
 * Initialize webhook management UI
 */
export function initWebhookManagement() {
    const container = document.getElementById('webhook-management-section');
    if (!container) return;

    renderWebhookManagementUI(container);
    loadWebhookStats();
    loadWebhookHistory();
    bindWebhookEvents();
}

/**
 * Render webhook management UI
 */
function renderWebhookManagementUI(container) {
    container.innerHTML = `
        <div class="webhook-management">
            <!-- Webhook Configuration -->
            <div class="webhook-config-section">
                <div class="card">
                    <div class="card-header">
                        <h3><i class="fas fa-plug"></i> Webhook Configuration</h3>
                    </div>
                    <div class="card-body">
                        <div class="form-group">
                            <label for="webhook-url-input">Callback URL</label>
                            <input type="url" id="webhook-url-input" class="form-input" 
                                   placeholder="https://your-server.com/webhooks/quantum">
                        </div>
                        
                        <div class="form-group">
                            <label>Event Subscriptions</label>
                            <div class="event-checkboxes">
                                ${WEBHOOK_EVENTS.map(event => `
                                    <label class="checkbox-inline">
                                        <input type="checkbox" name="webhook-events" value="${event}" checked>
                                        <span>${event}</span>
                                    </label>
                                `).join('')}
                            </div>
                        </div>

                        <div class="form-group">
                            <label for="webhook-secret">HMAC Secret (Optional)</label>
                            <div class="input-group">
                                <input type="password" id="webhook-secret" class="form-input" 
                                       placeholder="Enter secret for HMAC signature">
                                <button class="btn btn-ghost" onclick="window.generateWebhookSecret()">
                                    <i class="fas fa-key"></i> Generate
                                </button>
                            </div>
                            <small class="form-hint">Secret used to sign webhook payloads with HMAC-SHA256</small>
                        </div>

                        <div class="form-group">
                            <label for="webhook-timeout">Timeout (seconds)</label>
                            <input type="number" id="webhook-timeout" class="form-input" value="30" min="5" max="120">
                        </div>

                        <div class="form-actions">
                            <button class="btn btn-primary" onclick="window.saveWebhookConfig()">
                                <i class="fas fa-save"></i> Save Configuration
                            </button>
                            <button class="btn btn-ghost" onclick="window.testWebhook()">
                                <i class="fas fa-paper-plane"></i> Send Test
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Webhook Statistics -->
            <div class="webhook-stats-section">
                <div class="card">
                    <div class="card-header">
                        <h3><i class="fas fa-chart-bar"></i> Delivery Statistics</h3>
                        <span class="stats-period">Last 7 days</span>
                    </div>
                    <div class="card-body">
                        <div id="webhook-stats-grid" class="webhook-stats-grid">
                            <!-- Filled by loadWebhookStats -->
                        </div>
                    </div>
                </div>
            </div>

            <!-- HMAC Signature Display -->
            <div class="hmac-section" id="hmac-section" style="display: none;">
                <div class="card">
                    <div class="card-header">
                        <h3><i class="fas fa-shield-alt"></i> HMAC Signature Verification</h3>
                    </div>
                    <div class="card-body">
                        <div class="hmac-info">
                            <p>Each webhook delivery includes an <code>X-HMAC-Signature</code> header containing a SHA256 HMAC signature of the payload.</p>
                        </div>
                        <div class="hmac-verification">
                            <div class="form-group">
                                <label for="hmac-payload">Payload to Verify</label>
                                <textarea id="hmac-payload" class="form-textarea" rows="4" 
                                          placeholder="Paste webhook payload JSON here"></textarea>
                            </div>
                            <div class="form-group">
                                <label for="hmac-signature">Signature (from header)</label>
                                <input type="text" id="hmac-signature" class="form-input" 
                                       placeholder="sha256=...">
                            </div>
                            <div class="form-group">
                                <label for="hmac-secret-verify">Your Secret</label>
                                <input type="password" id="hmac-secret-verify" class="form-input" 
                                       placeholder="Enter your webhook secret">
                            </div>
                            <button class="btn btn-primary" onclick="window.verifyHMACSignature()">
                                <i class="fas fa-check-circle"></i> Verify Signature
                            </button>
                            <div id="hmac-result" class="hmac-result" style="display: none;"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Webhook History/Logs -->
            <div class="webhook-history-section">
                <div class="card">
                    <div class="card-header">
                        <h3><i class="fas fa-history"></i> Delivery History</h3>
                        <div class="history-actions">
                            <button class="btn btn-ghost btn-sm" onclick="window.exportWebhookLogs()">
                                <i class="fas fa-download"></i> Export
                            </button>
                            <button class="btn btn-ghost btn-sm" onclick="window.refreshWebhookHistory()">
                                <i class="fas fa-sync"></i>
                            </button>
                        </div>
                    </div>
                    <div class="card-body">
                        <!-- Filters -->
                        <div class="history-filters">
                            <select id="webhook-status-filter" class="form-select" onchange="window.filterWebhookHistory()">
                                <option value="all">All Statuses</option>
                                <option value="success">Delivered</option>
                                <option value="failed">Failed</option>
                                <option value="pending">Pending</option>
                            </select>
                            <select id="webhook-event-filter" class="form-select" onchange="window.filterWebhookHistory()">
                                <option value="all">All Events</option>
                                ${WEBHOOK_EVENTS.map(e => `<option value="${e}">${e}</option>`).join('')}
                            </select>
                            <select id="webhook-date-filter" class="form-select" onchange="window.filterWebhookHistory()">
                                <option value="24h">Last 24 hours</option>
                                <option value="7d" selected>Last 7 days</option>
                                <option value="30d">Last 30 days</option>
                                <option value="all">All time</option>
                            </select>
                        </div>

                        <!-- History Table -->
                        <div class="webhook-history-table">
                            <table class="data-table">
                                <thead>
                                    <tr>
                                        <th>Timestamp</th>
                                        <th>Event</th>
                                        <th>URL</th>
                                        <th>Status</th>
                                        <th>Response Time</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="webhook-history-body">
                                    <!-- Filled dynamically -->
                                </tbody>
                            </table>
                        </div>

                        <!-- Pagination -->
                        <div class="history-pagination" id="webhook-pagination">
                            <!-- Filled dynamically -->
                        </div>
                    </div>
                </div>
            </div>

            <!-- Webhook Detail Modal -->
            <div id="webhook-detail-modal" class="modal">
                <div class="modal-content modal-lg">
                    <div class="modal-header">
                        <h3><i class="fas fa-info-circle"></i> Webhook Delivery Details</h3>
                        <button class="modal-close" onclick="window.closeWebhookModal()">&times;</button>
                    </div>
                    <div class="modal-body" id="webhook-detail-body">
                        <!-- Filled dynamically -->
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-ghost" onclick="window.redeliverWebhook()">
                            <i class="fas fa-redo"></i> Redeliver
                        </button>
                        <button class="btn btn-secondary" onclick="window.closeWebhookModal()">Close</button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Load webhook statistics
 */
export async function loadWebhookStats() {
    const statsGrid = document.getElementById('webhook-stats-grid');
    if (!statsGrid) return;

    try {
        let data;
        try {
            data = await apiGet('/webhooks/stats');
        } catch (error) {
            if (STATE.isAuthenticated) {
                data = getDemoWebhookStats();
            } else {
                statsGrid.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-lock"></i>
                        <p>Sign in to view webhook statistics</p>
                    </div>
                `;
                return;
            }
        }

        STATE.webhookStats = data;

        const successRate = data.total > 0 ? ((data.successful / data.total) * 100).toFixed(1) : 0;

        statsGrid.innerHTML = `
            <div class="webhook-stat-card">
                <div class="stat-icon blue">
                    <i class="fas fa-paper-plane"></i>
                </div>
                <div class="stat-info">
                    <span class="stat-value">${data.total || 0}</span>
                    <span class="stat-label">Total Sent</span>
                </div>
            </div>
            <div class="webhook-stat-card">
                <div class="stat-icon green">
                    <i class="fas fa-check-circle"></i>
                </div>
                <div class="stat-info">
                    <span class="stat-value">${data.successful || 0}</span>
                    <span class="stat-label">Delivered</span>
                </div>
            </div>
            <div class="webhook-stat-card">
                <div class="stat-icon red">
                    <i class="fas fa-times-circle"></i>
                </div>
                <div class="stat-info">
                    <span class="stat-value">${data.failed || 0}</span>
                    <span class="stat-label">Failed</span>
                </div>
            </div>
            <div class="webhook-stat-card">
                <div class="stat-icon yellow">
                    <i class="fas fa-clock"></i>
                </div>
                <div class="stat-info">
                    <span class="stat-value">${data.pending || 0}</span>
                    <span class="stat-label">Pending</span>
                </div>
            </div>
            <div class="webhook-stat-card highlight">
                <div class="stat-icon purple">
                    <i class="fas fa-percentage"></i>
                </div>
                <div class="stat-info">
                    <span class="stat-value">${successRate}%</span>
                    <span class="stat-label">Success Rate</span>
                </div>
            </div>
            <div class="webhook-stat-card">
                <div class="stat-icon info">
                    <i class="fas fa-tachometer-alt"></i>
                </div>
                <div class="stat-info">
                    <span class="stat-value">${data.avg_response_time ? `${data.avg_response_time}ms` : '-'}</span>
                    <span class="stat-label">Avg Response</span>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Failed to load webhook stats:', error);
    }
}

/**
 * Load webhook delivery history
 */
export async function loadWebhookHistory() {
    const tbody = document.getElementById('webhook-history-body');
    if (!tbody) return;

    try {
        let history;
        try {
            const params = new URLSearchParams({
                status: webhookState.filters.status,
                event: webhookState.filters.event,
                range: webhookState.filters.dateRange
            });
            history = await apiGet(`/webhooks/history?${params}`);
        } catch (error) {
            history = getDemoWebhookHistory();
        }

        webhookState.history = history;

        if (history.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-row">
                        <div class="empty-state">
                            <i class="fas fa-inbox"></i>
                            <p>No webhook deliveries found</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = history.map(delivery => `
            <tr class="webhook-row ${delivery.success ? 'success' : 'failed'}" 
                onclick="window.viewWebhookDetail('${delivery.id}')">
                <td>
                    <span class="timestamp">${formatDate(delivery.timestamp)}</span>
                    <span class="time">${formatTimeShort(delivery.timestamp)}</span>
                </td>
                <td>
                    <span class="event-badge ${delivery.event.split('.')[0]}">${escapeHtml(delivery.event)}</span>
                </td>
                <td>
                    <span class="url-cell" title="${escapeHtml(delivery.url)}">
                        ${escapeHtml(delivery.url.length > 40 ? delivery.url.substring(0, 40) + '...' : delivery.url)}
                    </span>
                </td>
                <td>
                    <span class="status-badge ${delivery.success ? 'delivered' : 'failed'}">
                        ${delivery.success ? '✓ Delivered' : '✗ Failed'}
                    </span>
                    ${delivery.status_code ? `<span class="status-code">(${delivery.status_code})</span>` : ''}
                </td>
                <td>
                    <span class="response-time">${delivery.response_time ? `${delivery.response_time}ms` : '-'}</span>
                </td>
                <td>
                    <button class="btn btn-ghost btn-xs" onclick="event.stopPropagation(); window.viewWebhookDetail('${delivery.id}')">
                        <i class="fas fa-eye"></i>
                    </button>
                    ${!delivery.success ? `
                        <button class="btn btn-ghost btn-xs" onclick="event.stopPropagation(); window.redeliverWebhook('${delivery.id}')">
                            <i class="fas fa-redo"></i>
                        </button>
                    ` : ''}
                </td>
            </tr>
        `).join('');

        // Show HMAC section if configured
        const hmacSection = document.getElementById('hmac-section');
        if (hmacSection && STATE.webhookConfig?.secret) {
            hmacSection.style.display = 'block';
        }

    } catch (error) {
        console.error('Failed to load webhook history:', error);
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-row">
                    <div class="empty-state error-state">
                        <i class="fas fa-exclamation-triangle"></i>
                        <p>Failed to load webhook history</p>
                        <button class="btn btn-outline btn-sm" onclick="window.refreshWebhookHistory()">Retry</button>
                    </div>
                </td>
            </tr>
        `;
    }
}

/**
 * View webhook delivery detail
 */
function viewWebhookDetail(deliveryId) {
    const delivery = webhookState.history.find(d => d.id === deliveryId);
    if (!delivery) return;

    webhookState.selectedWebhook = delivery;
    const modal = document.getElementById('webhook-detail-modal');
    const body = document.getElementById('webhook-detail-body');

    body.innerHTML = `
        <div class="webhook-detail">
            <div class="detail-header">
                <div class="detail-status ${delivery.success ? 'success' : 'failed'}">
                    <i class="fas ${delivery.success ? 'fa-check-circle' : 'fa-times-circle'}"></i>
                    <span>${delivery.success ? 'Delivered Successfully' : 'Delivery Failed'}</span>
                </div>
                <div class="detail-timestamp">${formatDate(delivery.timestamp)} at ${formatTimeShort(delivery.timestamp)}</div>
            </div>

            <div class="detail-sections">
                <div class="detail-section">
                    <h4><i class="fas fa-info-circle"></i> Request Information</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="label">Event</span>
                            <span class="value">${escapeHtml(delivery.event)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">URL</span>
                            <span class="value url">${escapeHtml(delivery.url)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Method</span>
                            <span class="value">POST</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Attempt</span>
                            <span class="value">${delivery.attempt || 1}/${delivery.max_attempts || 3}</span>
                        </div>
                    </div>
                </div>

                <div class="detail-section">
                    <h4><i class="fas fa-shield-alt"></i> HMAC Signature</h4>
                    <div class="hmac-display">
                        <code class="hmac-value">${delivery.hmac_signature || 'N/A'}</code>
                        <button class="btn btn-ghost btn-xs" onclick="window.copyHMACSignature()">
                            <i class="fas fa-copy"></i>
                        </button>
                    </div>
                </div>

                <div class="detail-section">
                    <h4><i class="fas fa-code"></i> Request Headers</h4>
                    <pre class="code-block">${JSON.stringify(delivery.headers || {
                        'Content-Type': 'application/json',
                        'X-Event-Type': delivery.event,
                        'X-Delivery-ID': delivery.id,
                        'X-HMAC-Signature': delivery.hmac_signature || 'sha256=...'
                    }, null, 2)}</pre>
                </div>

                <div class="detail-section">
                    <h4><i class="fas fa-file-code"></i> Request Payload</h4>
                    <pre class="code-block payload">${JSON.stringify(delivery.payload || {
                        event: delivery.event,
                        timestamp: delivery.timestamp,
                        data: { job_id: '...', status: '...' }
                    }, null, 2)}</pre>
                </div>

                <div class="detail-section">
                    <h4><i class="fas fa-server"></i> Response</h4>
                    <div class="response-info">
                        <div class="response-status">
                            <span class="label">Status Code:</span>
                            <span class="status-code-badge ${delivery.success ? 'success' : 'error'}">
                                ${delivery.status_code || 'N/A'}
                            </span>
                        </div>
                        <div class="response-time">
                            <span class="label">Response Time:</span>
                            <span>${delivery.response_time ? `${delivery.response_time}ms` : 'N/A'}</span>
                        </div>
                    </div>
                    ${delivery.response_body ? `
                        <pre class="code-block response">${escapeHtml(delivery.response_body.substring(0, 500))}${delivery.response_body.length > 500 ? '...' : ''}</pre>
                    ` : ''}
                </div>

                ${delivery.error ? `
                    <div class="detail-section error-section">
                        <h4><i class="fas fa-exclamation-triangle"></i> Error Details</h4>
                        <div class="error-message">${escapeHtml(delivery.error)}</div>
                    </div>
                ` : ''}
            </div>
        </div>
    `;

    modal.classList.add('active');
}

/**
 * Generate webhook secret
 */
function generateWebhookSecret() {
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    const secret = Array.from(array, b => b.toString(16).padStart(2, '0')).join('');
    
    const secretInput = document.getElementById('webhook-secret');
    if (secretInput) {
        secretInput.value = secret;
        secretInput.type = 'text';
        setTimeout(() => { secretInput.type = 'password'; }, 5000);
    }
    
    showToast('success', 'Secret Generated', 'Store this secret securely - it won\'t be shown again');
}

/**
 * Verify HMAC signature
 */
async function verifyHMACSignature() {
    const payload = document.getElementById('hmac-payload')?.value;
    const signature = document.getElementById('hmac-signature')?.value;
    const secret = document.getElementById('hmac-secret-verify')?.value;
    const resultEl = document.getElementById('hmac-result');

    if (!payload || !signature || !secret) {
        showToast('error', 'Missing Fields', 'Please fill in all fields to verify');
        return;
    }

    try {
        const encoder = new TextEncoder();
        const key = await crypto.subtle.importKey(
            'raw',
            encoder.encode(secret),
            { name: 'HMAC', hash: 'SHA-256' },
            false,
            ['sign']
        );

        const signatureBuffer = await crypto.subtle.sign(
            'HMAC',
            key,
            encoder.encode(payload)
        );

        const expectedSignature = 'sha256=' + Array.from(new Uint8Array(signatureBuffer))
            .map(b => b.toString(16).padStart(2, '0'))
            .join('');

        const isValid = signature === expectedSignature;

        resultEl.style.display = 'block';
        resultEl.className = `hmac-result ${isValid ? 'valid' : 'invalid'}`;
        resultEl.innerHTML = `
            <i class="fas ${isValid ? 'fa-check-circle' : 'fa-times-circle'}"></i>
            <span>${isValid ? 'Signature is valid!' : 'Signature verification failed'}</span>
            ${!isValid ? `
                <div class="expected-sig">
                    <span>Expected:</span>
                    <code>${expectedSignature}</code>
                </div>
            ` : ''}
        `;

        showToast(isValid ? 'success' : 'error', 
            isValid ? 'Valid Signature' : 'Invalid Signature',
            isValid ? 'The HMAC signature matches' : 'Signature does not match the payload');
    } catch (error) {
        console.error('HMAC verification error:', error);
        showToast('error', 'Verification Error', 'Failed to verify signature');
    }
}

/**
 * Save webhook configuration
 */
async function saveWebhookConfig() {
    const url = document.getElementById('webhook-url-input')?.value;
    const secret = document.getElementById('webhook-secret')?.value;
    const timeout = document.getElementById('webhook-timeout')?.value;
    const events = Array.from(document.querySelectorAll('input[name="webhook-events"]:checked'))
        .map(cb => cb.value);

    if (!url) {
        showToast('error', 'URL Required', 'Please enter a webhook URL');
        return;
    }

    try {
        await apiPost('/webhooks/config', {
            url,
            secret,
            timeout: parseInt(timeout) || 30,
            events
        });

        showToast('success', 'Configuration Saved', 'Webhook configuration updated');
        
        const hmacSection = document.getElementById('hmac-section');
        if (hmacSection) {
            hmacSection.style.display = secret ? 'block' : 'none';
        }
    } catch (error) {
        showToast('error', 'Save Failed', error.message || 'Failed to save configuration');
    }
}

/**
 * Send test webhook
 */
async function testWebhook() {
    try {
        await apiPost('/webhooks/test', {});
        showToast('success', 'Test Sent', 'Test webhook delivery initiated');
    } catch (error) {
        showToast('error', 'Test Failed', error.message || 'Failed to send test webhook');
    }
}

/**
 * Redeliver webhook
 */
async function redeliverWebhook(deliveryId) {
    const id = deliveryId || webhookState.selectedWebhook?.id;
    if (!id) return;

    try {
        await apiPost(`/webhooks/${id}/redeliver`, {});
        showToast('success', 'Redelivery Initiated', 'Webhook will be redelivered shortly');
        loadWebhookHistory();
    } catch (error) {
        showToast('error', 'Redelivery Failed', error.message || 'Failed to redeliver webhook');
    }
}

/**
 * Close webhook modal
 */
function closeWebhookModal() {
    const modal = document.getElementById('webhook-detail-modal');
    if (modal) modal.classList.remove('active');
}

/**
 * Filter webhook history
 */
function filterWebhookHistory() {
    webhookState.filters.status = document.getElementById('webhook-status-filter')?.value || 'all';
    webhookState.filters.event = document.getElementById('webhook-event-filter')?.value || 'all';
    webhookState.filters.dateRange = document.getElementById('webhook-date-filter')?.value || '7d';
    loadWebhookHistory();
}

/**
 * Export webhook logs
 */
async function exportWebhookLogs() {
    try {
        const data = await apiGet('/webhooks/export?format=json');
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `webhook-logs-${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
        showToast('success', 'Export Complete', 'Webhook logs downloaded');
    } catch (error) {
        showToast('error', 'Export Failed', 'Failed to export webhook logs');
    }
}

/**
 * Bind event handlers
 */
function bindWebhookEvents() {
    // Additional bindings if needed
}

/**
 * Demo data generators
 */
function getDemoWebhookStats() {
    return {
        total: 156,
        successful: 148,
        failed: 5,
        pending: 3,
        avg_response_time: 234
    };
}

function getDemoWebhookHistory() {
    const now = Date.now();
    return [
        { id: 'wh_001', event: 'job.completed', url: 'https://api.example.com/webhooks', success: true, timestamp: new Date(now - 300000).toISOString(), status_code: 200, response_time: 145, hmac_signature: 'sha256=a1b2c3...' },
        { id: 'wh_002', event: 'job.started', url: 'https://api.example.com/webhooks', success: true, timestamp: new Date(now - 600000).toISOString(), status_code: 200, response_time: 89 },
        { id: 'wh_003', event: 'job.failed', url: 'https://api.example.com/webhooks', success: false, timestamp: new Date(now - 900000).toISOString(), status_code: 500, error: 'Internal Server Error', response_time: 234 },
        { id: 'wh_004', event: 'job.completed', url: 'https://hooks.slack.com/quantum', success: true, timestamp: new Date(now - 1200000).toISOString(), status_code: 200, response_time: 312 },
        { id: 'wh_005', event: 'key.generated', url: 'https://api.example.com/webhooks', success: true, timestamp: new Date(now - 1800000).toISOString(), status_code: 200, response_time: 67 }
    ];
}

// Global exports
window.loadWebhookStats = loadWebhookStats;
window.loadWebhookHistory = loadWebhookHistory;
window.refreshWebhookHistory = loadWebhookHistory;
window.viewWebhookDetail = viewWebhookDetail;
window.closeWebhookModal = closeWebhookModal;
window.redeliverWebhook = redeliverWebhook;
window.generateWebhookSecret = generateWebhookSecret;
window.verifyHMACSignature = verifyHMACSignature;
window.saveWebhookConfig = saveWebhookConfig;
window.testWebhook = testWebhook;
window.filterWebhookHistory = filterWebhookHistory;
window.exportWebhookLogs = exportWebhookLogs;
window.copyHMACSignature = () => {
    if (webhookState.selectedWebhook?.hmac_signature) {
        navigator.clipboard.writeText(webhookState.selectedWebhook.hmac_signature);
        showToast('success', 'Copied', 'HMAC signature copied to clipboard');
    }
};
