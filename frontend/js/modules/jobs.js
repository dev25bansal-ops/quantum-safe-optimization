/**
 * Jobs Module
 * Handles job listing, loading, and management
 */

import { CONFIG, STATE } from './config.js';
import { escapeHtml, formatDate, getTypeIcon, getStatusIcon, getAuthHeaders } from './utils.js';
import { showToast } from './toast.js';
import { filterJobs } from './search.js';
import { addNotification } from './notifications.js';
import { apiGet, apiPost, apiDelete } from './api.js';

// Forward declarations for callbacks
let viewJobDetailsCallback = null;
let updateStatusPieChartCallback = null;

export function setJobsCallbacks(viewDetails, updateChart) {
    viewJobDetailsCallback = viewDetails;
    updateStatusPieChartCallback = updateChart;
}

/**
 * Load jobs from API
 */
export async function loadJobs(showLoading = false) {
    if (STATE.isLoading) return;

    // Rate limiting: exponential backoff on failures
    const now = Date.now();
    if (STATE.loadJobsFailures > 0 && STATE.lastLoadAttempt) {
        const backoffMs = Math.min(2000 * Math.pow(2, STATE.loadJobsFailures - 1), 30000); // Max 30 seconds
        const timeSinceLastAttempt = now - STATE.lastLoadAttempt;
        if (timeSinceLastAttempt < backoffMs) {
            console.log(`[Jobs] Rate limited: waiting ${Math.ceil((backoffMs - timeSinceLastAttempt) / 1000)}s before retry`);
            return;
        }
    }
    STATE.lastLoadAttempt = now;

    // If user is not authenticated, show existing jobs (demo jobs) without API call
    // Check both storage types for backwards compatibility
    const token = sessionStorage.getItem('authToken') || localStorage.getItem('authToken');
    if (!token) {
        STATE.totalJobs = STATE.jobs.length;
        updateJobsUI();
        updateStats();
        updatePaginationUI();
        return;
    }

    try {
        STATE.isLoading = true;

        // Show loading skeleton if requested
        if (showLoading) {
            showJobsLoadingSkeleton();
        }

        // Build URL with pagination and filter params
        const skip = (STATE.currentPage - 1) * STATE.pageSize;
        let url = `/jobs?skip=${skip}&limit=${STATE.pageSize}`;

        // Add server-side filter params
        if (STATE.filterStatus && STATE.filterStatus !== 'all') {
            url += `&status=${encodeURIComponent(STATE.filterStatus)}`;
        }
        if (STATE.filterType && STATE.filterType !== 'all') {
            url += `&problem_type=${encodeURIComponent(STATE.filterType.toUpperCase())}`;
        }
        if (STATE.searchQuery) {
            url += `&search=${encodeURIComponent(STATE.searchQuery)}`;
        }

        // Use apiGet which includes retry logic and authentication headers
        const data = await apiGet(url);

        // Normalize job data - add encrypted flag from encrypt_result or encrypted_result
        STATE.jobs = (data.jobs || []).map(job => ({
            ...job,
            encrypted: job.encrypted || job.encrypt_result || !!job.encrypted_result
        }));

        // Update total count if provided
        STATE.totalJobs = data.total || STATE.jobs.length;

        // Reset failure counter on success
        STATE.loadJobsFailures = 0;

        updateJobsUI();
        updateStats();
        updatePaginationUI();

    } catch (error) {
        console.error('Failed to load jobs:', error);
        // Track consecutive failures for smart feedback
        STATE.loadJobsFailures = (STATE.loadJobsFailures || 0) + 1;

        // Check if this is a network/API unavailable error (demo mode scenario)
        const isApiUnavailable =
            error.message.includes('Failed to fetch') ||
            error.message.includes('NetworkError') ||
            error.message.includes('fetch') ||
            error.name === 'TypeError';

        // Only show toasts for real errors, not demo mode / API unavailable
        if (!isApiUnavailable) {
            // Show feedback on first failure or every 10th failure (avoid spam)
            if (STATE.loadJobsFailures === 1) {
                showToast('warning', 'Connection Issue', 'Unable to load jobs. Retrying...');
            } else if (STATE.loadJobsFailures % 10 === 0) {
                showToast('error', 'Persistent Error', `Failed to load jobs ${STATE.loadJobsFailures} times. Check your connection.`);
                addNotification('error', 'Jobs Load Failed', `Unable to fetch jobs after ${STATE.loadJobsFailures} attempts`);
            }
        }

        // In demo mode or on initial load failure, just show clean empty state
        if (STATE.jobs.length === 0) {
            updateJobsUI();  // This will show the "No jobs yet" state
            updateStats();
            updatePaginationUI();
        }
    } finally {
        STATE.isLoading = false;
        hideJobsLoadingSkeleton();
    }
}

