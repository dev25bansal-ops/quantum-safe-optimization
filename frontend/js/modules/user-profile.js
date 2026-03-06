/**
 * User Profile Module
 * Handles user settings, API tokens, usage statistics, and billing
 */

import { showToast } from './toast.js';
import { apiGet, apiPost, apiDelete } from './api.js';
import { STATE, CONFIG } from './config.js';
import { formatDate, escapeHtml } from './utils.js';

let profileState = {
    user: null,
    apiTokens: [],
    usage: null,
    billing: null,
    preferences: {}
};

/**
 * Initialize user profile section
 */
export function initUserProfile() {
    const container = document.getElementById('profile-section');
    if (!container) return;

    renderProfileUI(container);
    loadUserProfile();
    loadApiTokens();
    loadUsageStats();
}

/**
 * Render profile UI
 */
function renderProfileUI(container) {
    container.innerHTML = `
        <div class="profile-container">
            <!-- Profile Header -->
            <div class="profile-header-section">
                <div class="profile-avatar-large" id="profile-avatar-large">
                    <span>--</span>
                </div>
                <div class="profile-header-info">
                    <h2 id="profile-name">Loading...</h2>
                    <p id="profile-email">--</p>
                    <div class="profile-badges">
                        <span class="profile-badge" id="profile-tier">
                            <i class="fas fa-crown"></i> Free Tier
                        </span>
                        <span class="profile-badge" id="profile-member-since">
                            <i class="fas fa-calendar"></i> Member since --
                        </span>
                    </div>
                </div>
                <div class="profile-header-actions">
                    <button class="btn btn-outline" onclick="window.editProfile()">
                        <i class="fas fa-edit"></i> Edit Profile
                    </button>
                </div>
            </div>

            <!-- Usage Overview -->
            <div class="profile-section">
                <div class="card">
                    <div class="card-header">
                        <h3><i class="fas fa-chart-pie"></i> Usage Overview</h3>
                        <span class="period-selector">
                            <select id="usage-period" onchange="window.loadUsageStats()">
                                <option value="7d">Last 7 days</option>
                                <option value="30d" selected>Last 30 days</option>
                                <option value="90d">Last 90 days</option>
                            </select>
                        </span>
                    </div>
                    <div class="card-body">
                        <div class="usage-grid">
                            <div class="usage-card">
                                <div class="usage-icon">
                                    <i class="fas fa-tasks"></i>
                                </div>
                                <div class="usage-info">
                                    <span class="usage-value" id="usage-jobs">--</span>
                                    <span class="usage-label">Jobs Submitted</span>
                                </div>
                            </div>
                            <div class="usage-card">
                                <div class="usage-icon success">
                                    <i class="fas fa-check-circle"></i>
                                </div>
                                <div class="usage-info">
                                    <span class="usage-value" id="usage-success">--</span>
                                    <span class="usage-label">Completed</span>
                                </div>
                            </div>
                            <div class="usage-card">
                                <div class="usage-icon warning">
                                    <i class="fas fa-clock"></i>
                                </div>
                                <div class="usage-info">
                                    <span class="usage-value" id="usage-time">--</span>
                                    <span class="usage-label">Compute Time</span>
                                </div>
                            </div>
                            <div class="usage-card">
                                <div class="usage-icon info">
                                    <i class="fas fa-microchip"></i>
                                </div>
                                <div class="usage-info">
                                    <span class="usage-value" id="usage-qubits">--</span>
                                    <span class="usage-label">Qubits Used</span>
                                </div>
                            </div>
                        </div>

                        <!-- Usage Chart -->
                        <div class="usage-chart-container">
                            <canvas id="usage-chart"></canvas>
                        </div>

                        <!-- Quota Progress -->
                        <div class="quota-section">
                            <h4>Monthly Quota</h4>
                            <div class="quota-item">
                                <div class="quota-header">
                                    <span>Jobs</span>
                                    <span id="quota-jobs-text">0 / 100</span>
                                </div>
                                <div class="quota-bar">
                                    <div class="quota-fill" id="quota-jobs-fill" style="width: 0%"></div>
                                </div>
                            </div>
                            <div class="quota-item">
                                <div class="quota-header">
                                    <span>Compute Hours</span>
                                    <span id="quota-hours-text">0 / 10h</span>
                                </div>
                                <div class="quota-bar">
                                    <div class="quota-fill" id="quota-hours-fill" style="width: 0%"></div>
                                </div>
                            </div>
                            <div class="quota-item">
                                <div class="quota-header">
                                    <span>API Requests</span>
                                    <span id="quota-requests-text">0 / 10,000</span>
                                </div>
                                <div class="quota-bar">
                                    <div class="quota-fill" id="quota-requests-fill" style="width: 0%"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- API Tokens -->
            <div class="profile-section">
                <div class="card">
                    <div class="card-header">
                        <h3><i class="fas fa-key"></i> API Tokens</h3>
                        <button class="btn btn-primary btn-sm" onclick="window.generateApiToken()">
                            <i class="fas fa-plus"></i> Generate Token
                        </button>
                    </div>
                    <div class="card-body">
                        <div class="tokens-list" id="api-tokens-list">
                            <div class="loading-state">
                                <i class="fas fa-spinner fa-spin"></i>
                                <span>Loading tokens...</span>
                            </div>
                        </div>

                        <!-- Generate Token Modal -->
                        <div id="token-generate-modal" class="modal">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h3><i class="fas fa-key"></i> Generate API Token</h3>
                                    <button class="modal-close" onclick="window.closeTokenModal()">&times;</button>
                                </div>
                                <div class="modal-body">
                                    <div class="form-group">
                                        <label for="token-name">Token Name</label>
                                        <input type="text" id="token-name" class="form-input" 
                                               placeholder="e.g., Production API Key">
                                    </div>
                                    <div class="form-group">
                                        <label for="token-expiry">Expiry</label>
                                        <select id="token-expiry" class="form-select">
                                            <option value="30">30 days</option>
                                            <option value="90">90 days</option>
                                            <option value="365">1 year</option>
                                            <option value="never">Never</option>
                                        </select>
                                    </div>
                                    <div class="form-group">
                                        <label>Permissions</label>
                                        <div class="checkbox-group">
                                            <label class="checkbox">
                                                <input type="checkbox" id="perm-jobs" checked>
                                                <span class="checkmark"></span>
                                                <span>Jobs (read/write)</span>
                                            </label>
                                            <label class="checkbox">
                                                <input type="checkbox" id="perm-keys" checked>
                                                <span class="checkmark"></span>
                                                <span>Keys (read)</span>
                                            </label>
                                            <label class="checkbox">
                                                <input type="checkbox" id="perm-webhooks">
                                                <span class="checkmark"></span>
                                                <span>Webhooks (read/write)</span>
                                            </label>
                                        </div>
                                    </div>
                                </div>
                                <div class="modal-footer">
                                    <button class="btn btn-ghost" onclick="window.closeTokenModal()">Cancel</button>
                                    <button class="btn btn-primary" onclick="window.confirmGenerateToken()">
                                        <i class="fas fa-key"></i> Generate
                                    </button>
                                </div>
                            </div>
                        </div>

                        <!-- Token Created Modal -->
                        <div id="token-created-modal" class="modal">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h3><i class="fas fa-check-circle"></i> Token Created</h3>
                                    <button class="modal-close" onclick="window.closeTokenCreatedModal()">&times;</button>
                                </div>
                                <div class="modal-body">
                                    <div class="token-warning">
                                        <i class="fas fa-exclamation-triangle"></i>
                                        <span>Copy this token now! It won't be shown again.</span>
                                    </div>
                                    <div class="token-display">
                                        <code id="new-token-value"></code>
                                        <button class="btn btn-ghost btn-sm" onclick="window.copyNewToken()">
                                            <i class="fas fa-copy"></i>
                                        </button>
                                    </div>
                                </div>
                                <div class="modal-footer">
                                    <button class="btn btn-primary" onclick="window.closeTokenCreatedModal()">
                                        Done
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Account Settings -->
            <div class="profile-section">
                <div class="card">
                    <div class="card-header">
                        <h3><i class="fas fa-cog"></i> Account Settings</h3>
                    </div>
                    <div class="card-body">
                        <div class="settings-form">
                            <div class="form-group">
                                <label for="setting-name">Display Name</label>
                                <input type="text" id="setting-name" class="form-input" 
                                       placeholder="Your name">
                            </div>
                            <div class="form-group">
                                <label for="setting-email">Email Address</label>
                                <input type="email" id="setting-email" class="form-input" 
                                       placeholder="your@email.com" disabled>
                            </div>
                            <div class="form-group">
                                <label for="setting-timezone">Timezone</label>
                                <select id="setting-timezone" class="form-select">
                                    <option value="UTC">UTC</option>
                                    <option value="America/New_York">Eastern Time</option>
                                    <option value="America/Chicago">Central Time</option>
                                    <option value="America/Denver">Mountain Time</option>
                                    <option value="America/Los_Angeles">Pacific Time</option>
                                    <option value="Europe/London">London</option>
                                    <option value="Europe/Paris">Paris</option>
                                    <option value="Asia/Tokyo">Tokyo</option>
                                </select>
                            </div>

                            <h4>Notifications</h4>
                            <div class="checkbox-group">
                                <label class="checkbox">
                                    <input type="checkbox" id="notify-email" checked>
                                    <span class="checkmark"></span>
                                    <span>Email notifications for completed jobs</span>
                                </label>
                                <label class="checkbox">
                                    <input type="checkbox" id="notify-webhook">
                                    <span class="checkmark"></span>
                                    <span>Webhook notifications</span>
                                </label>
                                <label class="checkbox">
                                    <input type="checkbox" id="notify-newsletter">
                                    <span class="checkmark"></span>
                                    <span>Newsletter and updates</span>
                                </label>
                            </div>

                            <div class="form-actions">
                                <button class="btn btn-primary" onclick="window.saveAccountSettings()">
                                    <i class="fas fa-save"></i> Save Settings
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Security Settings -->
            <div class="profile-section">
                <div class="card">
                    <div class="card-header">
                        <h3><i class="fas fa-shield-alt"></i> Security</h3>
                    </div>
                    <div class="card-body">
                        <div class="security-actions">
                            <div class="security-item">
                                <div class="security-info">
                                    <h4>Change Password</h4>
                                    <p>Update your account password</p>
                                </div>
                                <button class="btn btn-outline" onclick="window.showChangePassword()">
                                    <i class="fas fa-key"></i> Change
                                </button>
                            </div>
                            <div class="security-item">
                                <div class="security-info">
                                    <h4>Two-Factor Authentication</h4>
                                    <p>Add an extra layer of security</p>
                                </div>
                                <button class="btn btn-outline" onclick="window.setup2FA()">
                                    <i class="fas fa-mobile-alt"></i> Enable
                                </button>
                            </div>
                            <div class="security-item">
                                <div class="security-info">
                                    <h4>Active Sessions</h4>
                                    <p>Manage your active login sessions</p>
                                </div>
                                <button class="btn btn-outline" onclick="window.viewSessions()">
                                    <i class="fas fa-laptop"></i> View
                                </button>
                            </div>
                            <div class="security-item danger">
                                <div class="security-info">
                                    <h4>Delete Account</h4>
                                    <p>Permanently delete your account and data</p>
                                </div>
                                <button class="btn btn-danger" onclick="window.confirmDeleteAccount()">
                                    <i class="fas fa-trash"></i> Delete
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Billing (for paid tiers) -->
            <div class="profile-section" id="billing-section" style="display: none;">
                <div class="card">
                    <div class="card-header">
                        <h3><i class="fas fa-credit-card"></i> Billing</h3>
                        <a href="#" class="btn btn-outline btn-sm" onclick="window.manageSubscription()">
                            <i class="fas fa-external-link-alt"></i> Manage
                        </a>
                    </div>
                    <div class="card-body">
                        <div class="billing-info">
                            <div class="billing-item">
                                <span class="billing-label">Current Plan</span>
                                <span class="billing-value" id="billing-plan">Free</span>
                            </div>
                            <div class="billing-item">
                                <span class="billing-label">Next Billing Date</span>
                                <span class="billing-value" id="billing-next">--</span>
                            </div>
                            <div class="billing-item">
                                <span class="billing-label">Payment Method</span>
                                <span class="billing-value" id="billing-method">--</span>
                            </div>
                        </div>

                        <button class="btn btn-primary" onclick="window.upgradePlan()">
                            <i class="fas fa-arrow-up"></i> Upgrade Plan
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Load user profile data
 */
async function loadUserProfile() {
    try {
        let userData;
        try {
            userData = await apiGet('/auth/me');
        } catch (e) {
            // Use stored user data
            const storedUser = localStorage.getItem('quantumSafeUser');
            userData = storedUser ? JSON.parse(storedUser) : getDefaultUser();
        }

        profileState.user = userData;
        updateProfileUI(userData);

    } catch (error) {
        console.error('Failed to load profile:', error);
    }
}

function getDefaultUser() {
    return {
        name: 'Demo User',
        email: 'demo@example.com',
        created_at: new Date().toISOString(),
        tier: 'free'
    };
}

/**
 * Update profile UI with user data
 */
function updateProfileUI(user) {
    if (!user) return;

    // Avatar
    const avatar = document.getElementById('profile-avatar-large');
    if (avatar) {
        avatar.querySelector('span').textContent = (user.name || user.email || 'U').charAt(0).toUpperCase();
    }

    // Name and email
    document.getElementById('profile-name').textContent = user.name || 'User';
    document.getElementById('profile-email').textContent = user.email || '--';

    // Tier badge
    const tierBadge = document.getElementById('profile-tier');
    if (tierBadge) {
        tierBadge.innerHTML = `<i class="fas fa-crown"></i> ${user.tier || 'Free'} Tier`;
    }

    // Member since
    const memberSince = document.getElementById('profile-member-since');
    if (memberSince && user.created_at) {
        const date = new Date(user.created_at);
        memberSince.innerHTML = `<i class="fas fa-calendar"></i> Member since ${date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}`;
    }

    // Update settings form
    if (user.name) {
        document.getElementById('setting-name').value = user.name;
    }
    if (user.email) {
        document.getElementById('setting-email').value = user.email;
    }
}

/**
 * Load API tokens
 */
async function loadApiTokens() {
    const tokensList = document.getElementById('api-tokens-list');
    if (!tokensList) return;

    try {
        let tokens;
        try {
            tokens = await apiGet('/auth/tokens');
        } catch (e) {
            tokens = getDemoTokens();
        }

        profileState.apiTokens = tokens;

        if (tokens.length === 0) {
            tokensList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-key"></i>
                    <p>No API tokens generated</p>
                    <button class="btn btn-primary btn-sm" onclick="window.generateApiToken()">
                        <i class="fas fa-plus"></i> Generate Token
                    </button>
                </div>
            `;
            return;
        }

        tokensList.innerHTML = tokens.map(token => `
            <div class="token-item">
                <div class="token-info">
                    <span class="token-name">
                        <i class="fas fa-key"></i>
                        ${escapeHtml(token.name || 'API Token')}
                    </span>
                    <span class="token-preview">${token.prefix || 'qso_'}...${token.last4 || '****'}</span>
                    <div class="token-meta">
                        <span class="token-created">Created: ${formatDate(token.created_at)}</span>
                        ${token.expires_at ? `<span class="token-expires">Expires: ${formatDate(token.expires_at)}</span>` : ''}
                        <span class="token-last-used">Last used: ${token.last_used ? formatDate(token.last_used) : 'Never'}</span>
                    </div>
                </div>
                <div class="token-actions">
                    <button class="btn btn-ghost btn-sm" onclick="window.copyToken('${token.id}')" title="Copy">
                        <i class="fas fa-copy"></i>
                    </button>
                    <button class="btn btn-ghost btn-sm danger" onclick="window.revokeToken('${token.id}')" title="Revoke">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Failed to load tokens:', error);
        tokensList.innerHTML = `
            <div class="error-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Failed to load tokens</p>
                <button class="btn btn-outline btn-sm" onclick="window.loadApiTokens()">Retry</button>
            </div>
        `;
    }
}

function getDemoTokens() {
    return [
        {
            id: 'tok_demo_1',
            name: 'Development Token',
            prefix: 'qso_',
            last4: 'abcd',
            created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
            expires_at: new Date(Date.now() + 83 * 24 * 60 * 60 * 1000).toISOString(),
            last_used: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString()
        }
    ];
}

/**
 * Load usage statistics
 */
async function loadUsageStats() {
    try {
        let usage;
        try {
            const period = document.getElementById('usage-period')?.value || '30d';
            usage = await apiGet(`/users/usage?period=${period}`);
        } catch (e) {
            usage = getDemoUsage();
        }

        profileState.usage = usage;
        updateUsageUI(usage);

    } catch (error) {
        console.error('Failed to load usage:', error);
    }
}

function getDemoUsage() {
    return {
        jobs_submitted: 47,
        jobs_completed: 42,
        compute_time_hours: 2.3,
        qubits_used: 1280,
        api_requests: 3420,
        quota: {
            jobs_limit: 100,
            hours_limit: 10,
            requests_limit: 10000
        },
        daily: [
            { date: new Date(Date.now() - 6 * 24 * 60 * 60 * 1000).toISOString(), jobs: 5 },
            { date: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(), jobs: 8 },
            { date: new Date(Date.now() - 4 * 24 * 60 * 60 * 1000).toISOString(), jobs: 3 },
            { date: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(), jobs: 12 },
            { date: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(), jobs: 7 },
            { date: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(), jobs: 9 },
            { date: new Date().toISOString(), jobs: 3 }
        ]
    };
}

/**
 * Update usage UI
 */
function updateUsageUI(usage) {
    if (!usage) return;

    document.getElementById('usage-jobs').textContent = usage.jobs_submitted || 0;
    document.getElementById('usage-success').textContent = usage.jobs_completed || 0;
    document.getElementById('usage-time').textContent = `${usage.compute_time_hours?.toFixed(1) || 0}h`;
    document.getElementById('usage-qubits').textContent = usage.qubits_used?.toLocaleString() || 0;

    // Update quota bars
    const quota = usage.quota || {};
    
    const jobsPercent = Math.min((usage.jobs_submitted / (quota.jobs_limit || 100)) * 100, 100);
    document.getElementById('quota-jobs-fill').style.width = `${jobsPercent}%`;
    document.getElementById('quota-jobs-text').textContent = `${usage.jobs_submitted} / ${quota.jobs_limit || 100}`;

    const hoursPercent = Math.min((usage.compute_time_hours / (quota.hours_limit || 10)) * 100, 100);
    document.getElementById('quota-hours-fill').style.width = `${hoursPercent}%`;
    document.getElementById('quota-hours-text').textContent = `${usage.compute_time_hours?.toFixed(1) || 0}h / ${quota.hours_limit || 10}h`;

    const requestsPercent = Math.min((usage.api_requests / (quota.requests_limit || 10000)) * 100, 100);
    document.getElementById('quota-requests-fill').style.width = `${requestsPercent}%`;
    document.getElementById('quota-requests-text').textContent = `${usage.api_requests?.toLocaleString() || 0} / ${(quota.requests_limit || 10000).toLocaleString()}`;

    // Render usage chart
    renderUsageChart(usage.daily || []);
}

/**
 * Render usage chart
 */
async function renderUsageChart(dailyData) {
    const canvas = document.getElementById('usage-chart');
    if (!canvas || !window.Chart) return;

    await loadChartJS();

    const ctx = canvas.getContext('2d');

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: dailyData.map(d => {
                const date = new Date(d.date);
                return date.toLocaleDateString('en-US', { weekday: 'short' });
            }),
            datasets: [{
                label: 'Jobs',
                data: dailyData.map(d => d.jobs),
                backgroundColor: 'rgba(99, 102, 241, 0.6)',
                borderColor: '#6366f1',
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { display: false }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(100, 116, 139, 0.2)' }
                }
            }
        }
    });
}

/**
 * Generate API token
 */
function generateApiToken() {
    const modal = document.getElementById('token-generate-modal');
    if (modal) modal.classList.add('active');
}

function closeTokenModal() {
    const modal = document.getElementById('token-generate-modal');
    if (modal) {
        modal.classList.remove('active');
        document.getElementById('token-name').value = '';
    }
}

async function confirmGenerateToken() {
    const name = document.getElementById('token-name').value;
    const expiry = document.getElementById('token-expiry').value;
    const permissions = {
        jobs: document.getElementById('perm-jobs').checked,
        keys: document.getElementById('perm-keys').checked,
        webhooks: document.getElementById('perm-webhooks').checked
    };

    if (!name) {
        showToast('error', 'Error', 'Please enter a token name');
        return;
    }

    try {
        let result;
        try {
            result = await apiPost('/auth/tokens', { name, expiry: expiry === 'never' ? null : parseInt(expiry), permissions });
        } catch (e) {
            // Demo token
            result = {
                token: 'qso_demo_' + Math.random().toString(36).substr(2, 32)
            };
        }

        closeTokenModal();

        // Show created modal
        document.getElementById('new-token-value').textContent = result.token;
        document.getElementById('token-created-modal').classList.add('active');

        loadApiTokens();

    } catch (error) {
        showToast('error', 'Failed', error.message || 'Failed to generate token');
    }
}

function closeTokenCreatedModal() {
    document.getElementById('token-created-modal').classList.remove('active');
}

function copyNewToken() {
    const token = document.getElementById('new-token-value').textContent;
    navigator.clipboard.writeText(token);
    showToast('success', 'Copied', 'Token copied to clipboard');
}

/**
 * Copy token
 */
function copyToken(tokenId) {
    const token = profileState.apiTokens.find(t => t.id === tokenId);
    if (token?.full_token) {
        navigator.clipboard.writeText(token.full_token);
        showToast('success', 'Copied', 'Token copied to clipboard');
    } else {
        showToast('info', 'Info', 'Full token not available. Generate a new token if needed.');
    }
}

/**
 * Revoke token
 */
async function revokeToken(tokenId) {
    if (!confirm('Are you sure you want to revoke this token? This cannot be undone.')) return;

    try {
        await apiDelete(`/auth/tokens/${tokenId}`);
        showToast('success', 'Revoked', 'Token has been revoked');
        loadApiTokens();
    } catch (error) {
        showToast('error', 'Failed', error.message || 'Failed to revoke token');
    }
}

/**
 * Save account settings
 */
async function saveAccountSettings() {
    const name = document.getElementById('setting-name').value;
    const timezone = document.getElementById('setting-timezone').value;
    const notifyEmail = document.getElementById('notify-email').checked;
    const notifyWebhook = document.getElementById('notify-webhook').checked;
    const notifyNewsletter = document.getElementById('notify-newsletter').checked;

    try {
        await apiPost('/users/settings', {
            name,
            timezone,
            notifications: {
                email: notifyEmail,
                webhook: notifyWebhook,
                newsletter: notifyNewsletter
            }
        });

        showToast('success', 'Saved', 'Account settings updated');

        // Update UI
        if (profileState.user) {
            profileState.user.name = name;
            updateProfileUI(profileState.user);
        }

    } catch (error) {
        // Save locally if API fails
        localStorage.setItem('userSettings', JSON.stringify({
            name,
            timezone,
            notifications: { email: notifyEmail, webhook: notifyWebhook, newsletter: notifyNewsletter }
        }));
        showToast('success', 'Saved', 'Settings saved locally');
    }
}

/**
 * Security actions
 */
function showChangePassword() {
    showToast('info', 'Coming Soon', 'Password change feature coming soon');
}

function setup2FA() {
    showToast('info', 'Coming Soon', 'Two-factor authentication coming soon');
}

function viewSessions() {
    showToast('info', 'Coming Soon', 'Session management coming soon');
}

function confirmDeleteAccount() {
    if (confirm('Are you sure you want to delete your account? This will permanently delete all your data.')) {
        if (confirm('This action cannot be undone. Type DELETE to confirm.')) {
            showToast('info', 'Coming Soon', 'Account deletion coming soon');
        }
    }
}

// Global exports
window.loadApiTokens = loadApiTokens;
window.loadUsageStats = loadUsageStats;
window.generateApiToken = generateApiToken;
window.closeTokenModal = closeTokenModal;
window.confirmGenerateToken = confirmGenerateToken;
window.closeTokenCreatedModal = closeTokenCreatedModal;
window.copyNewToken = copyNewToken;
window.copyToken = copyToken;
window.revokeToken = revokeToken;
window.saveAccountSettings = saveAccountSettings;
window.editProfile = () => showToast('info', 'Coming Soon', 'Profile editing coming soon');
window.showChangePassword = showChangePassword;
window.setup2FA = setup2FA;
window.viewSessions = viewSessions;
window.confirmDeleteAccount = confirmDeleteAccount;

export default {
    initUserProfile,
    loadUserProfile,
    loadApiTokens,
    loadUsageStats
};
