/**
 * Key Management Module
 * Handles ML-KEM key generation, viewing, rotation, and revocation
 */

import { showToast } from './toast.js';
import { apiGet, apiPost, apiDelete } from './api.js';
import { STATE } from './config.js';
import { formatDate, formatTimeShort } from './utils.js';

let keyState = {
    keys: [],
    selectedKey: null,
    generating: false
};

/**
 * Initialize key management UI
 */
export function initKeyManagement() {
    const container = document.getElementById('key-management-section');
    if (!container) return;

    renderKeyManagementUI(container);
    loadKeys();
}

/**
 * Render key management UI
 */
function renderKeyManagementUI(container) {
    container.innerHTML = `
        <div class="key-management-panel">
            <!-- Key Status Overview -->
            <div class="key-status-overview">
                <div class="status-card">
                    <div class="status-icon active">
                        <i class="fas fa-key"></i>
                    </div>
                    <div class="status-info">
                        <span class="status-value" id="active-keys-count">0</span>
                        <span class="status-label">Active Keys</span>
                    </div>
                </div>
                <div class="status-card">
                    <div class="status-icon warning">
                        <i class="fas fa-clock"></i>
                    </div>
                    <div class="status-info">
                        <span class="status-value" id="expiring-keys-count">0</span>
                        <span class="status-label">Expiring Soon</span>
                    </div>
                </div>
                <div class="status-card">
                    <div class="status-icon info">
                        <i class="fas fa-rotate"></i>
                    </div>
                    <div class="status-info">
                        <span class="status-value" id="last-rotation">-</span>
                        <span class="status-label">Last Rotation</span>
                    </div>
                </div>
            </div>

            <!-- Key Generation -->
            <div class="key-generation-section">
                <div class="card">
                    <div class="card-header">
                        <h4><i class="fas fa-plus-circle"></i> Generate New Key</h4>
                    </div>
                    <div class="card-body">
                        <div class="form-grid">
                            <div class="form-group">
                                <label for="key-algorithm">Algorithm</label>
                                <select id="key-algorithm" class="form-select">
                                    <option value="ML-KEM-768">ML-KEM-768 (NIST Level 3)</option>
                                    <option value="ML-KEM-512">ML-KEM-512 (NIST Level 1)</option>
                                    <option value="ML-KEM-1024">ML-KEM-1024 (NIST Level 5)</option>
                                    <option value="ML-DSA-65">ML-DSA-65 (Signatures)</option>
                                    <option value="ML-DSA-44">ML-DSA-44 (Signatures)</option>
                                    <option value="ML-DSA-87">ML-DSA-87 (Signatures)</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="key-label">Label (Optional)</label>
                                <input type="text" id="key-label" class="form-input" 
                                       placeholder="e.g., Production Key 2024">
                            </div>
                        </div>

                        <div class="key-options">
                            <label class="checkbox">
                                <input type="checkbox" id="key-auto-rotate">
                                <span class="checkmark"></span>
                                <div class="checkbox-label">
                                    <strong>Auto-rotate every 90 days</strong>
                                    <small>Automatically generate new key and schedule old for deletion</small>
                                </div>
                            </label>
                        </div>

                        <div class="form-actions">
                            <button class="btn btn-primary" onclick="window.generateKey()" id="generate-key-btn">
                                <i class="fas fa-key"></i> Generate Key
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Generation Result -->
                <div class="key-generation-result" id="key-generation-result" style="display: none;">
                    <div class="card">
                        <div class="card-header">
                            <h4><i class="fas fa-check-circle"></i> Key Generated Successfully</h4>
                            <button class="btn btn-ghost btn-sm" onclick="window.closeKeyResult()">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                        <div class="card-body">
                            <div class="key-warning">
                                <i class="fas fa-exclamation-triangle"></i>
                                <span>Store the private key securely! It will not be shown again.</span>
                            </div>

                            <div class="key-output-group">
                                <div class="key-output">
                                    <label>Key ID</label>
                                    <div class="key-value-group">
                                        <code id="generated-key-id">-</code>
                                        <button class="btn btn-ghost btn-xs" onclick="window.copyKeyField('generated-key-id')">
                                            <i class="fas fa-copy"></i>
                                        </button>
                                    </div>
                                </div>

                                <div class="key-output">
                                    <label>Public Key</label>
                                    <div class="key-value-group">
                                        <textarea id="generated-public-key" class="form-textarea" readonly rows="2"></textarea>
                                        <button class="btn btn-ghost btn-xs" onclick="window.copyKeyField('generated-public-key')">
                                            <i class="fas fa-copy"></i>
                                        </button>
                                    </div>
                                </div>

                                <div class="key-output private">
                                    <label>Private Key (Download Only)</label>
                                    <div class="key-value-group">
                                        <textarea id="generated-private-key" class="form-textarea" readonly rows="4"></textarea>
                                        <div class="key-actions">
                                            <button class="btn btn-sm btn-primary" onclick="window.downloadPrivateKey()">
                                                <i class="fas fa-download"></i> Download
                                            </button>
                                            <button class="btn btn-sm btn-ghost" onclick="window.copyKeyField('generated-private-key')">
                                                <i class="fas fa-copy"></i> Copy
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Registered Keys List -->
            <div class="keys-list-section">
                <div class="card">
                    <div class="card-header">
                        <h4><i class="fas fa-list"></i> Registered Keys</h4>
                        <button class="btn btn-ghost btn-sm" onclick="window.refreshKeys()">
                            <i class="fas fa-sync"></i>
                        </button>
                    </div>
                    <div class="card-body">
                        <div class="keys-table-container">
                            <table class="data-table">
                                <thead>
                                    <tr>
                                        <th>Key ID</th>
                                        <th>Algorithm</th>
                                        <th>Label</th>
                                        <th>Created</th>
                                        <th>Status</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="keys-table-body">
                                    <!-- Filled dynamically -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Key Detail Modal -->
            <div id="key-detail-modal" class="modal">
                <div class="modal-content modal-lg">
                    <div class="modal-header">
                        <h3><i class="fas fa-key"></i> Key Details</h3>
                        <button class="modal-close" onclick="window.closeKeyModal()">&times;</button>
                    </div>
                    <div class="modal-body" id="key-detail-body">
                        <!-- Filled dynamically -->
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-danger" onclick="window.revokeKey()">
                            <i class="fas fa-ban"></i> Revoke Key
                        </button>
                        <button class="btn btn-primary" onclick="window.rotateKey()">
                            <i class="fas fa-rotate"></i> Rotate Key
                        </button>
                        <button class="btn btn-secondary" onclick="window.closeKeyModal()">Close</button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Load registered keys
 */
async function loadKeys() {
    const tbody = document.getElementById('keys-table-body');
    if (!tbody) return;

    try {
        let keys;
        try {
            keys = await apiGet('/keys');
        } catch (e) {
            keys = getDemoKeys();
        }

        keyState.keys = keys;

        // Update counts
        const activeKeys = keys.filter(k => k.status === 'active').length;
        const expiringKeys = keys.filter(k => {
            const daysUntilExpiry = Math.ceil((new Date(k.expires_at) - new Date()) / (1000 * 60 * 60 * 24));
            return daysUntilExpiry < 30;
        }).length;

        document.getElementById('active-keys-count').textContent = activeKeys;
        document.getElementById('expiring-keys-count').textContent = expiringKeys;

        if (keys.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-row">
                        <div class="empty-state">
                            <i class="fas fa-key"></i>
                            <p>No keys registered</p>
                            <small>Generate a key above to get started</small>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = keys.map(key => `
            <tr class="key-row ${key.status}" onclick="window.viewKeyDetail('${key.key_id}')">
                <td>
                    <code class="key-id">${key.key_id.substring(0, 16)}...</code>
                </td>
                <td>
                    <span class="algorithm-badge">${key.algorithm}</span>
                </td>
                <td>
                    <span class="key-label">${escapeHtml(key.label || '-')}</span>
                </td>
                <td>
                    <span class="created-date">${formatDate(key.created_at)}</span>
                </td>
                <td>
                    <span class="status-badge ${key.status}">${key.status}</span>
                    ${key.expires_at ? `<small class="expires">Expires: ${formatDate(key.expires_at)}</small>` : ''}
                </td>
                <td>
                    <div class="key-actions-cell">
                        <button class="btn btn-ghost btn-xs" onclick="event.stopPropagation(); window.viewKeyDetail('${key.key_id}')" title="View">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-ghost btn-xs" onclick="event.stopPropagation(); window.rotateKey('${key.key_id}')" title="Rotate">
                            <i class="fas fa-rotate"></i>
                        </button>
                        <button class="btn btn-ghost btn-xs danger" onclick="event.stopPropagation(); window.confirmRevokeKey('${key.key_id}')" title="Revoke">
                            <i class="fas fa-ban"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');

    } catch (error) {
        console.error('Failed to load keys:', error);
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-row">
                    <div class="empty-state error-state">
                        <i class="fas fa-exclamation-triangle"></i>
                        <p>Failed to load keys</p>
                        <button class="btn btn-outline btn-sm" onclick="window.refreshKeys()">Retry</button>
                    </div>
                </td>
            </tr>
        `;
    }
}

/**
 * Generate new key
 */
async function generateKey() {
    const algorithm = document.getElementById('key-algorithm')?.value;
    const label = document.getElementById('key-label')?.value;
    const autoRotate = document.getElementById('key-auto-rotate')?.checked;
    const btn = document.getElementById('generate-key-btn');

    if (!algorithm) {
        showToast('error', 'Select Algorithm', 'Please select a key algorithm');
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';

    try {
        let result;
        try {
            result = await apiPost('/keys/generate', {
                algorithm,
                label: label || null,
                auto_rotate: autoRotate
            });
        } catch (e) {
            // Demo key generation
            result = generateDemoKey(algorithm, label);
        }

        // Show result
        const resultSection = document.getElementById('key-generation-result');
        resultSection.style.display = 'block';

        document.getElementById('generated-key-id').textContent = result.key_id;
        document.getElementById('generated-public-key').value = result.public_key;
        document.getElementById('generated-private-key').value = result.private_key;

        keyState.lastGeneratedKey = result;

        showToast('success', 'Key Generated', `${algorithm} key created successfully`);
        loadKeys();

    } catch (error) {
        console.error('Key generation failed:', error);
        showToast('error', 'Generation Failed', error.message || 'Failed to generate key');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-key"></i> Generate Key';
    }
}

/**
 * View key details
 */
function viewKeyDetail(keyId) {
    const key = keyState.keys.find(k => k.key_id === keyId);
    if (!key) return;

    keyState.selectedKey = key;
    const modal = document.getElementById('key-detail-modal');
    const body = document.getElementById('key-detail-body');

    const daysUntilExpiry = Math.ceil((new Date(key.expires_at) - new Date()) / (1000 * 60 * 60 * 24));
    const isExpiring = daysUntilExpiry < 30;

    body.innerHTML = `
        <div class="key-detail-content">
            <div class="detail-header ${key.status}">
                <div class="detail-status">
                    <i class="fas ${key.status === 'active' ? 'fa-check-circle' : 'fa-times-circle'}"></i>
                    <span>${key.status.toUpperCase()}</span>
                </div>
                <div class="detail-id">
                    <span class="label">Key ID:</span>
                    <code>${key.key_id}</code>
                </div>
            </div>

            <div class="detail-sections">
                <div class="detail-section">
                    <h5>Key Information</h5>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="label">Algorithm</span>
                            <span class="value">${key.algorithm}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Label</span>
                            <span class="value">${key.label || '-'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Created</span>
                            <span class="value">${formatDate(key.created_at)} ${formatTimeShort(key.created_at)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Expires</span>
                            <span class="value ${isExpiring ? 'warning' : ''}">${formatDate(key.expires_at)} (${daysUntilExpiry} days)</span>
                        </div>
                    </div>
                </div>

                <div class="detail-section">
                    <h5>Public Key</h5>
                    <div class="public-key-display">
                        <pre>${key.public_key || 'Not available (key stored securely)'}</pre>
                        ${key.public_key ? `
                            <button class="btn btn-ghost btn-xs" onclick="window.copyPublicKey()">
                                <i class="fas fa-copy"></i>
                            </button>
                        ` : ''}
                    </div>
                </div>

                <div class="detail-section">
                    <h5>Usage Statistics</h5>
                    <div class="usage-stats">
                        <div class="usage-item">
                            <span class="usage-label">Encryptions</span>
                            <span class="usage-value">${key.encryption_count || 0}</span>
                        </div>
                        <div class="usage-item">
                            <span class="usage-label">Decryptions</span>
                            <span class="usage-value">${key.decryption_count || 0}</span>
                        </div>
                        <div class="usage-item">
                            <span class="usage-label">Last Used</span>
                            <span class="usage-value">${key.last_used ? formatDate(key.last_used) : 'Never'}</span>
                        </div>
                    </div>
                </div>

                <div class="detail-section">
                    <h5>Key History</h5>
                    <div class="key-history">
                        ${key.history?.length > 0 ? key.history.map(h => `
                            <div class="history-item">
                                <span class="history-action">${h.action}</span>
                                <span class="history-time">${formatDate(h.timestamp)}</span>
                            </div>
                        `).join('') : '<p class="no-history">No history available</p>'}
                    </div>
                </div>

                ${isExpiring ? `
                    <div class="detail-section warning-section">
                        <div class="warning-banner">
                            <i class="fas fa-exclamation-triangle"></i>
                            <span>This key expires in ${daysUntilExpiry} days. Consider rotating it.</span>
                        </div>
                    </div>
                ` : ''}
            </div>
        </div>
    `;

    modal.classList.add('active');
}

/**
 * Rotate key
 */
async function rotateKey(keyId) {
    const id = keyId || keyState.selectedKey?.key_id;
    if (!id) return;

    if (!confirm('Are you sure you want to rotate this key? A new key will be generated and the old key will be scheduled for deprecation.')) {
        return;
    }

    try {
        const result = await apiPost(`/keys/${id}/rotate`, {});

        showToast('success', 'Key Rotated', 'New key generated. Download the new private key!');

        // Show new key if provided
        if (result.new_key) {
            keyState.lastGeneratedKey = result.new_key;
            viewKeyDetail(result.new_key.key_id);
        }

        loadKeys();

    } catch (error) {
        showToast('error', 'Rotation Failed', error.message || 'Failed to rotate key');
    }
}

/**
 * Confirm key revocation
 */
function confirmRevokeKey(keyId) {
    if (!confirm('Are you sure you want to revoke this key? This action cannot be undone and the key will no longer be usable.')) {
        return;
    }

    revokeKeyById(keyId);
}

/**
 * Revoke key by ID
 */
async function revokeKeyById(keyId) {
    const id = keyId || keyState.selectedKey?.key_id;
    if (!id) return;

    try {
        await apiDelete(`/keys/${id}`);

        showToast('success', 'Key Revoked', 'The key has been revoked');
        closeKeyModal();
        loadKeys();

    } catch (error) {
        showToast('error', 'Revocation Failed', error.message || 'Failed to revoke key');
    }
}

/**
 * Download private key
 */
function downloadPrivateKey() {
    if (!keyState.lastGeneratedKey?.private_key) {
        showToast('error', 'No Key', 'No private key available to download');
        return;
    }

    const key = keyState.lastGeneratedKey;
    const filename = `${key.algorithm.toLowerCase()}_${key.key_id.substring(0, 8)}_private.key`;
    const blob = new Blob([key.private_key], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast('success', 'Downloaded', 'Private key saved securely');
}

/**
 * Copy key field
 */
function copyKeyField(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const text = el.value || el.textContent;
    navigator.clipboard.writeText(text);
    showToast('success', 'Copied', 'Key copied to clipboard');
}

/**
 * Close key modal
 */
function closeKeyModal() {
    const modal = document.getElementById('key-detail-modal');
    if (modal) modal.classList.remove('active');
}

/**
 * Close key result section
 */
function closeKeyResult() {
    const resultSection = document.getElementById('key-generation-result');
    if (resultSection) resultSection.style.display = 'none';
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
 * Demo key generators
 */
function getDemoKeys() {
    return [
        {
            key_id: 'mlkem768_a1b2c3d4e5f6',
            algorithm: 'ML-KEM-768',
            label: 'Production Key',
            status: 'active',
            created_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
            expires_at: new Date(Date.now() + 60 * 24 * 60 * 60 * 1000).toISOString(),
            encryption_count: 1523,
            last_used: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString()
        },
        {
            key_id: 'mlkem512_g7h8i9j0k1l2',
            algorithm: 'ML-KEM-512',
            label: 'Development Key',
            status: 'active',
            created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
            expires_at: new Date(Date.now() + 83 * 24 * 60 * 60 * 1000).toISOString(),
            encryption_count: 89,
            last_used: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
        }
    ];
}

function generateDemoKey(algorithm, label) {
    const keyId = `${algorithm.toLowerCase().replace('-', '').toLowerCase()}_${Math.random().toString(36).substring(2, 14)}`;
    return {
        key_id: keyId,
        algorithm,
        label,
        public_key: `-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...\n-----END PUBLIC KEY-----`,
        private_key: `-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQD...\n-----END PRIVATE KEY-----`
    };
}

// Global exports
window.refreshKeys = loadKeys;
window.generateKey = generateKey;
window.viewKeyDetail = viewKeyDetail;
window.rotateKey = rotateKey;
window.confirmRevokeKey = confirmRevokeKey;
window.revokeKey = () => revokeKeyById(keyState.selectedKey?.key_id);
window.closeKeyModal = closeKeyModal;
window.closeKeyResult = closeKeyResult;
window.downloadPrivateKey = downloadPrivateKey;
window.copyKeyField = copyKeyField;
window.copyPublicKey = () => {
    if (keyState.selectedKey?.public_key) {
        navigator.clipboard.writeText(keyState.selectedKey.public_key);
        showToast('success', 'Copied', 'Public key copied to clipboard');
    }
};
