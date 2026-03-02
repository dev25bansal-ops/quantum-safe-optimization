/**
 * Workers Module
 * Handles worker status panel display
 */

import { CONFIG, STATE } from './config.js';
import { escapeHtml, getAuthHeaders } from './utils.js';
import { apiGet } from './api.js';

/**
 * Load worker status from API
 */
export async function loadWorkerStatus() {
    const workersGrid = document.getElementById('workers-grid');
    if (!workersGrid) return;

    try {
        let workers;

        try {
            const data = await apiGet('/workers');
            workers = data.workers || data || [];
        } catch (error) {
            // Show demo data for authenticated demo users or on network/404 error
            if (error.message.includes('Session expired') || error.message.includes('401') || 
                error.message.includes('404') || error.message.includes('Failed to fetch') || error.name === 'TypeError') {
                if (STATE.isAuthenticated) {
                    workers = getDemoWorkers();
                } else {
                    workersGrid.innerHTML = `
                        <div class="empty-state">
                            <i class="fas fa-lock"></i>
                            <p>Sign in to view worker status</p>
                        </div>
                    `;
                    return;
                }
            } else {
                throw error;
            }
        }

        STATE.workers = workers;

        if (workers.length === 0) {
            workersGrid.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-server"></i>
                    <p>No active workers</p>
                </div>
            `;
            return;
        }

        workersGrid.innerHTML = workers.map(worker => `
            <div class="worker-card ${worker.status || 'unknown'}">
                <div class="worker-header">
                    <span class="worker-name"><i class="fas fa-microchip"></i> ${escapeHtml(worker.name || worker.hostname || 'Worker')}</span>
                    <span class="worker-status ${worker.status === 'online' || worker.status === 'active' ? 'online' : 'offline'}">
                        ${escapeHtml(worker.status || 'Unknown')}
                    </span>
                </div>
                <div class="worker-details">
                    <div class="worker-detail">
                        <span class="label">Queue:</span>
                        <span class="value">${escapeHtml(worker.queue || worker.queues?.join(', ') || 'default')}</span>
                    </div>
                    <div class="worker-detail">
                        <span class="label">Tasks:</span>
                        <span class="value">${worker.active_tasks || worker.processed || 0}</span>
                    </div>
                    <div class="worker-detail">
                        <span class="label">Concurrency:</span>
                        <span class="value">${worker.concurrency || worker.pool_size || '—'}</span>
                    </div>
                    <div class="worker-detail">
                        <span class="label">Uptime:</span>
                        <span class="value">${escapeHtml(worker.uptime || '—')}</span>
                    </div>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Failed to load worker status:', error);
        workersGrid.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Failed to load worker status</p>
                <button class="btn btn-outline btn-sm" onclick="loadWorkerStatus()">Retry</button>
            </div>
        `;
    }
}

/**
 * Generate demo worker data
 */
function getDemoWorkers() {
    return [
        { name: 'worker-quantum-01', status: 'online', queue: 'high-priority', active_tasks: 3, concurrency: 8, uptime: '4d 12h 35m' },
        { name: 'worker-quantum-02', status: 'online', queue: 'default', active_tasks: 1, concurrency: 4, uptime: '2d 8h 15m' },
        { name: 'worker-annealing-01', status: 'online', queue: 'annealing', active_tasks: 2, concurrency: 2, uptime: '1d 3h 42m' }
    ];
}

// Make globally accessible
window.loadWorkerStatus = loadWorkerStatus;
