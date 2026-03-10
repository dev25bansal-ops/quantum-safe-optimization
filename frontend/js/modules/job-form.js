/**
 * Job Form Module
 * Handles job creation form and submission
 */

import { CONFIG, STATE, ANSATZ_MAPPING, JOB_TEMPLATES } from './config.js';
import { showToast } from './toast.js';
import { addNotification } from './notifications.js';
import { navigateToSection } from './navigation.js';
import { updateJobsUI } from './jobs.js';
import { apiPost } from './api.js';

// Forward declarations for callbacks
let loadJobsCallback = null;

export function setJobFormCallbacks(loadJobs) {
    loadJobsCallback = loadJobs;
}

/**
 * Initialize job form handlers
 */
export function initJobForm() {
    const form = document.getElementById('job-form');
    const problemType = document.getElementById('problem-type');
    const backendSelect = document.getElementById('backend');
    const advancedSimSection = document.getElementById('advanced-simulator-config');

    // Show/hide config sections based on problem type
    if (problemType) {
        problemType.addEventListener('change', () => {
            document.querySelectorAll('.config-section').forEach(sec => {
                sec.style.display = 'none';
            });

            const selectedConfig = document.getElementById(`config-${problemType.value.toLowerCase()}`);
            if (selectedConfig) {
                selectedConfig.style.display = 'block';
            }

            // Update backend options for annealing
            const backendSelect = document.getElementById('backend');
            if (problemType.value === 'ANNEALING') {
                if (!['local_simulator', 'advanced_simulator', 'dwave'].includes(backendSelect.value)) {
                    backendSelect.value = 'dwave';
                }
            }

            if (advancedSimSection) {
                advancedSimSection.style.display = backendSelect.value === 'advanced_simulator' ? 'block' : 'none';
            }
        });
    }

    if (backendSelect) {
        backendSelect.addEventListener('change', () => {
            if (advancedSimSection) {
                advancedSimSection.style.display = backendSelect.value === 'advanced_simulator' ? 'block' : 'none';
            }
        });
    }

    // Preview button
    document.getElementById('preview-job')?.addEventListener('click', () => {
        const jobData = buildJobData();
        document.getElementById('preview-json').textContent = JSON.stringify(jobData, null, 2);
        document.getElementById('preview-modal').classList.add('active');
    });

    // Form submission
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await submitJob();
        });
    }

    if (advancedSimSection && backendSelect) {
        advancedSimSection.style.display = backendSelect.value === 'advanced_simulator' ? 'block' : 'none';
    }
}

/**
 * Build job data from form
 */
export function buildJobData() {
    const problemType = document.getElementById('problem-type').value;
    const backend = document.getElementById('backend').value;
    const encrypt = document.getElementById('encrypt-data').checked;
    const sign = document.getElementById('sign-request').checked;

    let problemConfig = {};

    switch (problemType) {
        case 'QAOA':
            let qaoaGraph = [];
            try {
                qaoaGraph = JSON.parse(document.getElementById('qaoa-graph').value || '[]');
            } catch (e) {
                showToast('error', 'Invalid Graph JSON', 'Please enter valid JSON for the graph field');
                document.getElementById('qaoa-graph')?.focus();
                throw new Error('Invalid graph JSON format');
            }
            problemConfig = {
                problem_instance: document.getElementById('qaoa-problem').value,
                p_layers: parseInt(document.getElementById('qaoa-layers').value),
                optimizer: document.getElementById('qaoa-optimizer').value,
                shots: parseInt(document.getElementById('qaoa-shots').value),
                graph: qaoaGraph
            };
            break;

        case 'VQE':
            const ansatzValue = document.getElementById('vqe-ansatz').value.toLowerCase();
            problemConfig = {
                molecule: document.getElementById('vqe-molecule').value,
                ansatz: ANSATZ_MAPPING[ansatzValue] || 'hardware_efficient',
                optimizer: document.getElementById('vqe-optimizer').value,
                shots: parseInt(document.getElementById('vqe-shots').value)
            };
            break;

        case 'ANNEALING':
            let quboMatrix = [];
            try {
                quboMatrix = JSON.parse(document.getElementById('anneal-matrix').value || '[]');
            } catch (e) {
                showToast('error', 'Invalid Matrix JSON', 'Please enter valid JSON for the QUBO matrix field');
                document.getElementById('anneal-matrix')?.focus();
                throw new Error('Invalid QUBO matrix JSON format');
            }
            problemConfig = {
                formulation: document.getElementById('anneal-formulation').value,
                num_reads: parseInt(document.getElementById('anneal-reads').value),
                annealing_time: parseInt(document.getElementById('anneal-time').value),
                chain_strength: parseFloat(document.getElementById('anneal-chain').value),
                qubo_matrix: quboMatrix
            };
            break;
    }

    // Get optional fields
    const priority = document.getElementById('job-priority')?.value || 'normal';
    const callbackUrl = document.getElementById('callback-url')?.value?.trim() || null;

    const jobData = {
        problem_type: problemType,
        problem_config: problemConfig,
        backend: backend,
        encrypted: encrypt,
        signed: sign,
        priority: priority
    };

    if (backend === 'advanced_simulator') {
        jobData.simulator_config = {
            simulator_type: document.getElementById('simulator-type')?.value || 'statevector',
            noise_model: document.getElementById('noise-model')?.value || 'ideal',
            enable_readout_mitigation: document.getElementById('enable-readout-mitigation')?.checked || false,
            enable_zne: document.getElementById('enable-zne')?.checked || false,
            precision: document.getElementById('sim-precision')?.value || 'double',
            max_parallel_circuits: parseInt(document.getElementById('max-parallel')?.value || '4', 10),
            use_caching: document.getElementById('enable-caching')?.checked !== false,
        };
    }

    // Only include callback_url if provided
    if (callbackUrl) {
        jobData.callback_url = callbackUrl;
    }

    return jobData;
}

