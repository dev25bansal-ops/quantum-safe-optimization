/**
 * Job Details Module
 * Handles job detail view, timeline, and actions
 */

import { CONFIG, STATE } from './config.js';
import { escapeHtml, formatDate, formatTimeShort, getAuthHeaders } from './utils.js';
import { showToast } from './toast.js';
import { navigateToSection } from './navigation.js';
import { apiPost, apiDelete, apiGet } from './api.js';

// Forward declarations for callbacks
let loadJobsCallback = null;
let connectWebSocketCallback = null;
let updateVisualizationsCallback = null;
let initConvergenceChartCallback = null;

export function setJobDetailsCallbacks(loadJobs, connectWebSocket, updateVisualizations, initChart) {
    loadJobsCallback = loadJobs;
    connectWebSocketCallback = connectWebSocket;
    updateVisualizationsCallback = updateVisualizations;
    initConvergenceChartCallback = initChart;
}

/**
 * View job details
 */
export function viewJobDetails(jobId) {
    const job = STATE.jobs.find(j => j.job_id === jobId);
    if (!job) return;

    STATE.selectedJobId = jobId;

    // Update job header
    document.getElementById('job-detail-title').textContent = `${job.problem_type} Optimization Job`;
    document.getElementById('job-detail-breadcrumb').textContent = `${job.problem_type} Job`;

    // Update job ID badge
    const jobIdEl = document.getElementById('job-detail-id');
    if (jobIdEl) {
        const codeEl = jobIdEl.querySelector('code');
        if (codeEl) {
            codeEl.textContent = job.job_id.substring(0, 12) + '...';
        } else {
            jobIdEl.textContent = job.job_id;
        }
    }

    // Update status pill with proper class
    const statusPill = document.getElementById('job-detail-status');
    if (statusPill) {
        statusPill.className = `status-pill ${job.status}`;
        const statusText = statusPill.querySelector('.status-text');
        if (statusText) {
            statusText.textContent = job.status.charAt(0).toUpperCase() + job.status.slice(1);
        } else {
            statusPill.textContent = job.status;
        }
    }

    // Update job type badge
    const typeBadge = document.getElementById('job-type-badge');
    const typeLabel = document.getElementById('detail-type-label');
    if (typeLabel) typeLabel.textContent = job.problem_type;

    // Set type icon based on problem type
    if (typeBadge) {
        const typeIconEl = typeBadge.querySelector('.type-icon');
        if (typeIconEl) {
            const icons = {
                'QAOA': '⚛️',
                'VQE': '🔬',
                'Grover': '🔍',
                'Shor': '🔢',
                'default': '🌀'
            };
            typeIconEl.textContent = icons[job.problem_type] || icons.default;
        }
    }

    document.getElementById('detail-type').textContent = job.problem_type;
    document.getElementById('detail-backend').textContent = job.backend;
    document.getElementById('detail-created').textContent = formatDate(job.created_at);

    // Update encrypted status with icon
    const encryptedEl = document.getElementById('detail-encrypted');
    if (encryptedEl) {
        if (job.encrypted) {
            encryptedEl.innerHTML = '<i class="fas fa-shield-alt"></i> PQC Enabled';
            encryptedEl.classList.add('security-badge');
        } else {
            encryptedEl.textContent = 'Standard';
            encryptedEl.classList.remove('security-badge');
        }
    }

    // Update backend param in sidebar
    const backendParam = document.getElementById('detail-backend-param');
    if (backendParam) backendParam.textContent = job.backend;

    // Show qubits and layers info
    const qubitsEl = document.getElementById('detail-qubits');
    const layersEl = document.getElementById('detail-layers');
    if (qubitsEl) {
        const qubits = job.problem_config?.num_qubits || job.problem_config?.graph?.length || '-';
        qubitsEl.textContent = qubits;
    }
    if (layersEl) {
        const layers = job.problem_config?.p_layers || job.problem_config?.depth || job.problem_config?.layers || '-';
        layersEl.textContent = layers;
    }

    document.getElementById('detail-config').textContent = JSON.stringify(job.problem_config || {}, null, 2);

    // Update timeline based on job status
    updateJobTimeline(job);

    // Show results if completed
    const resultsSection = document.getElementById('results-section');
    const chartSection = document.getElementById('chart-section');
    const additionalStats = document.getElementById('additional-stats');

    if (job.status === 'completed' && job.result) {
        resultsSection.style.display = 'block';
        document.getElementById('result-optimal').textContent = job.result.optimal_value?.toFixed(6) || '-';

        // Show optimal solution - could be optimal_bitstring, optimal_solution, or optimal_params
        const solution = job.result.optimal_bitstring || job.result.optimal_solution || job.result.optimal_params;
        document.getElementById('result-solution').textContent = solution ?
            (typeof solution === 'string' ? solution : JSON.stringify(solution, null, 2)) : '-';

        // Show iterations from convergence_history length
        const iterations = job.result.iterations ||
            (job.result.convergence_history ? job.result.convergence_history.length : null);
        document.getElementById('result-iterations').textContent = iterations || '-';

        // Calculate execution time from timestamps
        let execTime = job.result.execution_time;
        if (!execTime && job.result.submitted_at && job.result.completed_at) {
            const start = new Date(job.result.submitted_at);
            const end = new Date(job.result.completed_at);
            execTime = ((end - start) / 1000).toFixed(2);
        }
        document.getElementById('result-time').textContent = execTime ? `${execTime}s` : '-';

        // Calculate improvement (from initial to final value)
        const improvementEl = document.getElementById('result-improvement');
        if (improvementEl && job.result.convergence_history && job.result.convergence_history.length > 1) {
            const initial = job.result.convergence_history[0];
            const final = job.result.convergence_history[job.result.convergence_history.length - 1];
            const improvement = ((Math.abs(final - initial) / Math.abs(initial)) * 100).toFixed(1);
            improvementEl.textContent = `${improvement}%`;
            improvementEl.style.color = 'var(--success)';
        } else if (improvementEl) {
            improvementEl.textContent = '-';
        }

        // Show additional statistics if available
        if (additionalStats && job.result.statistics) {
            additionalStats.style.display = 'block';
            document.getElementById('stat-mean').textContent = job.result.statistics.mean?.toFixed(6) || '-';
            document.getElementById('stat-std').textContent = job.result.statistics.std?.toFixed(6) || '-';
            document.getElementById('stat-best').textContent = job.result.statistics.best_sample || '-';
            document.getElementById('stat-success-rate').textContent =
                job.result.statistics.success_rate ? `${(job.result.statistics.success_rate * 100).toFixed(1)}%` : '-';
        } else if (additionalStats) {
            additionalStats.style.display = 'none';
        }

        // Show convergence chart if data available
        if (job.result.convergence_history && job.result.convergence_history.length > 0 && chartSection) {
            chartSection.style.display = 'block';
            if (initConvergenceChartCallback) {
                initConvergenceChartCallback('convergence-chart', job.result.convergence_history);
            }
        } else if (chartSection) {
            chartSection.style.display = 'none';
        }
    } else {
        resultsSection.style.display = 'none';
        if (chartSection) chartSection.style.display = 'none';
        if (additionalStats) additionalStats.style.display = 'none';
    }

    // Show progress bar for running jobs
    const progressSection = document.getElementById('progress-section');
    if (progressSection) {
        if (job.status === 'running' || job.status === 'pending') {
            progressSection.style.display = 'block';
            const progressBar = document.getElementById('job-progress-bar');
            const progressText = document.getElementById('job-progress-text');
            if (progressBar && progressText) {
                const progress = job.progress || (job.status === 'pending' ? 5 : 50);
                progressBar.style.width = `${progress}%`;
                progressText.textContent = job.status === 'pending' ? 'Queued...' : 'Processing...';
            }
        } else {
            progressSection.style.display = 'none';
        }
    }

    // Show/hide cancel and retry buttons based on job status
    const cancelBtn = document.getElementById('cancel-job');
    const retryBtn = document.getElementById('retry-job');
    if (cancelBtn) {
        cancelBtn.style.display = (job.status === 'pending' || job.status === 'running') ? 'inline-flex' : 'none';
    }
    if (retryBtn) {
        retryBtn.style.display = job.status === 'failed' ? 'inline-flex' : 'none';
    }

    // Connect WebSocket for real-time updates if job is running
    if ((job.status === 'running' || job.status === 'pending') && connectWebSocketCallback) {
        connectWebSocketCallback(jobId);
    }

    // Update visualizations (charts, graphs)
    if (updateVisualizationsCallback) {
        updateVisualizationsCallback(job);
    }

    navigateToSection('job-details');
}

