/**
 * Job Comparison Module
 * Handles job comparison functionality
 */

import { STATE } from './config.js';
import { escapeHtml, formatDate } from './utils.js';
import { showToast } from './toast.js';

/**
 * Initialize job comparison handlers
 */
export function initJobComparison() {
    const selectAllCheckbox = document.getElementById('select-all-jobs');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', (e) => {
            const checkboxes = document.querySelectorAll('.job-select-checkbox');
            checkboxes.forEach(cb => {
                cb.checked = e.target.checked;
                const jobId = cb.dataset.jobId;
                if (e.target.checked) {
                    if (!STATE.selectedForCompare.includes(jobId)) {
                        STATE.selectedForCompare.push(jobId);
                    }
                } else {
                    STATE.selectedForCompare = [];
                }
            });
            updateCompareButton();
        });
    }
}

/**
 * Toggle job selection for comparison
 */
export function toggleJobSelection(jobId) {
    const index = STATE.selectedForCompare.indexOf(jobId);
    if (index === -1) {
        if (STATE.selectedForCompare.length >= 4) {
            showToast('warning', 'Limit Reached', 'You can compare up to 4 jobs at once');
            // Uncheck the checkbox
            const checkbox = document.querySelector(`.job-select-checkbox[data-job-id="${jobId}"]`);
            if (checkbox) checkbox.checked = false;
            return;
        }
        STATE.selectedForCompare.push(jobId);
    } else {
        STATE.selectedForCompare.splice(index, 1);
    }
    updateCompareButton();
}

/**
 * Update compare button visibility
 */
export function updateCompareButton() {
    const btn = document.getElementById('compare-jobs-btn');
    const countSpan = document.getElementById('compare-count');

    if (btn && countSpan) {
        countSpan.textContent = STATE.selectedForCompare.length;
        btn.style.display = STATE.selectedForCompare.length >= 2 ? 'inline-flex' : 'none';
    }
}

/**
 * Open comparison modal
 */
export function openCompareModal() {
    if (STATE.selectedForCompare.length < 2) {
        showToast('info', 'Select Jobs', 'Select at least 2 jobs to compare');
        return;
    }

    const modal = document.getElementById('compare-modal');
    const grid = document.getElementById('compare-grid');

    if (!modal || !grid) return;

    const jobs = STATE.selectedForCompare.map(id => STATE.jobs.find(j => j.job_id === id)).filter(Boolean);

    grid.innerHTML = jobs.map(job => `
        <div class="compare-card">
            <div class="compare-header">
                <span class="type-badge ${escapeHtml(job.problem_type.toLowerCase())}">${escapeHtml(job.problem_type)}</span>
                <span class="status-badge ${escapeHtml(job.status)}">${escapeHtml(job.status)}</span>
            </div>
            <div class="compare-id">${escapeHtml(job.job_id.substring(0, 12))}...</div>
            <div class="compare-details">
                <div class="compare-row">
                    <span class="compare-label">Backend</span>
                    <span class="compare-value">${escapeHtml(job.backend)}</span>
                </div>
                <div class="compare-row">
                    <span class="compare-label">Created</span>
                    <span class="compare-value">${formatDate(job.created_at)}</span>
                </div>
                <div class="compare-row">
                    <span class="compare-label">Encrypted</span>
                    <span class="compare-value">${job.encrypted ? '🔐 Yes' : 'No'}</span>
                </div>
                ${job.result ? `
                    <div class="compare-row highlight">
                        <span class="compare-label">Optimal Value</span>
                        <span class="compare-value">${job.result.optimal_value?.toFixed(6) || '-'}</span>
                    </div>
                    <div class="compare-row">
                        <span class="compare-label">Iterations</span>
                        <span class="compare-value">${job.result.iterations || job.result.convergence_history?.length || '-'}</span>
                    </div>
                    <div class="compare-row">
                        <span class="compare-label">Exec Time</span>
                        <span class="compare-value">${job.result.execution_time ? job.result.execution_time + 's' : '-'}</span>
                    </div>
                ` : '<div class="compare-row"><span class="compare-label">Results</span><span class="compare-value text-muted">Not available</span></div>'}
            </div>
        </div>
    `).join('');

    modal.classList.add('active');
}

/**
 * Close comparison modal
 */
export function closeCompareModal() {
    const modal = document.getElementById('compare-modal');
    if (modal) modal.classList.remove('active');
}

/**
 * Export comparison data
 */
export function exportComparison() {
    const jobs = STATE.selectedForCompare.map(id => STATE.jobs.find(j => j.job_id === id)).filter(Boolean);

    const comparison = {
        exported_at: new Date().toISOString(),
        jobs: jobs.map(job => ({
            job_id: job.job_id,
            problem_type: job.problem_type,
            backend: job.backend,
            status: job.status,
            encrypted: job.encrypted,
            created_at: job.created_at,
            result: job.result || null
        }))
    };

    const blob = new Blob([JSON.stringify(comparison, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `job_comparison_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);

    showToast('success', 'Exported', 'Comparison exported successfully');
    closeCompareModal();
}

// Make functions globally accessible
window.toggleJobSelection = toggleJobSelection;
window.openCompareModal = openCompareModal;
window.closeCompareModal = closeCompareModal;
window.exportComparison = exportComparison;