/**
 * Submit job to API
 */
export async function submitJob() {
    const jobData = buildJobData();
    const submitBtn = document.querySelector('#job-form button[type="submit"]');
    const originalBtnContent = submitBtn?.innerHTML;

    // Check if user is authenticated before submitting
    // Check both storage types for backwards compatibility
    const token = sessionStorage.getItem('authToken') || localStorage.getItem('authToken');

    try {
        // Show loading state on button
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
        }

        // If no auth token, skip the API call and go straight to demo mode
        if (!token) {
            throw new TypeError('No auth token - using demo mode');
        }

        showToast('info', 'Submitting Job', 'Sending to quantum backend...');

        const result = await apiPost('/jobs', jobData);

        showToast('success', 'Job Submitted', `Job ID: ${result.job_id}`);

        // Add notification for successful job submission
        addNotification('success', 'Job Submitted', `${jobData.problem_type} job created`, result.job_id);

        // Reset form and navigate to jobs
        document.getElementById('job-form').reset();
        document.querySelectorAll('.config-section').forEach(sec => {
            sec.style.display = 'none';
        });

        // Refresh jobs and navigate
        if (loadJobsCallback) await loadJobsCallback();
        navigateToSection('jobs');

    } catch (error) {
        console.error('Job submission failed:', error);

        // Check if this is a demo mode / API unavailable scenario
        const isApiUnavailable =
            error.message.includes('Failed to fetch') ||
            error.message.includes('NetworkError') ||
            error.message.includes('501') ||
            error.message.includes('405') ||
            error.name === 'TypeError';

        if (isApiUnavailable) {
            // Create a demo job locally
            const demoJobId = 'demo-' + Date.now().toString(36) + Math.random().toString(36).substr(2, 5);

            // Enhance problem_config with fields needed for display
            const enhancedConfig = {
                ...jobData.problem_config,
                num_qubits: jobData.problem_config?.graph?.length ||
                    jobData.problem_config?.num_qubits || 4,
                depth: jobData.problem_config?.p_layers ||
                    jobData.problem_config?.depth || 2
            };

            const demoJob = {
                job_id: demoJobId,
                problem_type: jobData.problem_type,
                status: 'completed',
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                encrypted: jobData.encrypted,
                backend: jobData.backend,
                problem_config: enhancedConfig,
                result: generateDemoResult(jobData)
            };

            // Add to STATE
            STATE.jobs.unshift(demoJob);
            STATE.totalJobs = STATE.jobs.length;

            // Update the jobs UI to show the new job
            updateJobsUI();

            showToast('success', 'Demo Job Created', `Job ID: ${demoJobId} (demo mode)`);
            addNotification('success', 'Demo Job Created', `${jobData.problem_type} job simulated`, demoJobId);

            // Reset form and navigate to jobs
            document.getElementById('job-form').reset();
            document.querySelectorAll('.config-section').forEach(sec => {
                sec.style.display = 'none';
            });

            navigateToSection('jobs');
        } else {
            // Provide user-friendly guidance for common errors
            let errorMsg = error.message || 'An error occurred';
            if (errorMsg.includes('ML-KEM') || errorMsg.includes('public key')) {
                errorMsg = 'PQC encryption requires a registered key. Uncheck "Encrypt with ML-KEM-768" or register a key first.';
            }
            showToast('error', 'Submission Failed', errorMsg);
            addNotification('error', 'Submission Failed', errorMsg);
        }
    } finally {
        // Restore button state
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnContent || '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg> Submit Job';
        }
    }
}