/**
 * Update job timeline visualization
 */
export function updateJobTimeline(job) {
    const steps = ['created', 'queued', 'processing', 'completed'];
    const statusMap = {
        'pending': 1,     // Created + Queued active
        'running': 2,     // Created + Queued complete, Processing active
        'completed': 3,   // All complete
        'failed': 2       // Failed at processing
    };

    const currentStep = statusMap[job.status] || 0;

    steps.forEach((step, index) => {
        const stepEl = document.getElementById(`timeline-${step}`);
        // Support both old (.timeline-icon) and new (.stage-indicator) structures
        const indicatorEl = stepEl?.querySelector('.stage-indicator') || stepEl?.querySelector('.timeline-icon');
        const timeEl = document.getElementById(`timeline-${step}-time`);
        const connectorEl = document.getElementById(`timeline-connector-${index + 1}`);

        if (indicatorEl) {
            indicatorEl.classList.remove('completed', 'active', 'failed');

            if (index < currentStep) {
                indicatorEl.classList.add('completed');
            } else if (index === currentStep) {
                if (job.status === 'failed' && step === 'completed') {
                    indicatorEl.classList.add('failed');
                    const iconEl = indicatorEl.querySelector('.stage-icon') || indicatorEl;
                    if (iconEl) iconEl.innerHTML = '<i class="fas fa-times-circle"></i>';
                    if (timeEl) timeEl.textContent = 'Failed';
                } else {
                    indicatorEl.classList.add('active');
                }
            }
        }

        if (connectorEl) {
            connectorEl.classList.remove('completed', 'active');
            if (index < currentStep) {
                connectorEl.classList.add('completed');
            } else if (index === currentStep - 1) {
                connectorEl.classList.add('active');
            }
        }

        // Set timestamps
        if (timeEl && step !== 'completed') {
            switch (step) {
                case 'created':
                    timeEl.textContent = job.created_at ? formatTimeShort(job.created_at) : '-';
                    break;
                case 'queued':
                    timeEl.textContent = job.queued_at ? formatTimeShort(job.queued_at) :
                        (currentStep >= 1 ? 'Queued' : '-');
                    break;
                case 'processing':
                    timeEl.textContent = job.started_at ? formatTimeShort(job.started_at) :
                        (currentStep >= 2 ? 'Processing' : '-');
                    break;
            }
        } else if (timeEl && step === 'completed') {
            if (job.status === 'completed') {
                timeEl.textContent = job.completed_at ? formatTimeShort(job.completed_at) : 'Done';
                const iconEl = stepEl?.querySelector('.stage-icon') || stepEl?.querySelector('.timeline-icon');
                if (iconEl) iconEl.innerHTML = '<i class="fas fa-check-double"></i>';
            } else if (job.status === 'failed') {
                timeEl.textContent = 'Failed';
            } else {
                timeEl.textContent = '-';
            }
        }
    });
}