/**
 * Show loading skeleton in jobs table
 */
function showJobsLoadingSkeleton() {
    const tableBody = document.getElementById('jobs-table-body');
    if (!tableBody) return;

    const skeletonRows = Array(5).fill().map(() => `
        <tr class="skeleton-row">
            <td><div class="skeleton skeleton-text" style="width: 80px;"></div></td>
            <td><div class="skeleton skeleton-text" style="width: 60px;"></div></td>
            <td><div class="skeleton skeleton-text" style="width: 100px;"></div></td>
            <td><div class="skeleton skeleton-text" style="width: 70px;"></div></td>
            <td><div class="skeleton skeleton-text" style="width: 50px;"></div></td>
            <td><div class="skeleton skeleton-text" style="width: 80px;"></div></td>
            <td><div class="skeleton skeleton-text" style="width: 60px;"></div></td>
        </tr>
    `).join('');

    tableBody.innerHTML = skeletonRows;
}

/**
 * Hide loading skeleton
 */
function hideJobsLoadingSkeleton() {
    const skeletonRows = document.querySelectorAll('.skeleton-row');
    skeletonRows.forEach(row => row.remove());
}

/**
 * Update pagination UI
 */
function updatePaginationUI() {
    const paginationContainer = document.getElementById('pagination-controls');
    if (!paginationContainer) return;

    const totalPages = Math.ceil(STATE.totalJobs / STATE.pageSize);

    if (totalPages <= 1) {
        paginationContainer.style.display = 'none';
        return;
    }

    paginationContainer.style.display = 'flex';

    let paginationHTML = `
        <button class="btn btn-ghost btn-sm" onclick="goToPage(1)" ${STATE.currentPage === 1 ? 'disabled' : ''}>
            <i class="fas fa-angle-double-left"></i>
        </button>
        <button class="btn btn-ghost btn-sm" onclick="goToPage(${STATE.currentPage - 1})" ${STATE.currentPage === 1 ? 'disabled' : ''}>
            <i class="fas fa-angle-left"></i>
        </button>
    `;

    // Show page numbers
    const startPage = Math.max(1, STATE.currentPage - 2);
    const endPage = Math.min(totalPages, STATE.currentPage + 2);

    for (let i = startPage; i <= endPage; i++) {
        paginationHTML += `
            <button class="btn ${i === STATE.currentPage ? 'btn-primary' : 'btn-ghost'} btn-sm" onclick="goToPage(${i})">
                ${i}
            </button>
        `;
    }

    paginationHTML += `
        <button class="btn btn-ghost btn-sm" onclick="goToPage(${STATE.currentPage + 1})" ${STATE.currentPage === totalPages ? 'disabled' : ''}>
            <i class="fas fa-angle-right"></i>
        </button>
        <button class="btn btn-ghost btn-sm" onclick="goToPage(${totalPages})" ${STATE.currentPage === totalPages ? 'disabled' : ''}>
            <i class="fas fa-angle-double-right"></i>
        </button>
        <span class="pagination-info">Page ${STATE.currentPage} of ${totalPages} (${STATE.totalJobs} jobs)</span>
    `;

    paginationContainer.innerHTML = paginationHTML;
}

/**
 * Go to specific page
 */
export function goToPage(page) {
    const totalPages = Math.ceil(STATE.totalJobs / STATE.pageSize);
    if (page < 1 || page > totalPages) return;

    STATE.currentPage = page;
    loadJobs(true);
}

/**
 * Update jobs UI (table and recent jobs)
 */