/**
 * Generate demo result for a job
 */
function generateDemoResult(jobData) {
    const numQubits = jobData.problem_config?.graph?.length || 4;
    const pLayers = jobData.problem_config?.p_layers || 2;
    const bitstring = Array(numQubits).fill(0).map(() => Math.random() > 0.5 ? '1' : '0').join('');

    // Generate convergence history with a clearer trend
    const convergenceHistory = Array(20).fill(0).map((_, i) => {
        const base = -7 + (i / 20) * 4;  // Start at -7, end around -3
        const noise = (Math.random() - 0.5) * 0.5;
        return base + noise;
    });

    // Generate optimal params (gamma and beta arrays)
    const optimalParams = {
        gamma: Array(pLayers).fill(0).map(() => Math.random() * Math.PI),
        beta: Array(pLayers).fill(0).map(() => Math.random() * Math.PI / 2)
    };

    // Generate energy levels for distribution chart
    const energyLevels = Array(50).fill(0).map(() => -Math.random() * 5 - 2);

    // Generate probabilities
    const numStates = Math.min(16, Math.pow(2, numQubits));
    const probabilities = {};
    let totalProb = 0;
    for (let i = 0; i < numStates; i++) {
        const state = i.toString(2).padStart(numQubits, '0');
        const prob = Math.random();
        probabilities[state] = prob;
        totalProb += prob;
    }
    // Normalize probabilities
    Object.keys(probabilities).forEach(key => {
        probabilities[key] = probabilities[key] / totalProb;
    });

    return {
        optimal_bitstring: bitstring,
        optimal_value: parseFloat(convergenceHistory[convergenceHistory.length - 1].toFixed(4)),
        convergence_history: convergenceHistory,
        energy_levels: energyLevels,
        optimal_params: optimalParams,
        execution_time: (Math.random() * 2 + 0.5).toFixed(3),
        probabilities: probabilities,
        iterations: 20,
        final_energy: parseFloat(convergenceHistory[convergenceHistory.length - 1].toFixed(4))
    };
}

/**
 * Load a job template
 */
export function loadTemplate(templateId) {
    const template = JOB_TEMPLATES[templateId];
    if (!template) return;

    // Set problem type
    const problemType = document.getElementById('problem-type');
    problemType.value = template.type;
    problemType.dispatchEvent(new Event('change'));

    // Wait for config section to show
    setTimeout(() => {
        switch (template.type) {
            case 'QAOA':
                document.getElementById('qaoa-problem').value = template.config.problem || 'MaxCut';
                document.getElementById('qaoa-layers').value = template.config.layers || 2;
                document.getElementById('qaoa-optimizer').value = template.config.optimizer || 'COBYLA';
                document.getElementById('qaoa-shots').value = template.config.shots || 1000;
                document.getElementById('qaoa-graph').value = JSON.stringify(template.config.graph || []);
                break;

            case 'VQE':
                document.getElementById('vqe-molecule').value = template.config.molecule || 'H2';
                document.getElementById('vqe-ansatz').value = template.config.ansatz || 'hardware_efficient';
                document.getElementById('vqe-optimizer').value = template.config.optimizer || 'COBYLA';
                document.getElementById('vqe-shots').value = template.config.shots || 1000;
                break;

            case 'ANNEALING':
                document.getElementById('backend').value = 'local_simulator';
                document.getElementById('anneal-formulation').value = template.config.formulation || 'QUBO';
                document.getElementById('anneal-reads').value = template.config.reads || 100;
                document.getElementById('anneal-time').value = template.config.time || 20;
                document.getElementById('anneal-chain').value = template.config.chain || 1.0;
                document.getElementById('anneal-matrix').value = JSON.stringify(template.config.matrix || []);
                break;
        }

        showToast('success', 'Template Loaded', `${template.name} configuration applied`);
    }, 100);
}

// Make functions globally accessible
window.loadTemplate = loadTemplate;
window.buildJobData = buildJobData;
window.submitJob = submitJob;