/**
 * Toggle config panel collapse
 */
export function toggleConfigPanel() {
    const configPanel = document.getElementById('config-panel');
    const collapseIcon = document.getElementById('config-collapse-icon');
    if (configPanel) {
        configPanel.classList.toggle('collapsed');
        if (collapseIcon) {
            collapseIcon.style.transform = configPanel.classList.contains('collapsed') ? 'rotate(-90deg)' : 'rotate(0)';
        }
    }
}

/**
 * Initialize job detail action handlers
 */
export function initJobDetailActions() {
    // Refresh job details
    document.getElementById('refresh-job')?.addEventListener('click', async () => {
        if (STATE.selectedJobId) {
            if (loadJobsCallback) await loadJobsCallback();
            viewJobDetails(STATE.selectedJobId);
            showToast('info', 'Refreshed', 'Job status updated');
        }
    });

    // Cancel job
    document.getElementById('cancel-job')?.addEventListener('click', async () => {
        if (!STATE.selectedJobId) return;

        if (!confirm('Are you sure you want to cancel this job?')) return;

        try {
            await apiDelete(`/jobs/${STATE.selectedJobId}`);

            showToast('success', 'Job Cancelled', 'The job has been cancelled');
            if (loadJobsCallback) await loadJobsCallback();
            viewJobDetails(STATE.selectedJobId);
        } catch (error) {
            showToast('error', 'Cancel Failed', error.message || 'Failed to cancel job');
        }
    });

    // Retry job
    document.getElementById('retry-job')?.addEventListener('click', async () => {
        if (!STATE.selectedJobId) return;

        try {
            const data = await apiPost(`/jobs/${STATE.selectedJobId}/retry`, {});

            showToast('success', 'Job Restarted', `New job ID: ${data.job_id?.substring(0, 8) || 'created'}`);
            if (loadJobsCallback) await loadJobsCallback();

            // Navigate to new job if different ID returned
            if (data.job_id && data.job_id !== STATE.selectedJobId) {
                viewJobDetails(data.job_id);
            } else {
                viewJobDetails(STATE.selectedJobId);
            }
        } catch (error) {
            showToast('error', 'Retry Failed', error.message || 'Failed to retry job');
        }
    });
}

// Make functions globally accessible
window.viewJobDetails = viewJobDetails;
window.toggleConfigPanel = toggleConfigPanel;