export function updateJobsUI() {
    // Update jobs count badge
    const jobsCountEl = document.getElementById('jobs-count');
    if (jobsCountEl) {
        jobsCountEl.textContent = STATE.jobs.length;
    }

    // Update recent jobs in overview
    const recentJobsContainer = document.getElementById('recent-jobs');
    if (recentJobsContainer) {
        if (STATE.jobs.length === 0) {
            recentJobsContainer.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <p>No jobs yet</p>
                    <a href="#" class="btn btn-primary btn-sm" data-section="new-job">Create Your First Job</a>
                </div>
            `;
        } else {
            const recentJobs = STATE.jobs.slice(0, 5);
            recentJobsContainer.innerHTML = recentJobs.map(job => `
                <div class="job-item" data-job-id="${escapeHtml(job.job_id)}">
                    <div class="job-info">
                        <div class="job-type-icon">${getTypeIcon(escapeHtml(job.problem_type))}</div>
                        <div class="job-details">
                            <h4>${escapeHtml(job.problem_type)}</h4>
                            <span class="job-meta">${escapeHtml(job.backend)} • ${formatDate(job.created_at)}</span>
                        </div>
                    </div>
                    <div class="job-status">
                        ${job.encrypted ? '<span class="encrypted-badge">🔐</span>' : ''}
                        <span class="status-badge ${escapeHtml(job.status)}">${escapeHtml(job.status)}</span>
                    </div>
                </div>
            `).join('');

            // Add click handlers
            recentJobsContainer.querySelectorAll('.job-item').forEach(item => {
                item.addEventListener('click', () => {
                    if (viewJobDetailsCallback) viewJobDetailsCallback(item.dataset.jobId);
                });
            });
        }
    }

    // Update jobs table
    const tableBody = document.getElementById('jobs-table-body');
    if (tableBody) {
        if (STATE.jobs.length === 0) {
            tableBody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="7">
                        <div class="empty-state">
                            <p>No jobs found</p>
                        </div>
                    </td>
                </tr>
            `;
        } else {
            const filteredJobs = filterJobs(STATE.jobs);
            if (filteredJobs.length === 0) {
                tableBody.innerHTML = `
                    <tr class="empty-row">
                        <td colspan="7">
                            <div class="empty-state">
                                <p>No jobs match your filters</p>
                                <button class="btn btn-outline btn-sm" onclick="clearFilters()">Clear Filters</button>
                            </div>
                        </td>
                    </tr>
                `;
            } else {
                tableBody.innerHTML = filteredJobs.map(job => `
                    <tr class="job-row ${escapeHtml(job.status) === 'running' ? 'pulse-animation' : ''}" data-job-id="${escapeHtml(job.job_id)}">
                        <td class="checkbox-col">
                            <input type="checkbox" class="job-select-checkbox" data-job-id="${escapeHtml(job.job_id)}" 
                                   ${STATE.selectedForCompare.includes(job.job_id) ? 'checked' : ''}
                                   onchange="toggleJobSelection('${escapeHtml(job.job_id)}')">
                        </td>
                        <td class="job-id-cell" title="${escapeHtml(job.job_id)}">${escapeHtml(job.job_id.substring(0, 12))}...</td>
                        <td><span class="type-badge ${escapeHtml(job.problem_type.toLowerCase())}">${getTypeIcon(escapeHtml(job.problem_type))} ${escapeHtml(job.problem_type)}</span></td>
                        <td><span class="backend-badge">${escapeHtml(job.backend)}</span></td>
                        <td><span class="status-badge ${escapeHtml(job.status)}">${getStatusIcon(escapeHtml(job.status))} ${escapeHtml(job.status)}</span></td>
                        <td>${job.encrypted ? '<span class="encrypted-badge">🔐 Encrypted</span>' : '<span class="text-muted">—</span>'}</td>
                        <td>${formatDate(job.created_at)}</td>
                        <td class="actions-cell">
                            <button class="btn btn-outline btn-sm" onclick="viewJobDetails('${escapeHtml(job.job_id)}')" title="View Details">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="btn btn-outline btn-sm" onclick="exportJob('${escapeHtml(job.job_id)}')" title="Export">
                                <i class="fas fa-download"></i>
                            </button>
                        </td>
                    </tr>
                `).join('');

                // Update compare button visibility
                updateCompareButton();
            }
        }
    }
}

/**
 * Update stats display
 */
export function updateStats() {
    const total = STATE.jobs.length;
    const completed = STATE.jobs.filter(j => j.status === 'completed').length;
    const pending = STATE.jobs.filter(j => j.status === 'pending').length;
    const running = STATE.jobs.filter(j => j.status === 'running').length;
    const failed = STATE.jobs.filter(j => j.status === 'failed').length;
    const encrypted = STATE.jobs.filter(j => j.encrypted).length;

    const statTotal = document.getElementById('stat-total');
    const statCompleted = document.getElementById('stat-completed');
    const statRunning = document.getElementById('stat-running');
    const statEncrypted = document.getElementById('stat-encrypted');

    if (statTotal) statTotal.textContent = total;
    if (statCompleted) statCompleted.textContent = completed;
    if (statRunning) statRunning.textContent = running + pending;
    if (statEncrypted) statEncrypted.textContent = encrypted;

    // Update status pie chart
    if (updateStatusPieChartCallback) {
        updateStatusPieChartCallback({ completed, running, pending, failed });
    }
}

/**
 * Update compare button visibility
 */
function updateCompareButton() {
    const btn = document.getElementById('compare-jobs-btn');
    const countSpan = document.getElementById('compare-count');

    if (btn && countSpan) {
        countSpan.textContent = STATE.selectedForCompare.length;
        btn.style.display = STATE.selectedForCompare.length >= 2 ? 'inline-flex' : 'none';
    }
}

/**
 * Export a single job
 */
