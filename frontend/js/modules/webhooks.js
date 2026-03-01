/**
 * Webhooks Module
 * Handles webhook statistics display
 */

import { CONFIG, STATE } from './config.js';
import { escapeHtml, formatDate, getAuthHeaders } from './utils.js';
import { apiGet } from './api.js';

/**
 * Load webhook statistics from API
 */
export async function loadWebhookStats() {
    const statsGrid = document.getElementById('webhook-stats-grid');
    const recentSection = document.getElementById('recent-webhooks');
    const webhooksList = document.getElementById('webhooks-list');

    if (!statsGrid) return;

    try {
        let data;

        try {
            data = await apiGet('/webhooks/stats');
        } catch (error) {
            // Show demo data for authenticated demo users or on network error
            if (error.message.includes('Session expired') || error.message.includes('401') || 
                error.message.includes('Failed to fetch') || error.name === 'TypeError') {
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
            } else {
                throw error;
            }
        }

        STATE.webhookStats = data;

        // Render statistics grid
        statsGrid.innerHTML = `
            <div class="webhook-stat-card">
                <div class="stat-icon blue">
                    <i class="fas fa-paper-plane"></i>
                </div>
                <div class="stat-info">
                    <span class="stat-value">${data.total_sent || data.total || 0}</span>
                    <span class="stat-label">Total Sent</span>
                </div>
            </div>
            <div class="webhook-stat-card">
                <div class="stat-icon green">
                    <i class="fas fa-check-circle"></i>
                </div>
                <div class="stat-info">
                    <span class="stat-value">${data.successful || data.success || 0}</span>
                    <span class="stat-label">Successful</span>
                </div>
            </div>
            <div class="webhook-stat-card">
                <div class="stat-icon red">
                    <i class="fas fa-times-circle"></i>
                </div>
                <div class="stat-info">
                    <span class="stat-value">${data.failed || data.failures || 0}</span>
                    <span class="stat-label">Failed</span>
                </div>
            </div>
            <div class="webhook-stat-card">
                <div class="stat-icon yellow">
                    <i class="fas fa-redo"></i>
                </div>
                <div class="stat-info">
                    <span class="stat-value">${data.pending_retries || data.retries || 0}</span>
                    <span class="stat-label">Pending Retries</span>
                </div>
            </div>
        `;

        // Render recent webhooks if available
        const recentHooks = data.recent || data.deliveries || [];
        if (recentHooks.length > 0 && recentSection && webhooksList) {
            recentSection.style.display = 'block';
            webhooksList.innerHTML = recentHooks.slice(0, 10).map(hook => `
                <div class="webhook-item ${hook.status || (hook.success ? 'success' : 'failed')}">
                    <div class="webhook-info">
                        <span class="webhook-event"><i class="fas fa-bolt"></i> ${escapeHtml(hook.event || hook.type || 'job.update')}</span>
                        <span class="webhook-url">${escapeHtml(hook.url || hook.endpoint || '—')}</span>
                    </div>
                    <div class="webhook-meta">
                        <span class="webhook-time">${formatDate(hook.timestamp || hook.created_at)}</span>
                        <span class="webhook-status ${hook.success ? 'success' : 'failed'}">
                            ${hook.success ? '✓ Delivered' : '✗ Failed'}
                        </span>
                    </div>
                </div>
            `).join('');
        } else if (recentSection) {
            recentSection.style.display = 'none';
        }

    } catch (error) {
        console.error('Failed to load webhook stats:', error);
        statsGrid.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Failed to load webhook statistics</p>
                <button class="btn btn-outline btn-sm" onclick="loadWebhookStats()">Retry</button>
            </div>
        `;
    }
}

/**
 * Generate demo webhook stats
 */
function getDemoWebhookStats() {
    return {
        total_sent: 156,
        successful: 148,
        failed: 5,
        pending_retries: 3,
        recent: [
            { event: 'job.completed', url: 'https://api.example.com/webhooks', success: true, timestamp: new Date(Date.now() - 300000).toISOString() },
            { event: 'job.started', url: 'https://api.example.com/webhooks', success: true, timestamp: new Date(Date.now() - 600000).toISOString() },
            { event: 'job.failed', url: 'https://api.example.com/webhooks', success: false, timestamp: new Date(Date.now() - 900000).toISOString() },
            { event: 'job.completed', url: 'https://hooks.slack.com/quantum', success: true, timestamp: new Date(Date.now() - 1200000).toISOString() }
        ]
    };
}

// Make globally accessible
window.loadWebhookStats = loadWebhookStats;