export function exportJob(jobId, format = 'json') {
    const job = STATE.jobs.find(j => j.job_id === jobId);
    if (!job) return;

    if (format === 'csv') {
        exportJobAsCSVSingle(job);
    } else {
        const dataStr = JSON.stringify(job, null, 2);
        const blob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = `${job.job_id}_${job.problem_type}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showToast('success', 'Exported', `Job ${jobId.substring(0, 8)} exported as JSON`);
    }
}

/**
 * Export single job as CSV
 */
function exportJobAsCSVSingle(job) {
    const headers = ['Job ID', 'Problem Type', 'Backend', 'Status', 'Created', 'Encrypted', 'Optimal Value', 'Iterations', 'Execution Time'];
    const values = [
        job.job_id,
        job.problem_type,
        job.backend,
        job.status,
        job.created_at,
        job.encrypted ? 'Yes' : 'No',
        job.result?.optimal_value || '',
        job.result?.iterations || (job.result?.convergence_history?.length || ''),
        job.result?.execution_time || ''
    ];

    const csvContent = [headers.join(','), values.map(v => `"${v}"`).join(',')].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `${job.job_id}_${job.problem_type}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast('success', 'Exported', `Job ${job.job_id.substring(0, 8)} exported as CSV`);
}

/**
 * Export all jobs
 */
export function exportAllJobs() {
    if (STATE.jobs.length === 0) {
        showToast('info', 'No Jobs', 'There are no jobs to export');
        return;
    }

    const filteredJobs = filterJobs(STATE.jobs);
    const dataStr = JSON.stringify(filteredJobs, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `quantum_jobs_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast('success', 'Exported', `${filteredJobs.length} jobs exported successfully`);
}

/**
 * Export jobs as CSV
 */
export function exportJobAsCSV(jobs) {
    const headers = ['job_id', 'problem_type', 'backend', 'status', 'encrypted', 'created_at', 'optimal_value'];
    const rows = jobs.map(job => [
        job.job_id,
        job.problem_type,
        job.backend,
        job.status,
        job.encrypted ? 'Yes' : 'No',
        job.created_at,
        job.result?.optimal_value || ''
    ]);

    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `quantum_jobs_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/**
 * Clone a job with the same configuration
 */
export async function cloneJob(jobId) {
    const job = STATE.jobs.find(j => j.job_id === jobId);
    if (!job) {
        showToast('error', 'Error', 'Job not found');
        return;
    }

    showToast('info', 'Cloning', 'Creating a copy of this job...');

    try {
        // Prepare the job submission with the same config
        const newJobData = {
            problem_type: job.problem_type,
            backend: job.backend,
            encrypted: job.encrypted,
            problem_config: { ...job.problem_config }
        };

        const result = await apiPost('/jobs', newJobData);
        showToast('success', 'Job Cloned', `New job created: ${result.job_id.substring(0, 8)}`);
        await loadJobs();
        if (viewJobDetailsCallback) viewJobDetailsCallback(result.job_id);
    } catch (error) {
        console.error('Clone job error:', error);
        showToast('error', 'Clone Failed', error.message);
    }
}

/**
 * Copy solution to clipboard
 */
export function copySolution() {
    const solutionEl = document.getElementById('result-solution');
    if (solutionEl) {
        const text = solutionEl.textContent;
        navigator.clipboard.writeText(text).then(() => {
            showToast('success', 'Copied', 'Solution copied to clipboard');
        }).catch(err => {
            console.error('Copy failed:', err);
            showToast('error', 'Copy Failed', 'Could not copy to clipboard');
        });
    }
}

/**
 * Export convergence chart as PNG
 */
export function exportChartAsPNG() {
    const canvas = document.getElementById('convergence-chart');
    if (!canvas) {
        showToast('error', 'Error', 'No chart available to export');
        return;
    }

    const url = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = url;
    a.download = `convergence_chart_${STATE.selectedJobId?.substring(0, 8) || 'job'}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    showToast('success', 'Exported', 'Chart exported as PNG');
}

// Initialize export dropdown toggle
document.addEventListener('click', (e) => {
    const dropdown = document.querySelector('.export-dropdown');
    const toggleBtn = document.getElementById('export-dropdown-btn');

    if (toggleBtn && toggleBtn.contains(e.target)) {
        e.preventDefault();
        dropdown.classList.toggle('open');
    } else if (dropdown && !dropdown.contains(e.target)) {
        dropdown.classList.remove('open');
    }
});

// Make functions globally accessible
window.loadJobs = loadJobs;
window.goToPage = goToPage;
window.exportJob = exportJob;
window.exportAllJobs = exportAllJobs;
window.cloneJob = cloneJob;
window.copySolution = copySolution;
window.exportChartAsPNG = exportChartAsPNG;
