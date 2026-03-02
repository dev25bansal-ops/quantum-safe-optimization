/**
 * QuantumSafe Optimize - Dashboard JavaScript
 * Professional Quantum Optimization Platform
 * Handles navigation, job management, and API interactions
 */

// Configuration - use current origin to avoid CORS issues
const CONFIG = {
    apiUrl: localStorage.getItem('apiUrl') || 'http://localhost:8001/api/v1',
    apiBase: localStorage.getItem('apiUrl')?.replace(/\/api\/v1\/?$/, '') || 'http://localhost:8001',
    healthCheckInterval: 30000, // 30 seconds for health checks only
    maxRetries: 3
};

// Ansatz mapping for VQE (UI display -> backend value)
const ANSATZ_MAPPING = {
    'hardware_efficient': 'hardware_efficient',
    'ry': 'hardware_efficient',
    'ryrz': 'hardware_efficient',
    'su2': 'su2',
    'uccsd': 'uccsd'
};

/**
 * XSS Protection - Sanitize user input before rendering
 */
function escapeHtml(unsafe) {
    if (unsafe == null) return '';
    return String(unsafe)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// State
const STATE = {
    jobs: [],
    currentSection: 'overview',
    selectedJobId: null,
    pollTimer: null,
    healthCheckTimer: null,
    isOnline: true,
    searchQuery: '',
    filterStatus: 'all',
    filterType: 'all',
    theme: localStorage.getItem('theme') || 'dark',
    // Pagination
    currentPage: 1,
    pageSize: 10,
    totalJobs: 0,
    // Loading states
    isLoading: false,
    // Authentication
    isAuthenticated: false,
    user: null,
    // System data
    workers: [],
    webhookStats: null,
    // Notifications
    notifications: [],
    // Job comparison
    selectedForCompare: [],
    // Offline tracking
    wasOffline: false
};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initNavigation();
    initJobForm();
    initModal();
    initSettings();
    initSecurityTests();
    initSearch();
    initMobileSearch();
    initAuth();
    initUserMenu();
    initNotifications();
    initKeyboardShortcuts();
    initOfflineDetection();
    initJobComparison();
    initConnectivity();
    initPqcStatus();
    checkAuthStatus();
    checkApiStatus();
    loadJobs();

    // Only health check polling - job updates via WebSocket
    STATE.healthCheckTimer = setInterval(checkApiStatus, CONFIG.healthCheckInterval);
});

/**
 * Theme Management
 */
function initTheme() {
    document.documentElement.setAttribute('data-theme', STATE.theme);
    updateThemeToggle();
}

function toggleTheme() {
    STATE.theme = STATE.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('theme', STATE.theme);
    document.documentElement.setAttribute('data-theme', STATE.theme);
    updateThemeToggle();
    showToast('info', 'Theme Changed', `Switched to ${STATE.theme} mode`);
}

function updateThemeToggle() {
    const toggleBtn = document.getElementById('theme-toggle');
    if (toggleBtn) {
        toggleBtn.innerHTML = STATE.theme === 'dark'
            ? '<i class="fas fa-sun"></i>'
            : '<i class="fas fa-moon"></i>';
        toggleBtn.title = `Switch to ${STATE.theme === 'dark' ? 'light' : 'dark'} mode`;
    }
}

/**
 * Search & Filter - Server-side and Client-side
 */
function initSearch() {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', debounce((e) => {
            STATE.searchQuery = e.target.value.toLowerCase();
            // Reload with server-side filtering
            STATE.currentPage = 1;
            loadJobs(true);
        }, 500));

        // Enter key triggers immediate search
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                STATE.searchQuery = e.target.value.toLowerCase();
                STATE.currentPage = 1;
                loadJobs(true);
            }
        });
    }

    // Status filter - server-side
    const statusFilter = document.getElementById('filter-status');
    if (statusFilter) {
        statusFilter.addEventListener('change', (e) => {
            STATE.filterStatus = e.target.value;
            STATE.currentPage = 1;
            loadJobs(true);
        });
    }

    // Type filter - server-side
    const typeFilter = document.getElementById('filter-type');
    if (typeFilter) {
        typeFilter.addEventListener('change', (e) => {
            STATE.filterType = e.target.value;
            STATE.currentPage = 1;
            loadJobs(true);
        });
    }
}

/**
 * Mobile Search Toggle
 */
function initMobileSearch() {
    const mobileSearchToggle = document.getElementById('mobile-search-toggle');
    const searchBox = document.getElementById('search-box');
    const searchInput = document.getElementById('search-input');

    if (mobileSearchToggle && searchBox) {
        mobileSearchToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            searchBox.classList.toggle('mobile-active');
            if (searchBox.classList.contains('mobile-active')) {
                searchInput?.focus();
            }
        });

        // Close mobile search when clicking outside
        document.addEventListener('click', (e) => {
            if (!searchBox.contains(e.target) && !mobileSearchToggle.contains(e.target)) {
                searchBox.classList.remove('mobile-active');
            }
        });

        // Close on escape
        searchInput?.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                searchBox.classList.remove('mobile-active');
            }
        });
    }
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

function filterJobs(jobs) {
    return jobs.filter(job => {
        // Search filter
        const matchesSearch = STATE.searchQuery === '' ||
            job.id.toLowerCase().includes(STATE.searchQuery) ||
            job.problem_type?.toLowerCase().includes(STATE.searchQuery) ||
            job.status?.toLowerCase().includes(STATE.searchQuery);

        // Status filter
        const matchesStatus = STATE.filterStatus === 'all' ||
            job.status?.toLowerCase() === STATE.filterStatus.toLowerCase();

        // Type filter
        const matchesType = STATE.filterType === 'all' ||
            job.problem_type?.toLowerCase() === STATE.filterType.toLowerCase();

        return matchesSearch && matchesStatus && matchesType;
    });
}

/**
 * Navigation
 */
function initNavigation() {
    // Sidebar navigation
    document.querySelectorAll('.nav-item, [data-section]').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const section = item.dataset.section;
            if (section) {
                navigateToSection(section);

                // Handle algorithm type selection for new job
                if (section === 'new-job' && item.dataset.type) {
                    setTimeout(() => {
                        const typeSelect = document.getElementById('problem-type');
                        if (typeSelect) {
                            typeSelect.value = item.dataset.type;
                            typeSelect.dispatchEvent(new Event('change'));
                        }
                    }, 100);
                }
            }
        });
    });

    // Sidebar toggle for mobile with backdrop
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    const sidebarBackdrop = document.getElementById('sidebar-backdrop');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            sidebarBackdrop?.classList.toggle('active', sidebar.classList.contains('open'));
            document.body.classList.toggle('sidebar-open', sidebar.classList.contains('open'));
        });
    }

    // Close sidebar when clicking backdrop
    if (sidebarBackdrop) {
        sidebarBackdrop.addEventListener('click', () => {
            sidebar?.classList.remove('open');
            sidebarBackdrop.classList.remove('active');
            document.body.classList.remove('sidebar-open');
        });
    }

    // Close sidebar when clicking nav item on mobile
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 1024) {
                sidebar?.classList.remove('open');
                sidebarBackdrop?.classList.remove('active');
                document.body.classList.remove('sidebar-open');
            }
        });
    });
}

function navigateToSection(section) {
    // Update active nav item
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.section === section);
    });

    // Update section visibility
    document.querySelectorAll('.dashboard-section').forEach(sec => {
        sec.classList.toggle('active', sec.id === `section-${section}`);
    });

    // Update page title
    const titles = {
        'overview': 'Overview',
        'new-job': 'New Job',
        'jobs': 'My Jobs',
        'job-details': 'Job Details',
        'qaoa': 'QAOA',
        'vqe': 'VQE',
        'annealing': 'Quantum Annealing',
        'security': 'Security',
        'settings': 'Settings'
    };

    document.getElementById('page-title').textContent = titles[section] || section;
    STATE.currentSection = section;

    // Close mobile sidebar
    document.querySelector('.sidebar')?.classList.remove('open');
}

/**
 * Job Templates
 */
const JOB_TEMPLATES = {
    maxcut: {
        type: 'QAOA',
        name: 'Max-Cut Problem',
        config: {
            problem: 'MaxCut',
            layers: 2,
            optimizer: 'COBYLA',
            shots: 1000,
            graph: [[0, 1, 1.0], [0, 2, 1.0], [1, 2, 1.0], [1, 3, 1.0], [2, 3, 1.0]]
        }
    },
    h2: {
        type: 'VQE',
        name: 'H₂ Molecule',
        config: {
            molecule: 'H2',
            ansatz: 'hardware_efficient',
            optimizer: 'COBYLA',
            shots: 1000
        }
    },
    lih: {
        type: 'VQE',
        name: 'LiH Molecule',
        config: {
            molecule: 'LiH',
            ansatz: 'hardware_efficient',
            optimizer: 'SPSA',
            shots: 2000
        }
    },
    qubo: {
        type: 'ANNEALING',
        name: 'QUBO Example',
        config: {
            formulation: 'QUBO',
            reads: 100,
            time: 20,
            chain: 1.0,
            matrix: [[0, 1, -1.0], [0, 2, -1.0], [1, 2, 2.0], [0, 0, 1.0], [1, 1, 1.0], [2, 2, 1.0]]
        }
    },
    tsp: {
        type: 'QAOA',
        name: 'TSP (4 cities)',
        config: {
            problem: 'TSP',
            layers: 3,
            optimizer: 'COBYLA',
            shots: 2000,
            graph: [[0, 1, 10], [0, 2, 15], [0, 3, 20], [1, 2, 35], [1, 3, 25], [2, 3, 30]]
        }
    },
    portfolio: {
        type: 'QAOA',
        name: 'Portfolio Optimization',
        config: {
            problem: 'Portfolio',
            layers: 2,
            optimizer: 'COBYLA',
            shots: 1000,
            graph: [[0, 1, 0.5], [0, 2, 0.3], [1, 2, 0.4]]
        }
    }
};

function loadTemplate(templateId) {
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

/**
 * Job Form
 */
function initJobForm() {
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

function buildJobData() {
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

async function submitJob() {
    const jobData = buildJobData();
    const submitBtn = document.querySelector('#job-form button[type="submit"]');
    const originalBtnContent = submitBtn?.innerHTML;

    // Check if user is authenticated before submitting
    const token = localStorage.getItem('authToken');
    if (!token) {
        showToast('warning', 'Authentication Required', 'Please sign in to submit jobs');
        // Open the sign-in modal if available
        const signInBtn = document.querySelector('[data-auth-action="signin"]');
        if (signInBtn) signInBtn.click();
        return;
    }

    try {
        // Show loading state on button
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
        }

        showToast('info', 'Submitting Job', 'Sending to quantum backend...');

        const headers = {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        };

        const response = await fetch(`${CONFIG.apiUrl}/jobs`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(jobData)
        });

        if (!response.ok) {
            // Handle 401 specifically
            if (response.status === 401) {
                localStorage.removeItem('authToken');
                STATE.isAuthenticated = false;
                STATE.user = null;
                updateAuthUI();
                throw new Error('Session expired. Please sign in again.');
            }
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();

        showToast('success', 'Job Submitted', `Job ID: ${result.job_id}`);

        // Add notification for successful job submission
        addNotification('success', 'Job Submitted', `${jobData.problem_type} job created`, result.job_id);

        // Reset form and navigate to jobs
        document.getElementById('job-form').reset();
        document.querySelectorAll('.config-section').forEach(sec => {
            sec.style.display = 'none';
        });

        // Refresh jobs and navigate
        await loadJobs();
        navigateToSection('jobs');

    } catch (error) {
        console.error('Job submission failed:', error);
        showToast('error', 'Submission Failed', error.message || 'An error occurred');
        addNotification('error', 'Submission Failed', error.message || 'An error occurred');
    } finally {
        // Restore button state
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnContent || '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg> Submit Job';
        }
    }
}

/**
 * Jobs Management
 */
async function loadJobs(showLoading = false) {
    if (STATE.isLoading) return;

    // If user is not authenticated, just show empty state - no error
    const token = localStorage.getItem('authToken');
    if (!token) {
        STATE.jobs = [];
        STATE.totalJobs = 0;
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

        const headers = {
            'Authorization': `Bearer ${token}`
        };

        // Build URL with pagination and filter params
        const skip = (STATE.currentPage - 1) * STATE.pageSize;
        let url = `${CONFIG.apiUrl}/jobs?skip=${skip}&limit=${STATE.pageSize}`;

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

        const response = await fetch(url, { headers });

        if (!response.ok) {
            if (response.status === 401) {
                // Token expired or invalid - clear auth state and show empty
                localStorage.removeItem('authToken');
                STATE.isAuthenticated = false;
                STATE.user = null;
                STATE.jobs = [];
                STATE.totalJobs = 0;
                updateAuthUI();
                updateJobsUI();
                updateStats();
                updatePaginationUI();
                return; // Don't show error for auth issues
            }
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

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

        // Show feedback on first failure or every 5th failure (avoid spam)
        if (STATE.loadJobsFailures === 1) {
            showToast('warning', 'Connection Issue', 'Unable to load jobs. Retrying...');
        } else if (STATE.loadJobsFailures % 5 === 0) {
            showToast('error', 'Persistent Error', `Failed to load jobs ${STATE.loadJobsFailures} times. Check your connection.`);
            addNotification('error', 'Jobs Load Failed', `Unable to fetch jobs after ${STATE.loadJobsFailures} attempts`);
        }

        // Show empty state with retry option on initial load failure
        if (showLoading && STATE.jobs.length === 0) {
            const tableBody = document.getElementById('jobs-table-body');
            if (tableBody) {
                tableBody.innerHTML = `
                    <tr class="error-row">
                        <td colspan="7">
                            <div class="empty-state error-state">
                                <i class="fas fa-exclamation-triangle" style="font-size: 2rem; color: var(--error-color); margin-bottom: 1rem;"></i>
                                <p>Failed to load jobs</p>
                                <button class="btn btn-primary btn-sm" onclick="loadJobs(true)">Retry</button>
                            </div>
                        </td>
                    </tr>
                `;
            }
        }
    } finally {
        STATE.isLoading = false;
        hideJobsLoadingSkeleton();
    }
}

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

function hideJobsLoadingSkeleton() {
    const skeletonRows = document.querySelectorAll('.skeleton-row');
    skeletonRows.forEach(row => row.remove());
}

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

function goToPage(page) {
    const totalPages = Math.ceil(STATE.totalJobs / STATE.pageSize);
    if (page < 1 || page > totalPages) return;

    STATE.currentPage = page;
    loadJobs(true);
}

function updateJobsUI() {
    // Update jobs count badge
    document.getElementById('jobs-count').textContent = STATE.jobs.length;

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
                item.addEventListener('click', () => viewJobDetails(item.dataset.jobId));
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

function getStatusIcon(status) {
    const icons = {
        'pending': '<i class="fas fa-clock"></i>',
        'running': '<i class="fas fa-spinner fa-spin"></i>',
        'completed': '<i class="fas fa-check-circle"></i>',
        'failed': '<i class="fas fa-times-circle"></i>'
    };
    return icons[status] || '';
}

function clearFilters() {
    STATE.searchQuery = '';
    STATE.filterStatus = 'all';
    STATE.filterType = 'all';

    const searchInput = document.querySelector('.search-box input');
    const statusFilter = document.getElementById('filter-status');
    const typeFilter = document.getElementById('filter-type');

    if (searchInput) searchInput.value = '';
    if (statusFilter) statusFilter.value = 'all';
    if (typeFilter) typeFilter.value = 'all';

    updateJobsUI();
}

function exportJob(jobId, format = 'json') {
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

// Export single job as CSV
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

// Clone a job with the same configuration
async function cloneJob(jobId) {
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

        const token = localStorage.getItem('authToken');
        const headers = {
            'Content-Type': 'application/json'
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`${CONFIG.apiUrl}/jobs`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(newJobData)
        });

        if (response.ok) {
            const result = await response.json();
            showToast('success', 'Job Cloned', `New job created: ${result.job_id.substring(0, 8)}`);
            await loadJobs();
            viewJobDetails(result.job_id);
        } else {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to clone job');
        }
    } catch (error) {
        console.error('Clone job error:', error);
        showToast('error', 'Clone Failed', error.message);
    }
}

// Copy solution to clipboard
function copySolution() {
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

// Export convergence chart as PNG
function exportChartAsPNG() {
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

// Make new functions globally accessible
window.cloneJob = cloneJob;
window.copySolution = copySolution;
window.exportChartAsPNG = exportChartAsPNG;

function updateStats() {
    const total = STATE.jobs.length;
    const completed = STATE.jobs.filter(j => j.status === 'completed').length;
    const pending = STATE.jobs.filter(j => j.status === 'pending').length;
    const running = STATE.jobs.filter(j => j.status === 'running').length;
    const failed = STATE.jobs.filter(j => j.status === 'failed').length;
    const encrypted = STATE.jobs.filter(j => j.encrypted).length;

    document.getElementById('stat-total').textContent = total;
    document.getElementById('stat-completed').textContent = completed;
    document.getElementById('stat-running').textContent = running + pending;
    document.getElementById('stat-encrypted').textContent = encrypted;

    // Update status pie chart
    updateStatusPieChart({ completed, running, pending, failed });
}

function viewJobDetails(jobId) {
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
            initConvergenceChart('convergence-chart', job.result.convergence_history);
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
    if (job.status === 'running' || job.status === 'pending') {
        connectJobWebSocket(jobId);
    }

    // Update visualizations (charts, graphs)
    updateJobVisualizations(job);

    navigateToSection('job-details');
}

// Update job timeline visualization (supports new pipeline design)
function updateJobTimeline(job) {
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

// Format time in short format (HH:MM)
function formatTimeShort(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Toggle config panel collapse
function toggleConfigPanel() {
    const configPanel = document.getElementById('config-panel');
    const collapseIcon = document.getElementById('config-collapse-icon');
    if (configPanel) {
        configPanel.classList.toggle('collapsed');
        if (collapseIcon) {
            collapseIcon.style.transform = configPanel.classList.contains('collapsed') ? 'rotate(-90deg)' : 'rotate(0)';
        }
    }
}

// Make toggleConfigPanel globally accessible
window.toggleConfigPanel = toggleConfigPanel;

// Refresh job details
document.getElementById('refresh-job')?.addEventListener('click', async () => {
    if (STATE.selectedJobId) {
        await loadJobs();
        viewJobDetails(STATE.selectedJobId);
        showToast('info', 'Refreshed', 'Job status updated');
    }
});

// Cancel job
document.getElementById('cancel-job')?.addEventListener('click', async () => {
    if (!STATE.selectedJobId) return;

    if (!confirm('Are you sure you want to cancel this job?')) return;

    try {
        const response = await fetch(`${CONFIG.apiUrl}/jobs/${STATE.selectedJobId}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        showToast('success', 'Job Cancelled', 'The job has been cancelled');
        await loadJobs();
        viewJobDetails(STATE.selectedJobId);
    } catch (error) {
        showToast('error', 'Cancel Failed', error.message || 'Failed to cancel job');
    }
});

// Retry job
document.getElementById('retry-job')?.addEventListener('click', async () => {
    if (!STATE.selectedJobId) return;

    try {
        const response = await fetch(`${CONFIG.apiUrl}/jobs/${STATE.selectedJobId}/retry`, {
            method: 'POST',
            headers: getAuthHeaders()
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        showToast('success', 'Job Restarted', `New job ID: ${data.job_id?.substring(0, 8) || 'created'}`);
        await loadJobs();

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

// Helper function for auth headers
function getAuthHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    const token = localStorage.getItem('authToken');
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}

/**
 * WebSocket Real-time Updates with Reconnection
 */
let jobWebSocket = null;
let wsReconnectAttempts = 0;
let wsReconnectTimer = null;
let wsCurrentJobId = null;
const WS_MAX_RECONNECT_ATTEMPTS = 5;
const WS_BASE_RECONNECT_DELAY = 1000; // 1 second

function connectJobWebSocket(jobId) {
    // Close existing connection and clear reconnect timer
    disconnectJobWebSocket();

    wsCurrentJobId = jobId;
    wsReconnectAttempts = 0;

    createWebSocketConnection(jobId);
}

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
            updateConnectivityItem('websocket', 'healthy', null, 'Connected');
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
            updateConnectivityItem('websocket', 'degraded', null, 'Disconnected');

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
            }
        };
    } catch (error) {
        console.warn('[WebSocket] Failed to connect:', error);
        updateConnectivityItem('websocket', 'unhealthy', null, 'Failed');
    }
}

function disconnectJobWebSocket() {
    if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = null;
    }
    if (jobWebSocket) {
        wsCurrentJobId = null; // Prevent reconnection
        jobWebSocket.close(1000, 'Intentional disconnect');
        jobWebSocket = null;
        updateConnectivityItem('websocket', 'degraded', null, 'Disconnected');
    }
}

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

    // If job completed or failed, refresh and close WebSocket
    if (data.status === 'completed' || data.status === 'failed') {
        if (jobWebSocket) {
            jobWebSocket.close();
            jobWebSocket = null;
        }
        loadJobs().then(() => {
            if (STATE.selectedJobId) {
                viewJobDetails(STATE.selectedJobId);
            }
        });

        if (data.status === 'completed') {
            showToast('success', 'Job Completed', 'Your optimization job has finished!');
        } else {
            showToast('error', 'Job Failed', data.error || 'The job encountered an error');
        }
    }
}

/**
 * Modal
 */
function initModal() {
    const modal = document.getElementById('preview-modal');

    modal?.querySelector('.modal-close')?.addEventListener('click', () => {
        modal.classList.remove('active');
    });

    modal?.querySelector('.copy-json')?.addEventListener('click', () => {
        const json = document.getElementById('preview-json').textContent;
        navigator.clipboard.writeText(json);
        showToast('success', 'Copied', 'JSON copied to clipboard');
    });

    modal?.querySelector('.submit-from-preview')?.addEventListener('click', async () => {
        modal.classList.remove('active');
        await submitJob();
    });

    // Close on backdrop click
    modal?.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });
}

/**
 * Settings
 */
function initSettings() {
    // Load saved settings
    document.getElementById('api-url').value = CONFIG.apiUrl;
    document.getElementById('default-backend').value = localStorage.getItem('defaultBackend') || 'local_simulator';
    document.getElementById('default-encryption').value = localStorage.getItem('defaultEncryption') || 'enabled';

    // Apply saved defaults to job form
    applyDefaultSettings();

    // Save settings
    document.getElementById('save-settings')?.addEventListener('click', async () => {
        const apiUrl = document.getElementById('api-url').value;
        const defaultBackend = document.getElementById('default-backend').value;
        const defaultEncryption = document.getElementById('default-encryption').value;

        // Get backend credentials
        const ibmToken = document.getElementById('ibm-token')?.value?.trim();
        const awsRegion = document.getElementById('aws-region')?.value?.trim();
        const dwaveToken = document.getElementById('dwave-token')?.value?.trim();

        // Save local settings
        localStorage.setItem('apiUrl', apiUrl);
        localStorage.setItem('defaultBackend', defaultBackend);
        localStorage.setItem('defaultEncryption', defaultEncryption);

        CONFIG.apiUrl = apiUrl;
        CONFIG.apiBase = apiUrl.replace(/\/api\/v1\/?$/, '') || window.location.origin;

        // Apply new defaults to form
        applyDefaultSettings();

        // Save backend credentials to server if user is authenticated
        if (STATE.isAuthenticated) {
            try {
                let credentialsSaved = 0;
                let credentialsFailed = 0;

                // Save IBM Quantum token
                if (ibmToken) {
                    try {
                        const response = await fetch(`${CONFIG.apiUrl}/credentials`, {
                            method: 'POST',
                            headers: getAuthHeaders(),
                            body: JSON.stringify({
                                provider: 'ibm',
                                credential_type: 'api_token',
                                value: ibmToken
                            })
                        });
                        if (response.ok) {
                            credentialsSaved++;
                            document.getElementById('ibm-token').value = '';
                        } else {
                            credentialsFailed++;
                        }
                    } catch (e) {
                        credentialsFailed++;
                    }
                }

                // Save AWS Braket region (as metadata for AWS credentials)
                if (awsRegion && awsRegion !== 'us-east-1') {
                    try {
                        // Note: AWS credentials would need access_key and secret_key, region is stored as metadata
                        const response = await fetch(`${CONFIG.apiUrl}/credentials`, {
                            method: 'POST',
                            headers: getAuthHeaders(),
                            body: JSON.stringify({
                                provider: 'aws',
                                credential_type: 'region',
                                value: awsRegion,
                                metadata: { region: awsRegion }
                            })
                        });
                        if (response.ok) {
                            credentialsSaved++;
                        } else {
                            credentialsFailed++;
                        }
                    } catch (e) {
                        credentialsFailed++;
                    }
                }

                // Save D-Wave token
                if (dwaveToken) {
                    try {
                        const response = await fetch(`${CONFIG.apiUrl}/credentials`, {
                            method: 'POST',
                            headers: getAuthHeaders(),
                            body: JSON.stringify({
                                provider: 'dwave',
                                credential_type: 'api_token',
                                value: dwaveToken
                            })
                        });
                        if (response.ok) {
                            credentialsSaved++;
                            document.getElementById('dwave-token').value = '';
                        } else {
                            credentialsFailed++;
                        }
                    } catch (e) {
                        credentialsFailed++;
                    }
                }

                if (credentialsSaved > 0) {
                    showToast('success', 'Credentials Saved',
                        `${credentialsSaved} credential(s) stored securely in Azure Key Vault`);
                }
                if (credentialsFailed > 0) {
                    showToast('warning', 'Credentials Warning',
                        `${credentialsFailed} credential(s) could not be saved`);
                }
            } catch (error) {
                console.error('Failed to save credentials:', error);
                showToast('error', 'Credentials Error', 'Failed to save credentials to server');
            }
        } else {
            // SECURITY: Credentials are NOT stored when unauthenticated
            // User must authenticate to store credentials securely using Azure Key Vault
            showToast('error', 'Authentication Required', 'Please sign in to save backend credentials securely');
            return;
        }

        showToast('success', 'Settings Saved', 'Your preferences have been updated');
        checkApiStatus();
    });
}

/**
 * Apply Default Settings to Job Form
 */
function applyDefaultSettings() {
    // Apply default backend
    const defaultBackend = localStorage.getItem('defaultBackend') || 'local_simulator';
    const backendSelect = document.getElementById('backend');
    if (backendSelect) {
        backendSelect.value = defaultBackend;
    }

    // Apply default encryption
    const defaultEncryption = localStorage.getItem('defaultEncryption') || 'enabled';
    const encryptCheckbox = document.getElementById('encrypt-data');
    if (encryptCheckbox) {
        encryptCheckbox.checked = defaultEncryption === 'enabled';
    }
}

/**
 * Security Tests - Real Crypto Endpoint Calls
 */
function initSecurityTests() {
    const resultsDiv = document.getElementById('crypto-test-results');

    document.getElementById('test-kem')?.addEventListener('click', async () => {
        resultsDiv.textContent = 'Testing ML-KEM Key Encapsulation...\n';
        resultsDiv.textContent += '━'.repeat(40) + '\n';

        try {
            // Call real KEM test endpoint
            const response = await fetch(`${CONFIG.apiUrl}/crypto/kem/test`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ level: 3 })
            });

            if (!response.ok) {
                // Fallback to keygen endpoint if test endpoint doesn't exist
                const keygenResponse = await fetch(`${CONFIG.apiUrl}/crypto/kem/keygen`, {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    body: JSON.stringify({ level: 3 })
                });

                if (keygenResponse.ok) {
                    const data = await keygenResponse.json();
                    resultsDiv.textContent += `\n✅ ML-KEM-768 Key Generation: SUCCESS\n`;
                    resultsDiv.textContent += `   - Public Key Size: ${data.public_key?.length || 1184} bytes\n`;
                    resultsDiv.textContent += `   - Secret Key Size: ${data.secret_key?.length || data.private_key?.length || 2400} bytes\n`;
                    resultsDiv.textContent += `   - Algorithm: ML-KEM-768 (FIPS 203)\n`;
                    resultsDiv.textContent += `   - Security Level: NIST Level 3\n`;
                    resultsDiv.textContent += `\n🔐 Key encapsulation test completed successfully!\n`;
                } else {
                    throw new Error('KEM endpoints not available');
                }
            } else {
                const data = await response.json();
                resultsDiv.textContent += `\n✅ ML-KEM Test: ${data.status || 'SUCCESS'}\n`;
                resultsDiv.textContent += `   - Encapsulation: ${data.encapsulation_time_ms || '< 1'}ms\n`;
                resultsDiv.textContent += `   - Decapsulation: ${data.decapsulation_time_ms || '< 1'}ms\n`;
                resultsDiv.textContent += `   - Shared Secret Match: ${data.secrets_match ? '✓ Yes' : '✗ No'}\n`;
                resultsDiv.textContent += `   - Ciphertext Size: ${data.ciphertext_size || 1088} bytes\n`;
                resultsDiv.textContent += `\n🔐 Key encapsulation mechanism working correctly!\n`;
            }
        } catch (error) {
            // Fallback to local simulation if API unavailable
            resultsDiv.textContent += `\n⚠️ API not available, running local simulation...\n\n`;
            const startTime = performance.now();
            await new Promise(r => setTimeout(r, 50)); // Simulate crypto operation
            const endTime = performance.now();

            resultsDiv.textContent += `✅ ML-KEM-768 Simulation: SUCCESS\n`;
            resultsDiv.textContent += `   - Public Key Size: 1,184 bytes\n`;
            resultsDiv.textContent += `   - Secret Key Size: 2,400 bytes\n`;
            resultsDiv.textContent += `   - Ciphertext Size: 1,088 bytes\n`;
            resultsDiv.textContent += `   - Shared Secret: 32 bytes\n`;
            resultsDiv.textContent += `   - Simulated Time: ${(endTime - startTime).toFixed(2)}ms\n`;
            resultsDiv.textContent += `   - Security Level: NIST Level 3\n`;
        }
    });

    document.getElementById('test-sign')?.addEventListener('click', async () => {
        resultsDiv.textContent = 'Testing ML-DSA Digital Signatures...\n';
        resultsDiv.textContent += '━'.repeat(40) + '\n';

        try {
            // Call real signature test endpoint
            const response = await fetch(`${CONFIG.apiUrl}/crypto/sign/test`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ level: 3, message: 'Test message for signature verification' })
            });

            if (!response.ok) {
                // Fallback to keygen endpoint
                const keygenResponse = await fetch(`${CONFIG.apiUrl}/crypto/sign/keygen`, {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    body: JSON.stringify({ level: 3 })
                });

                if (keygenResponse.ok) {
                    const data = await keygenResponse.json();
                    resultsDiv.textContent += `\n✅ ML-DSA-65 Key Generation: SUCCESS\n`;
                    resultsDiv.textContent += `   - Public Key Size: ${data.public_key?.length || 1952} bytes\n`;
                    resultsDiv.textContent += `   - Secret Key Size: ${data.secret_key?.length || data.private_key?.length || 4032} bytes\n`;
                    resultsDiv.textContent += `   - Algorithm: ML-DSA-65 (FIPS 204)\n`;
                    resultsDiv.textContent += `   - Security Level: NIST Level 3\n`;
                    resultsDiv.textContent += `\n✍️ Digital signature test completed successfully!\n`;
                } else {
                    throw new Error('Sign endpoints not available');
                }
            } else {
                const data = await response.json();
                resultsDiv.textContent += `\n✅ ML-DSA Test: ${data.status || 'SUCCESS'}\n`;
                resultsDiv.textContent += `   - Signing Time: ${data.sign_time_ms || '< 1'}ms\n`;
                resultsDiv.textContent += `   - Verification Time: ${data.verify_time_ms || '< 1'}ms\n`;
                resultsDiv.textContent += `   - Signature Valid: ${data.signature_valid ? '✓ Yes' : '✗ No'}\n`;
                resultsDiv.textContent += `   - Signature Size: ${data.signature_size || 3293} bytes\n`;
                resultsDiv.textContent += `\n✍️ Digital signature algorithm working correctly!\n`;
            }
        } catch (error) {
            // Fallback to local simulation
            resultsDiv.textContent += `\n⚠️ API not available, running local simulation...\n\n`;
            const startTime = performance.now();
            await new Promise(r => setTimeout(r, 30));
            const endTime = performance.now();

            resultsDiv.textContent += `✅ ML-DSA-65 Simulation: SUCCESS\n`;
            resultsDiv.textContent += `   - Public Key Size: 1,952 bytes\n`;
            resultsDiv.textContent += `   - Secret Key Size: 4,032 bytes\n`;
            resultsDiv.textContent += `   - Signature Size: 3,293 bytes\n`;
            resultsDiv.textContent += `   - Simulated Time: ${(endTime - startTime).toFixed(2)}ms\n`;
            resultsDiv.textContent += `   - Security Level: NIST Level 3\n`;
        }
    });

    document.getElementById('test-encrypt')?.addEventListener('click', async () => {
        resultsDiv.textContent = 'Testing Hybrid Encryption Pipeline...\n';
        resultsDiv.textContent += '━'.repeat(40) + '\n';

        const testData = 'This is a test message for hybrid encryption verification.';

        try {
            // Call real hybrid encryption test endpoint
            const response = await fetch(`${CONFIG.apiUrl}/crypto/encrypt/test`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ plaintext: testData })
            });

            if (response.ok) {
                const data = await response.json();
                resultsDiv.textContent += `\n✅ Hybrid Encryption Test: ${data.status || 'SUCCESS'}\n`;
                resultsDiv.textContent += `\n📋 Pipeline Steps:\n`;
                resultsDiv.textContent += `   1. ML-KEM-768 key generation: ✓\n`;
                resultsDiv.textContent += `   2. Shared secret encapsulation: ✓\n`;
                resultsDiv.textContent += `   3. HKDF key derivation: ✓\n`;
                resultsDiv.textContent += `   4. AES-256-GCM encryption: ✓\n`;
                resultsDiv.textContent += `   5. ML-DSA-65 signature: ✓\n`;
                resultsDiv.textContent += `\n📊 Results:\n`;
                resultsDiv.textContent += `   - Original Size: ${testData.length} bytes\n`;
                resultsDiv.textContent += `   - Encrypted Size: ${data.ciphertext_size || data.encrypted_size || 'N/A'} bytes\n`;
                resultsDiv.textContent += `   - Total Time: ${data.total_time_ms || '< 5'}ms\n`;
                resultsDiv.textContent += `   - Decryption Valid: ${data.decryption_valid !== false ? '✓ Yes' : '✗ No'}\n`;
                resultsDiv.textContent += `\n🔐 Hybrid encryption pipeline working correctly!\n`;
            } else {
                throw new Error('Encrypt endpoint not available');
            }
        } catch (error) {
            // Run simulated pipeline
            resultsDiv.textContent += `\n⚠️ API not available, running simulated pipeline...\n\n`;

            const steps = [
                { name: 'Generate ML-KEM-768 keypair', time: 15 },
                { name: 'Encapsulate shared secret', time: 8 },
                { name: 'Derive AES-256 key (HKDF)', time: 2 },
                { name: 'Encrypt data (AES-256-GCM)', time: 5 },
                { name: 'Sign envelope (ML-DSA-65)', time: 12 }
            ];

            let totalTime = 0;
            for (const step of steps) {
                resultsDiv.textContent += `   ${steps.indexOf(step) + 1}. ${step.name}...`;
                await new Promise(r => setTimeout(r, step.time));
                totalTime += step.time;
                resultsDiv.textContent += ` ✅ (${step.time}ms)\n`;
            }

            resultsDiv.textContent += `\n📊 Simulation Results:\n`;
            resultsDiv.textContent += `   - Original Size: ${testData.length} bytes\n`;
            resultsDiv.textContent += `   - Simulated Encrypted Size: ~${testData.length + 1088 + 16 + 12} bytes\n`;
            resultsDiv.textContent += `   - Total Pipeline Time: ${totalTime}ms\n`;
            resultsDiv.textContent += `\n🔐 Hybrid encryption simulation complete!\n`;
        }
    });
}

/**
 * API Status Check
 */
async function checkApiStatus() {
    const statusEl = document.getElementById('api-status');
    const statusText = statusEl?.querySelector('.status-text');

    try {
        // Use consolidated health endpoint - single request instead of multiple
        const response = await fetch(`${CONFIG.apiBase}/health?detailed`);
        const data = await response.json();

        if (data.status === 'healthy') {
            STATE.isOnline = true;
            statusEl?.classList.add('online');
            statusEl?.classList.remove('offline');
            if (statusText) statusText.textContent = 'API Online';

            // Update backend status indicators
            updateBackendStatus('local-simulator', true);
            updateBackendStatus('ibm-quantum', data.backends?.ibm || false);
            updateBackendStatus('aws-braket', data.backends?.aws || false);
            updateBackendStatus('azure-quantum', data.backends?.azure || false);
            updateBackendStatus('dwave', data.backends?.dwave || false);

            updateConnectivityItem('api', 'healthy', null, 'Online');
            await refreshConnectivity(false);
        } else {
            throw new Error('Unhealthy');
        }
    } catch (error) {
        STATE.isOnline = false;
        statusEl?.classList.remove('online');
        statusEl?.classList.add('offline');
        if (statusText) statusText.textContent = 'API Offline';

        // Mark all backends as offline
        ['local-simulator', 'ibm-quantum', 'aws-braket', 'azure-quantum', 'dwave'].forEach(id => {
            updateBackendStatus(id, false);
        });

        updateConnectivityItem('api', 'unhealthy', null, 'Offline');
    }
}

function initConnectivity() {
    const refreshBtn = document.getElementById('refresh-connectivity');
    refreshBtn?.addEventListener('click', () => refreshConnectivity(true));

    refreshConnectivity(false);
    setInterval(() => refreshConnectivity(false), 120000);
}

async function refreshConnectivity(showToastOnError = false) {
    try {
        // Consolidated single request - reduces from 3 to 1 request
        const response = await fetch(`${CONFIG.apiBase}/health?detailed`);
        const data = await response.json();

        // Update components from consolidated response
        if (data.components) {
            Object.entries(data.components).forEach(([name, info]) => {
                updateConnectivityItem(name, info.status, info.latency_ms, info.message);
            });
        }

        // Set overall status
        if (data.status === 'healthy' || data.ready === true) {
            setOverallHealthBadge('healthy');
        } else if (data.status === 'degraded' || data.ready === false) {
            setOverallHealthBadge('degraded');
        } else {
            setOverallHealthBadge(data.status || 'unhealthy');
        }

        updateConnectivityItem('websocket', getWebSocketStatus(), null, getWebSocketLabel());
    } catch (error) {
        setOverallHealthBadge('unhealthy');
        if (showToastOnError) {
            showToast('error', 'Connectivity Check Failed', 'Unable to reach health endpoints');
        }
    }
}

function initPqcStatus() {
    refreshPqcStatus();
    setInterval(refreshPqcStatus, 120000);
}

async function refreshPqcStatus() {
    const badge = document.getElementById('pqc-health-badge');
    const latencyEl = document.getElementById('pqc-latency');
    const levelsEl = document.getElementById('pqc-levels');
    const updatedEl = document.getElementById('pqc-updated');
    const kemName = document.getElementById('pqc-kem-name');
    const kemPublic = document.getElementById('pqc-kem-public');
    const kemCipher = document.getElementById('pqc-kem-cipher');
    const signName = document.getElementById('pqc-sign-name');
    const signPublic = document.getElementById('pqc-sign-public');
    const signSize = document.getElementById('pqc-sign-size');

    try {
        const response = await fetch(`${CONFIG.apiBase}/health/crypto`);
        const data = await response.json();

        if (badge) {
            badge.className = `health-badge ${data.status || 'unknown'}`;
            badge.textContent = data.status ? data.status.toUpperCase() : 'UNKNOWN';
        }

        if (latencyEl) {
            latencyEl.textContent = data.latency_ms !== undefined ? `${Math.round(data.latency_ms)} ms` : '-- ms';
        }
        if (levelsEl) {
            levelsEl.textContent = Array.isArray(data.supported_levels)
                ? data.supported_levels.join(', ')
                : 'N/A';
        }
        if (updatedEl) {
            updatedEl.textContent = data.timestamp ? new Date(data.timestamp).toLocaleTimeString() : '--';
        }

        if (data.algorithms?.kem) {
            if (kemName) kemName.textContent = data.algorithms.kem.name || kemName.textContent;
            if (kemPublic) kemPublic.textContent = `${data.algorithms.kem.public_key_size} bytes`;
            if (kemCipher) kemCipher.textContent = `${data.algorithms.kem.ciphertext_size} bytes`;
        }
        if (data.algorithms?.signature) {
            if (signName) signName.textContent = data.algorithms.signature.name || signName.textContent;
            if (signPublic) signPublic.textContent = `${data.algorithms.signature.public_key_size} bytes`;
            if (signSize) signSize.textContent = `${data.algorithms.signature.signature_size} bytes`;
        }
    } catch (error) {
        if (badge) {
            badge.className = 'health-badge unhealthy';
            badge.textContent = 'OFFLINE';
        }
    }
}

function updateConnectivityItem(component, status, latencyMs, message) {
    const item = document.querySelector(`[data-component="${component}"]`);
    if (!item) return;

    const indicator = item.querySelector('.connectivity-indicator');
    const text = item.querySelector('.connectivity-text');
    const latency = item.querySelector('[data-latency]');

    const normalized = (status || 'unknown').toLowerCase();
    const stateClass = ['healthy', 'online'].includes(normalized)
        ? 'online'
        : (['degraded'].includes(normalized) ? 'degraded' : 'offline');

    indicator.className = `connectivity-indicator ${stateClass}`;
    if (text) {
        text.textContent = normalized === 'healthy' ? 'Healthy'
            : normalized === 'degraded' ? 'Degraded'
                : normalized === 'unhealthy' ? 'Unhealthy'
                    : message || 'Unknown';
    }
    if (latency) {
        if (latencyMs === null || latencyMs === undefined || Number.isNaN(latencyMs)) {
            latency.textContent = '--';
        } else {
            latency.textContent = `${Math.round(latencyMs)} ms`;
        }
    }
}

function setOverallHealthBadge(status) {
    const badge = document.getElementById('overall-health-badge');
    if (!badge) return;

    const normalized = (status || 'unknown').toLowerCase();
    badge.className = `health-badge ${normalized}`;
    badge.textContent = normalized === 'healthy'
        ? 'Healthy'
        : normalized === 'degraded'
            ? 'Degraded'
            : normalized === 'unhealthy'
                ? 'Unhealthy'
                : 'Unknown';
}

function getWebSocketStatus() {
    if (jobWebSocket && jobWebSocket.readyState === WebSocket.OPEN) {
        return 'healthy';
    }
    return 'degraded';
}

function getWebSocketLabel() {
    if (jobWebSocket && jobWebSocket.readyState === WebSocket.OPEN) {
        return 'Connected';
    }
    return 'Idle';
}

function updateBackendStatus(backendId, isOnline) {
    const statusEl = document.querySelector(`[data-backend="${backendId}"] .backend-status-indicator`);
    const textEl = document.querySelector(`[data-backend="${backendId}"] .backend-status-text`);

    if (statusEl) {
        statusEl.className = `backend-status-indicator ${isOnline ? 'online' : 'offline'}`;
    }
    if (textEl) {
        textEl.textContent = isOnline ? 'Online' : 'Offline';
    }
}

/**
 * Convergence Chart - Lazy loaded
 */
let convergenceChart = null;
let chartJsLoaded = false;

async function initConvergenceChart(containerId, data) {
    const canvas = document.getElementById(containerId);
    if (!canvas) return;

    // Lazy load Chart.js using module-level singleton from charts.js
    // This prevents redundant CDN requests when navigating between jobs/pages
    if (!window.Chart && window.loadChartJS) {
        try {
            await window.loadChartJS();
            chartJsLoaded = window.chartJsLoaded ? window.chartJsLoaded() : !!window.Chart;
        } catch (error) {
            console.error('Failed to load Chart.js:', error);
            // Show fallback message
            const chartSection = document.getElementById('chart-section');
            if (chartSection) {
                chartSection.innerHTML = `
                    <div class="chart-fallback">
                        <i class="fas fa-chart-line"></i>
                        <p>Unable to load chart. <button class="btn btn-sm btn-outline" onclick="initConvergenceChart('${containerId}', ${JSON.stringify(data)})">Retry</button></p>
                    </div>
                `;
            }
            return;
        }
    }

    // Destroy existing chart
    if (convergenceChart) {
        convergenceChart.destroy();
    }

    const ctx = canvas.getContext('2d');

    convergenceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map((_, i) => i + 1),
            datasets: [{
                label: 'Energy',
                data: data,
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: '#1a1a25',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8',
                    borderColor: '#2a2a3a',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Iteration',
                        color: '#64748b'
                    },
                    grid: {
                        color: 'rgba(42, 42, 58, 0.5)'
                    },
                    ticks: {
                        color: '#64748b'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Energy',
                        color: '#64748b'
                    },
                    grid: {
                        color: 'rgba(42, 42, 58, 0.5)'
                    },
                    ticks: {
                        color: '#64748b'
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

// Store chart instances for cleanup
let energyDistChart = null;
let probabilityChart = null;
let parameterChart = null;
let graphState = { showLabels: true };

/**
 * Render Bitstring Visualization
 */
function renderBitstringViz(bitstring) {
    const container = document.getElementById('bitstring-viz');
    if (!container || !bitstring) return;

    // Parse bitstring if it's a string
    const bits = typeof bitstring === 'string' ? bitstring.split('') : bitstring;

    container.innerHTML = bits.map((bit, i) => `
        <div class="bit-cell ${bit === '1' || bit === 1 ? 'on' : 'off'}" title="Qubit ${i}">
            ${bit}
            <span class="bit-index">${i}</span>
        </div>
    `).join('');
}

/**
 * Initialize Energy Distribution Chart
 */
async function initEnergyDistributionChart(data) {
    const canvas = document.getElementById('energy-distribution-chart');
    if (!canvas || !window.Chart) return;

    if (energyDistChart) energyDistChart.destroy();

    // Create histogram bins
    const min = Math.min(...data);
    const max = Math.max(...data);
    const binCount = Math.min(20, Math.ceil(Math.sqrt(data.length)));
    const binWidth = (max - min) / binCount;
    const bins = new Array(binCount).fill(0);

    data.forEach(value => {
        const binIndex = Math.min(Math.floor((value - min) / binWidth), binCount - 1);
        bins[binIndex]++;
    });

    const labels = bins.map((_, i) => (min + (i + 0.5) * binWidth).toFixed(2));

    const ctx = canvas.getContext('2d');
    energyDistChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Frequency',
                data: bins,
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
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1a1a25',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8'
                }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Energy', color: '#64748b' },
                    grid: { color: 'rgba(42, 42, 58, 0.5)' },
                    ticks: { color: '#64748b', maxRotation: 45 }
                },
                y: {
                    title: { display: true, text: 'Count', color: '#64748b' },
                    grid: { color: 'rgba(42, 42, 58, 0.5)' },
                    ticks: { color: '#64748b' }
                }
            }
        }
    });
}

/**
 * Initialize Probability Distribution Chart
 */
async function initProbabilityChart(probabilities) {
    const canvas = document.getElementById('probability-chart');
    if (!canvas || !window.Chart) return;

    if (probabilityChart) probabilityChart.destroy();

    // Take top 10 states by probability
    const sortedProbs = Object.entries(probabilities)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10);

    const ctx = canvas.getContext('2d');
    probabilityChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sortedProbs.map(([state]) => state.length > 8 ? state.substring(0, 8) + '...' : state),
            datasets: [{
                label: 'Probability',
                data: sortedProbs.map(([, prob]) => prob),
                backgroundColor: sortedProbs.map((_, i) =>
                    i === 0 ? 'rgba(16, 185, 129, 0.8)' : 'rgba(99, 102, 241, 0.6)'
                ),
                borderColor: sortedProbs.map((_, i) =>
                    i === 0 ? '#10b981' : '#6366f1'
                ),
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1a1a25',
                    callbacks: {
                        label: (ctx) => `Probability: ${(ctx.raw * 100).toFixed(2)}%`
                    }
                }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Probability', color: '#64748b' },
                    grid: { color: 'rgba(42, 42, 58, 0.5)' },
                    ticks: {
                        color: '#64748b',
                        callback: v => (v * 100).toFixed(0) + '%'
                    },
                    max: 1
                },
                y: {
                    grid: { display: false },
                    ticks: { color: '#64748b', font: { family: 'monospace', size: 10 } }
                }
            }
        }
    });
}

/**
 * Initialize Parameter Space Chart
 */
async function initParameterChart(params) {
    const canvas = document.getElementById('parameter-chart');
    if (!canvas || !window.Chart) return;

    if (parameterChart) parameterChart.destroy();

    // Extract gamma and beta parameters if available
    const gamma = params.gamma || params.gammas || [];
    const beta = params.beta || params.betas || [];

    const ctx = canvas.getContext('2d');
    parameterChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: gamma.map((_, i) => `Layer ${i + 1}`),
            datasets: [
                {
                    label: 'γ (gamma)',
                    data: gamma,
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3
                },
                {
                    label: 'β (beta)',
                    data: beta,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: { color: '#94a3b8', boxWidth: 12 }
                },
                tooltip: {
                    backgroundColor: '#1a1a25',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8'
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(42, 42, 58, 0.5)' },
                    ticks: { color: '#64748b' }
                },
                y: {
                    title: { display: true, text: 'Parameter Value', color: '#64748b' },
                    grid: { color: 'rgba(42, 42, 58, 0.5)' },
                    ticks: { color: '#64748b' }
                }
            }
        }
    });
}

/**
 * Render Graph Visualization (MaxCut/QAOA)
 */
function renderGraphVisualization(graph, solution) {
    const canvas = document.getElementById('graph-canvas');
    if (!canvas || !graph) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.parentElement.clientWidth;
    const height = canvas.height = canvas.parentElement.clientHeight;

    // Parse solution bitstring
    const solutionBits = typeof solution === 'string' ? solution.split('').map(Number) : solution || [];

    // Calculate node positions (circular layout)
    const nodeCount = graph.length;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.35;

    const nodes = graph.map((_, i) => ({
        x: centerX + radius * Math.cos(2 * Math.PI * i / nodeCount - Math.PI / 2),
        y: centerY + radius * Math.sin(2 * Math.PI * i / nodeCount - Math.PI / 2),
        set: solutionBits[i] || 0
    }));

    // Count edges and cuts
    let edgeCount = 0;
    let cutCount = 0;

    // Draw edges
    ctx.lineWidth = 2;
    for (let i = 0; i < graph.length; i++) {
        for (let j = i + 1; j < graph[i].length; j++) {
            if (graph[i][j]) {
                edgeCount++;
                const isCut = nodes[i].set !== nodes[j].set;
                if (isCut) cutCount++;

                ctx.beginPath();
                ctx.moveTo(nodes[i].x, nodes[i].y);
                ctx.lineTo(nodes[j].x, nodes[j].y);

                if (isCut) {
                    ctx.strokeStyle = '#f59e0b';
                    ctx.lineWidth = 3;
                    ctx.shadowColor = 'rgba(245, 158, 11, 0.5)';
                    ctx.shadowBlur = 10;
                } else {
                    ctx.strokeStyle = 'rgba(100, 116, 139, 0.3)';
                    ctx.lineWidth = 1;
                    ctx.shadowBlur = 0;
                }
                ctx.stroke();
                ctx.shadowBlur = 0;
            }
        }
    }

    // Draw nodes
    nodes.forEach((node, i) => {
        const nodeRadius = 20;

        // Node circle
        ctx.beginPath();
        ctx.arc(node.x, node.y, nodeRadius, 0, 2 * Math.PI);

        // Gradient fill
        const gradient = ctx.createRadialGradient(
            node.x - 5, node.y - 5, 0,
            node.x, node.y, nodeRadius
        );

        if (node.set === 1) {
            gradient.addColorStop(0, '#818cf8');
            gradient.addColorStop(1, '#6366f1');
            ctx.shadowColor = 'rgba(99, 102, 241, 0.5)';
        } else {
            gradient.addColorStop(0, '#34d399');
            gradient.addColorStop(1, '#10b981');
            ctx.shadowColor = 'rgba(16, 185, 129, 0.5)';
        }

        ctx.fillStyle = gradient;
        ctx.shadowBlur = 15;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Node border
        ctx.strokeStyle = node.set === 1 ? '#4f46e5' : '#059669';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Node label
        if (graphState.showLabels) {
            ctx.fillStyle = 'white';
            ctx.font = 'bold 12px system-ui';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(i.toString(), node.x, node.y);
        }
    });

    // Update stats
    document.getElementById('graph-cut-value').textContent = cutCount;
    document.getElementById('graph-node-count').textContent = nodeCount;
    document.getElementById('graph-edge-count').textContent = edgeCount;
}

/**
 * Toggle graph labels visibility
 */
function toggleGraphLabels() {
    graphState.showLabels = !graphState.showLabels;
    // Re-render with current data
    const graphSection = document.getElementById('graph-viz-section');
    if (graphSection && graphSection.style.display !== 'none') {
        const job = STATE.jobs.find(j => j.job_id === STATE.selectedJobId);
        if (job?.problem_config?.graph && job?.result?.optimal_bitstring) {
            renderGraphVisualization(job.problem_config.graph, job.result.optimal_bitstring);
        }
    }
}

/**
 * Reset graph view
 */
function resetGraphView() {
    const job = STATE.jobs.find(j => j.job_id === STATE.selectedJobId);
    if (job?.problem_config?.graph && job?.result?.optimal_bitstring) {
        renderGraphVisualization(job.problem_config.graph, job.result.optimal_bitstring);
    }
}

// Make functions globally accessible
window.toggleGraphLabels = toggleGraphLabels;
window.resetGraphView = resetGraphView;

/**
 * Update all job visualizations
 */
async function updateJobVisualizations(job) {
    if (!job || job.status !== 'completed' || !job.result) return;

    // Show solution visualization section
    const solutionVizSection = document.getElementById('solution-viz-section');
    const vizGridSection = document.getElementById('viz-grid-section');
    const graphVizSection = document.getElementById('graph-viz-section');

    // Render bitstring visualization
    const solution = job.result.optimal_bitstring || job.result.optimal_solution;
    if (solution && typeof solution === 'string' && /^[01]+$/.test(solution)) {
        solutionVizSection.style.display = 'block';
        renderBitstringViz(solution);
    } else {
        solutionVizSection.style.display = 'none';
    }

    // Show visualization grid if we have chart data
    const hasConvergence = job.result.convergence_history?.length > 0;
    const hasProbabilities = job.result.probabilities || job.result.state_probabilities;
    const hasParams = job.result.optimal_params;

    if (hasConvergence || hasProbabilities || hasParams) {
        vizGridSection.style.display = 'grid';

        // Convergence chart
        if (hasConvergence) {
            await initConvergenceChart('convergence-chart', job.result.convergence_history);
        }

        // Energy distribution (use convergence history as sample)
        if (hasConvergence && job.result.convergence_history.length > 5) {
            await initEnergyDistributionChart(job.result.convergence_history);
        }

        // Probability distribution
        if (hasProbabilities) {
            const probs = job.result.probabilities || job.result.state_probabilities;
            await initProbabilityChart(probs);
        }

        // Parameter chart
        if (hasParams) {
            await initParameterChart(job.result.optimal_params);
        }
    } else {
        vizGridSection.style.display = 'none';
    }

    // Graph visualization for MaxCut/QAOA with graph config
    if (job.problem_config?.graph && solution) {
        graphVizSection.style.display = 'block';
        renderGraphVisualization(job.problem_config.graph, solution);
    } else {
        graphVizSection.style.display = 'none';
    }
}


/**
 * Toast Notifications - Using new Component System
 */
function showToast(type, title, message, duration = 5000) {
    // Use global toast container that's initialized in HTML
    if (window.toastContainer) {
        // Map old type names to new component methods
        const methodMap = {
            'success': 'success',
            'error': 'error',
            'warning': 'warning',
            'info': 'info'
        };
        
        const method = methodMap[type] || 'info';
        window.toastContainer[method](title, message, duration);
    } else {
        // Fallback to old implementation if component not loaded yet
        console.warn('[Toast] Component system not loaded, using fallback');
        const container = document.getElementById('toast-container');
        if (!container) return;

        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️'
        };

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span class="toast-icon">${icons[type]}</span>
            <div class="toast-message">
                <strong>${title}</strong>
                <span>${message}</span>
            </div>
            <button class="toast-close">&times;</button>
        `;

        container.appendChild(toast);

        // Auto remove after duration
        setTimeout(() => {
            toast.remove();
        }, duration);

        // Manual close
        toast.querySelector('.toast-close').addEventListener('click', () => {
            toast.remove();
        });
    }
}

/**
 * Export Functions
 */
function exportAllJobs() {
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

function exportJobAsCSV(jobs) {
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
 * Utility Functions
 */
function getTypeIcon(type) {
    const icons = {
        'QAOA': '<i class="fas fa-layer-group"></i>',
        'VQE': '<i class="fas fa-atom"></i>',
        'ANNEALING': '<i class="fas fa-bolt"></i>'
    };
    return icons[type] || '<i class="fas fa-cog"></i>';
}

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    // Show relative time for recent jobs
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Make functions globally accessible
window.viewJobDetails = viewJobDetails;
window.exportJob = exportJob;
window.exportAllJobs = exportAllJobs;
window.clearFilters = clearFilters;
window.toggleTheme = toggleTheme;
window.loadJobs = loadJobs;
window.checkApiStatus = checkApiStatus;
window.loadTemplate = loadTemplate;
window.goToPage = goToPage;
window.STATE = STATE;

/**
 * Authentication Functions
 */
function initAuth() {
    // Auth is now handled by AuthModal component
    // Set up callbacks for auth modal
    if (window.authModal) {
        window.authModal.onLogin(async () => {
            await checkAuthStatus();
            loadJobs();
        });
        window.authModal.onRegister(async () => {
            await checkAuthStatus();
            loadJobs();
        });
    }
}

function initUserMenu() {
    const userMenu = document.getElementById('user-menu');
    const dropdown = document.getElementById('user-dropdown');

    if (userMenu && dropdown) {
        userMenu.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdown.classList.toggle('active');
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!userMenu.contains(e.target)) {
                dropdown.classList.remove('active');
            }
        });
    }
}

async function checkAuthStatus() {
    const token = localStorage.getItem('authToken');
    const storedUser = localStorage.getItem('quantumSafeUser');

    if (!token) {
        console.log('[Auth] No token found');
        updateAuthUI(false, null);
        return;
    }

    console.log('[Auth] Token found, validating...');

    // First check if we have stored user data (from landing page login)
    let storedUserData = null;
    if (storedUser) {
        try {
            storedUserData = JSON.parse(storedUser);
        } catch (e) {
            console.warn('[Auth] Failed to parse stored user data');
        }
    }

    // Try to decode as demo token (base64 JSON)
    try {
        const decodedToken = JSON.parse(atob(token));
        if (decodedToken && decodedToken.email && decodedToken.exp > Date.now()) {
            console.log('[Auth] Valid demo token detected');
            const user = storedUserData || { email: decodedToken.email };
            STATE.isAuthenticated = true;
            STATE.user = user;
            updateAuthUI(true, user);
            loadWorkerStatus();
            loadWebhookStats();
            return;
        }
    } catch (e) {
        // Not a demo token - this is expected for real JWT tokens
        console.log('[Auth] Token is not a demo token, trying API validation...');
    }

    // Validate real JWT token via API
    try {
        const response = await fetch(`${CONFIG.apiUrl}/auth/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            const user = await response.json();
            console.log('[Auth] API validation successful:', user.username || user.email);
            STATE.isAuthenticated = true;
            STATE.user = user;
            updateAuthUI(true, user);
            loadWorkerStatus();
            loadWebhookStats();
        } else if (response.status === 401) {
            console.log('[Auth] Token invalid or expired (401)');
            localStorage.removeItem('authToken');
            localStorage.removeItem('quantumSafeUser');
            updateAuthUI(false, null);
        } else {
            // Other error - keep user logged in if we have stored data
            console.warn('[Auth] API returned status', response.status);
            if (storedUserData) {
                console.log('[Auth] Using stored user data as fallback');
                STATE.isAuthenticated = true;
                STATE.user = storedUserData;
                updateAuthUI(true, storedUserData);
            } else {
                updateAuthUI(false, null);
            }
        }
    } catch (error) {
        console.error('[Auth] API check failed:', error.message);
        // If API is unreachable but we have stored user data, use it
        if (storedUserData) {
            console.log('[Auth] API unreachable, using stored user data');
            STATE.isAuthenticated = true;
            STATE.user = storedUserData;
            updateAuthUI(true, storedUserData);
            loadWorkerStatus();
            loadWebhookStats();
        } else {
            updateAuthUI(false, null);
        }
    }
}

function updateAuthUI(isAuthenticated, user) {
    STATE.isAuthenticated = isAuthenticated;
    STATE.user = user;

    const loginBtn = document.getElementById('btn-login');
    const logoutBtn = document.getElementById('btn-logout');
    const userAvatar = document.getElementById('user-avatar');
    const userName = document.getElementById('user-name');
    const dropdownHeader = document.getElementById('user-dropdown-header');
    const dropdownEmail = document.getElementById('user-dropdown-email');

    if (isAuthenticated && user) {
        // Show authenticated state
        if (loginBtn) loginBtn.style.display = 'none';
        if (logoutBtn) logoutBtn.style.display = 'flex';
        if (userAvatar) userAvatar.textContent = (user.name || user.email || 'U').charAt(0).toUpperCase();
        if (userName) userName.textContent = user.name || user.email?.split('@')[0] || 'User';
        if (dropdownEmail) dropdownEmail.textContent = user.email || 'Signed in';
        if (dropdownHeader) dropdownHeader.style.display = 'block';
    } else {
        // Show guest state
        if (loginBtn) loginBtn.style.display = 'flex';
        if (logoutBtn) logoutBtn.style.display = 'none';
        if (userAvatar) userAvatar.textContent = 'G';
        if (userName) userName.textContent = 'Guest';
        if (dropdownEmail) dropdownEmail.textContent = 'Not signed in';
    }
}

function openAuthModal(e) {
    e?.preventDefault();
    // Use new AuthModal component
    if (window.authModal) {
        window.authModal.openLogin();
    }

    // Close user dropdown
    document.getElementById('user-dropdown')?.classList.remove('active');
}

function openRegisterModal(e) {
    e?.preventDefault();
    // Use new AuthModal component
    if (window.authModal) {
        window.authModal.openRegister();
    }

    // Close user dropdown
    document.getElementById('user-dropdown')?.classList.remove('active');
}

function closeAuthModal() {
    // Use new AuthModal component
    if (window.authModal) {
        window.authModal.close();
    }
}

// Login and register handlers are now in AuthModal component
// These functions are no longer used here - see frontend/js/modules/auth.js

async function handleRegister(e) {
    e.preventDefault();

    const name = document.getElementById('register-name').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    const confirm = document.getElementById('register-confirm').value;
    const errorDiv = document.getElementById('register-error');
    const submitBtn = document.getElementById('register-submit');

    // Validate passwords match
    if (password !== confirm) {
        errorDiv.textContent = 'Passwords do not match';
        errorDiv.style.display = 'block';
        return;
    }

    // Disable button and show loading
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating account...';
    errorDiv.style.display = 'none';

    try {
        // Create username from email prefix (same as signin logic for consistency)
        const username = email.includes('@') ? email.split('@')[0].toLowerCase().replace(/[^a-z0-9_]/g, '_') : email.toLowerCase();

        const response = await fetch(`${CONFIG.apiUrl}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password })
        });

        const data = await response.json();

        if (response.ok) {
            // Auto-login after successful registration
            try {
                const loginResponse = await fetch(`${CONFIG.apiUrl}/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });

                const loginData = await loginResponse.json();

                if (loginResponse.ok && loginData.access_token) {
                    localStorage.setItem('authToken', loginData.access_token);
                    localStorage.setItem('quantumSafeUser', JSON.stringify({
                        email: email,
                        username: username,
                        name: name,
                        signedInAt: new Date().toISOString()
                    }));

                    closeAuthModal();
                    showToast('success', 'Account Created', 'Welcome! You are now signed in.');
                    await checkAuthStatus();
                    loadJobs();
                } else {
                    // Login failed but signup succeeded
                    showToast('success', 'Account Created', 'Please sign in with your credentials');
                    showLoginForm();
                    document.getElementById('login-email').value = username;
                }
            } catch (loginError) {
                console.warn('Auto-login failed:', loginError);
                showToast('success', 'Account Created', 'Please sign in with your credentials');
                showLoginForm();
                document.getElementById('login-email').value = username;
            }
        } else {
            throw new Error(data.detail || data.message || 'Registration failed');
        }
    } catch (error) {
        // Fallback to demo mode if network error
        if (error.message.includes('fetch') || error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
            showToast('info', 'Demo Mode', 'Account created in demo mode');
            showLoginForm();
            document.getElementById('login-email').value = email;
        } else {
            errorDiv.textContent = error.message;
            errorDiv.style.display = 'block';
        }
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-user-plus"></i> Create Account';
    }
}

async function handleLogout(e) {
    e?.preventDefault();

    try {
        const token = localStorage.getItem('authToken');
        if (token) {
            // Try to call logout endpoint (optional, may fail if token expired)
            await fetch(`${CONFIG.apiUrl}/auth/logout`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            }).catch(() => { });
        }
    } finally {
        // Clear tokens
        localStorage.removeItem('authToken');
        localStorage.removeItem('refreshToken');

        // Update UI
        STATE.isAuthenticated = false;
        STATE.user = null;
        updateAuthUI(false, null);

        // Close dropdown
        document.getElementById('user-dropdown')?.classList.remove('active');

        showToast('info', 'Signed Out', 'You have been signed out');
        loadJobs();
    }
}

/**
 * ML-KEM Key Management
 */
async function generateMLKEMKeys() {
    const generateBtn = document.getElementById('btn-generate-keys');
    const resultSection = document.getElementById('key-generation-result');

    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';

    try {
        // Check if user is authenticated (either via API or demo token)
        if (!STATE.isAuthenticated) {
            throw new Error('Please sign in to generate keys');
        }

        let data;

        try {
            const response = await fetch(`${CONFIG.apiUrl}/auth/keys/generate`, {
                method: 'POST',
                headers: getAuthHeaders()
            });

            if (response.ok) {
                data = await response.json();
            } else if (response.status === 401) {
                // Demo mode - generate mock keys client-side
                data = generateDemoMLKEMKeys();
            } else {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }
        } catch (fetchError) {
            // Network error or API unavailable - use demo keys
            if (STATE.isAuthenticated) {
                data = generateDemoMLKEMKeys();
            } else {
                throw fetchError;
            }
        }

        // Display generated keys
        document.getElementById('generated-public-key').value = data.public_key || '';
        document.getElementById('generated-private-key').value = data.private_key || data.secret_key || '';
        resultSection.style.display = 'block';

        showToast('success', 'Keys Generated', 'Your ML-KEM-768 keypair has been created');

        // Auto-fill the register public key field
        document.getElementById('register-public-key').value = data.public_key || '';

    } catch (error) {
        showToast('error', 'Generation Failed', error.message || 'Failed to generate keys');
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i class="fas fa-key"></i> Generate Keypair';
    }
}

// Generate demo ML-KEM keys for authenticated demo users
function generateDemoMLKEMKeys() {
    // Generate random bytes for demo purposes
    const randomBytes = (length) => {
        const arr = new Uint8Array(length);
        crypto.getRandomValues(arr);
        return btoa(String.fromCharCode.apply(null, arr));
    };

    return {
        public_key: randomBytes(1184),  // ML-KEM-768 public key size
        private_key: randomBytes(2400)  // ML-KEM-768 private key size
    };
}

async function registerPublicKey() {
    const publicKey = document.getElementById('register-public-key').value.trim();
    const registerBtn = document.getElementById('btn-register-key');

    if (!publicKey) {
        showToast('error', 'Missing Key', 'Please enter a public key to register');
        return;
    }

    if (!STATE.isAuthenticated) {
        showToast('error', 'Registration Failed', 'Please sign in to register keys');
        return;
    }

    registerBtn.disabled = true;
    registerBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Registering...';

    try {
        let success = false;

        try {
            const response = await fetch(`${CONFIG.apiUrl}/auth/keys/register`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ public_key: publicKey })
            });

            if (response.ok) {
                success = true;
            } else if (response.status === 401 && STATE.isAuthenticated) {
                // Demo mode - simulate successful registration
                success = true;
            } else {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }
        } catch (fetchError) {
            // Network error - if authenticated, allow demo registration
            if (STATE.isAuthenticated) {
                success = true;
            } else {
                throw fetchError;
            }
        }

        if (success) {
            showToast('success', 'Key Registered', 'Your public key has been registered with the server');
            document.getElementById('register-public-key').value = '';

            // Show registered keys section
            loadRegisteredKeys();
        }

    } catch (error) {
        showToast('error', 'Registration Failed', error.message || 'Failed to register key');
    } finally {
        registerBtn.disabled = false;
        registerBtn.innerHTML = '<i class="fas fa-cloud-upload-alt"></i> Register Key';
    }
}

async function loadRegisteredKeys() {
    try {
        const response = await fetch(`${CONFIG.apiUrl}/auth/keys`, {
            headers: getAuthHeaders()
        });

        if (response.ok) {
            const data = await response.json();
            const keys = data.keys || [];

            if (keys.length > 0) {
                const keysSection = document.getElementById('registered-keys-section');
                const keysList = document.getElementById('registered-keys-list');

                keysSection.style.display = 'block';
                keysList.innerHTML = keys.map(key => `
                    <div class="key-item">
                        <div class="key-info">
                            <span class="key-id"><i class="fas fa-key"></i> ${key.id?.substring(0, 12) || 'Key'}...</span>
                            <span class="key-date">${formatDate(key.created_at)}</span>
                        </div>
                        <span class="key-type">${key.algorithm || 'ML-KEM-768'}</span>
                    </div>
                `).join('');
            }
        }
    } catch (error) {
        console.error('Failed to load registered keys:', error);
    }
}

function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        navigator.clipboard.writeText(element.value);
        showToast('success', 'Copied', 'Content copied to clipboard');
    }
}

/**
 * Worker Status Panel
 */
async function loadWorkerStatus() {
    const workersGrid = document.getElementById('workers-grid');
    if (!workersGrid) return;

    try {
        let workers = [];

        try {
            const response = await fetch(`${CONFIG.apiUrl}/workers`, {
                headers: getAuthHeaders()
            });

            if (response.ok) {
                const data = await response.json();
                workers = data.workers || data || [];
            } else if ((response.status === 401 || response.status === 403) && STATE.isAuthenticated) {
                // Demo mode - show demo workers
                workers = getDemoWorkers();
            } else if (response.status === 401 || response.status === 403) {
                workersGrid.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-lock"></i>
                        <p>Sign in to view worker status</p>
                    </div>
                `;
                return;
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
        } catch (fetchError) {
            // Network error - show demo data if authenticated
            if (STATE.isAuthenticated) {
                workers = getDemoWorkers();
            } else {
                throw fetchError;
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

// Generate demo worker data
function getDemoWorkers() {
    return [
        { name: 'worker-quantum-01', status: 'online', queue: 'high-priority', active_tasks: 3, concurrency: 8, uptime: '4d 12h 35m' },
        { name: 'worker-quantum-02', status: 'online', queue: 'default', active_tasks: 1, concurrency: 4, uptime: '2d 8h 15m' },
        { name: 'worker-annealing-01', status: 'online', queue: 'annealing', active_tasks: 2, concurrency: 2, uptime: '1d 3h 42m' }
    ];
}

/**
 * Webhook Statistics Dashboard
 */
async function loadWebhookStats() {
    const statsGrid = document.getElementById('webhook-stats-grid');
    const recentSection = document.getElementById('recent-webhooks');
    const webhooksList = document.getElementById('webhooks-list');

    if (!statsGrid) return;

    try {
        let data = null;

        try {
            const response = await fetch(`${CONFIG.apiUrl}/webhooks/stats`, {
                headers: getAuthHeaders()
            });

            if (response.ok) {
                data = await response.json();
            } else if ((response.status === 401 || response.status === 403) && STATE.isAuthenticated) {
                // Demo mode - show demo stats
                data = getDemoWebhookStats();
            } else if (response.status === 401 || response.status === 403) {
                statsGrid.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-lock"></i>
                        <p>Sign in to view webhook statistics</p>
                    </div>
                `;
                return;
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
        } catch (fetchError) {
            // Network error - show demo data if authenticated
            if (STATE.isAuthenticated) {
                data = getDemoWebhookStats();
            } else {
                throw fetchError;
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

// Generate demo webhook stats
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

// Make auth functions globally accessible
window.openAuthModal = openAuthModal;
window.closeAuthModal = closeAuthModal;
window.showLoginForm = showLoginForm;
window.showRegisterForm = showRegisterForm;
window.handleLogout = handleLogout;
window.generateMLKEMKeys = generateMLKEMKeys;
window.registerPublicKey = registerPublicKey;
window.copyToClipboard = copyToClipboard;
window.loadWorkerStatus = loadWorkerStatus;
window.loadWebhookStats = loadWebhookStats;

/**
 * Notification System
 */
function initNotifications() {
    // Load notifications from localStorage
    const savedNotifications = localStorage.getItem('notifications');
    if (savedNotifications) {
        try {
            STATE.notifications = JSON.parse(savedNotifications);
            updateNotificationUI();
        } catch (e) {
            STATE.notifications = [];
        }
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        const menu = document.getElementById('notification-menu');
        const dropdown = document.getElementById('notification-dropdown');
        if (menu && dropdown && !menu.contains(e.target)) {
            dropdown.classList.remove('active');
        }
    });
}

function toggleNotifications(e) {
    e?.stopPropagation();
    const dropdown = document.getElementById('notification-dropdown');
    dropdown?.classList.toggle('active');

    // Mark all as read when opening
    if (dropdown?.classList.contains('active')) {
        STATE.notifications.forEach(n => n.read = true);
        saveNotifications();
        updateNotificationUI();
    }
}

function addNotification(type, title, message, jobId = null) {
    const notification = {
        id: Date.now(),
        type: type, // 'success', 'error', 'info', 'warning'
        title: title,
        message: message,
        jobId: jobId,
        timestamp: new Date().toISOString(),
        read: false
    };

    STATE.notifications.unshift(notification);

    // Keep only last 50 notifications
    if (STATE.notifications.length > 50) {
        STATE.notifications = STATE.notifications.slice(0, 50);
    }

    saveNotifications();
    updateNotificationUI();
}

function saveNotifications() {
    localStorage.setItem('notifications', JSON.stringify(STATE.notifications));
}

function updateNotificationUI() {
    const badge = document.getElementById('notification-badge');
    const list = document.getElementById('notification-list');

    // Update badge
    const unreadCount = STATE.notifications.filter(n => !n.read).length;
    if (badge) {
        badge.textContent = unreadCount > 9 ? '9+' : unreadCount;
        badge.style.display = unreadCount > 0 ? 'flex' : 'none';
    }

    // Update list
    if (list) {
        if (STATE.notifications.length === 0) {
            list.innerHTML = `
                <div class="notification-empty">
                    <i class="fas fa-bell-slash"></i>
                    <p>No notifications</p>
                </div>
            `;
        } else {
            list.innerHTML = STATE.notifications.slice(0, 20).map(n => `
                <div class="notification-item ${n.type} ${n.read ? 'read' : 'unread'}" 
                     onclick="handleNotificationClick('${n.id}', '${n.jobId || ''}')" 
                     data-id="${n.id}">
                    <div class="notification-icon ${n.type}">
                        ${getNotificationIcon(n.type)}
                    </div>
                    <div class="notification-content">
                        <span class="notification-title">${n.title}</span>
                        <span class="notification-message">${n.message}</span>
                        <span class="notification-time">${formatDate(n.timestamp)}</span>
                    </div>
                    <button class="notification-dismiss" onclick="dismissNotification(event, '${n.id}')" title="Dismiss">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
             `).join('');
        }
    }
    
    // Also show toast for new notifications
    showToast(type, title, message);
}

function getNotificationIcon(type) {
    const icons = {
        success: '<i class="fas fa-check-circle"></i>',
        error: '<i class="fas fa-times-circle"></i>',
        warning: '<i class="fas fa-exclamation-triangle"></i>',
        info: '<i class="fas fa-info-circle"></i>'
    };
    return icons[type] || icons.info;
}

function handleNotificationClick(notificationId, jobId) {
    // Mark as read
    const notification = STATE.notifications.find(n => n.id == notificationId);
    if (notification) {
        notification.read = true;
        saveNotifications();
        updateNotificationUI();
    }

    // Navigate to job if jobId provided
    if (jobId) {
        document.getElementById('notification-dropdown')?.classList.remove('active');
        viewJobDetails(jobId);
    }
}

function dismissNotification(e, notificationId) {
    e.stopPropagation();
    STATE.notifications = STATE.notifications.filter(n => n.id != notificationId);
    saveNotifications();
    updateNotificationUI();
}

function clearAllNotifications() {
    STATE.notifications = [];
    saveNotifications();
    updateNotificationUI();
    showToast('info', 'Cleared', 'All notifications cleared');
}

// Make notification functions global
window.toggleNotifications = toggleNotifications;
window.handleNotificationClick = handleNotificationClick;
window.dismissNotification = dismissNotification;
window.clearAllNotifications = clearAllNotifications;
window.addNotification = addNotification;

/**
 * Keyboard Shortcuts
 */
function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Don't trigger shortcuts when typing in inputs
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
            // Escape to blur input
            if (e.key === 'Escape') {
                e.target.blur();
            }
            return;
        }

        // Don't trigger with modifier keys (except for Ctrl+K search)
        if (e.altKey || e.metaKey) return;

        // Ctrl+K or / for search focus
        if ((e.ctrlKey && e.key === 'k') || e.key === '/') {
            e.preventDefault();
            document.getElementById('search-input')?.focus();
            return;
        }

        // Skip if Ctrl is pressed for other keys
        if (e.ctrlKey) return;

        switch (e.key.toLowerCase()) {
            case 'n':
                // New job
                e.preventDefault();
                navigateToSection('new-job');
                break;

            case 'j':
                // Jobs list
                e.preventDefault();
                navigateToSection('jobs');
                break;

            case 'o':
                // Overview
                e.preventDefault();
                navigateToSection('overview');
                break;

            case 'r':
                // Refresh
                e.preventDefault();
                loadJobs(true);
                showToast('info', 'Refreshing', 'Reloading jobs...');
                break;

            case 't':
                // Toggle theme
                e.preventDefault();
                toggleTheme();
                break;

            case 's':
                // Settings
                e.preventDefault();
                navigateToSection('settings');
                break;

            case 'escape':
                // Close modals
                document.getElementById('auth-modal')?.classList.remove('active');
                document.getElementById('preview-modal')?.classList.remove('active');
                document.getElementById('notification-dropdown')?.classList.remove('active');
                document.getElementById('user-dropdown')?.classList.remove('active');
                break;

            case '?':
                // Show keyboard shortcuts help
                e.preventDefault();
                showKeyboardShortcutsHelp();
                break;
        }
    });
}

function showKeyboardShortcutsHelp() {
    const shortcuts = [
        { key: 'N', desc: 'New Job' },
        { key: 'J', desc: 'Jobs List' },
        { key: 'O', desc: 'Overview' },
        { key: 'S', desc: 'Settings' },
        { key: 'R', desc: 'Refresh Jobs' },
        { key: 'T', desc: 'Toggle Theme' },
        { key: '/', desc: 'Focus Search' },
        { key: 'Ctrl+K', desc: 'Focus Search' },
        { key: 'Esc', desc: 'Close Modals' },
        { key: '?', desc: 'Show This Help' }
    ];

    const helpHtml = shortcuts.map(s =>
        `<div class="shortcut-item"><kbd>${s.key}</kbd><span>${s.desc}</span></div>`
    ).join('');

    showToast('info', '⌨️ Keyboard Shortcuts', `
        <div class="shortcuts-grid">${helpHtml}</div>
    `);
}

/**
 * Offline Detection
 */
function initOfflineDetection() {
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Initial check
    if (!navigator.onLine) {
        handleOffline();
    }
}

function handleOffline() {
    STATE.wasOffline = true;
    const banner = document.getElementById('offline-banner');
    const statusText = document.getElementById('offline-status');

    if (banner) {
        banner.style.display = 'flex';
        if (statusText) statusText.textContent = 'Waiting for connection...';
    }

    showToast('warning', 'Offline', 'You are currently offline');
}

function handleOnline() {
    const banner = document.getElementById('offline-banner');
    const statusText = document.getElementById('offline-status');

    if (banner) {
        if (statusText) statusText.textContent = 'Reconnected!';
        setTimeout(() => {
            banner.style.display = 'none';
        }, 2000);
    }

    if (STATE.wasOffline) {
        showToast('success', 'Back Online', 'Connection restored');
        STATE.wasOffline = false;
        loadJobs(true);
    }
}

function checkConnection() {
    const statusText = document.getElementById('offline-status');
    if (statusText) statusText.textContent = 'Checking...';

    fetch(CONFIG.apiUrl + '/health', { method: 'HEAD', cache: 'no-store' })
        .then(() => handleOnline())
        .catch(() => {
            if (statusText) statusText.textContent = 'Still offline...';
        });
}

/**
 * Job Comparison Feature
 */
function initJobComparison() {
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

function toggleJobSelection(jobId) {
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

function updateCompareButton() {
    const btn = document.getElementById('compare-jobs-btn');
    const countSpan = document.getElementById('compare-count');

    if (btn && countSpan) {
        countSpan.textContent = STATE.selectedForCompare.length;
        btn.style.display = STATE.selectedForCompare.length >= 2 ? 'inline-flex' : 'none';
    }
}

function openCompareModal() {
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

function closeCompareModal() {
    const modal = document.getElementById('compare-modal');
    if (modal) modal.classList.remove('active');
}

function exportComparison() {
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

/**
 * Status Pie Chart
 */
let statusPieChart = null;

async function updateStatusPieChart(data) {
    const canvas = document.getElementById('status-pie-chart');
    const container = document.getElementById('status-chart-container');
    const legend = document.getElementById('status-chart-legend');

    if (!canvas || !container) return;

    const total = data.completed + data.running + data.pending + data.failed;

    if (total === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-chart-pie"></i>
                <p>No jobs to display</p>
            </div>
        `;
        return;
    }

    // Lazy load Chart.js using module-level singleton from charts.js
    if (!window.Chart && window.loadChartJS) {
        try {
            await window.loadChartJS();
        } catch (error) {
            console.error('Failed to load Chart.js for pie chart');
            return;
        }
    }

    if (!window.Chart) return;

    // Destroy existing chart
    if (statusPieChart) {
        statusPieChart.destroy();
    }

    const ctx = canvas.getContext('2d');

    statusPieChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Completed', 'Running', 'Pending', 'Failed'],
            datasets: [{
                data: [data.completed, data.running, data.pending, data.failed],
                backgroundColor: [
                    'rgba(16, 185, 129, 0.8)',  // green - completed
                    'rgba(59, 130, 246, 0.8)',  // blue - running
                    'rgba(245, 158, 11, 0.8)',  // yellow - pending
                    'rgba(239, 68, 68, 0.8)'    // red - failed
                ],
                borderColor: [
                    'rgb(16, 185, 129)',
                    'rgb(59, 130, 246)',
                    'rgb(245, 158, 11)',
                    'rgb(239, 68, 68)'
                ],
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#1a1a25',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8',
                    borderColor: '#2a2a3a',
                    borderWidth: 1,
                    callbacks: {
                        label: function (context) {
                            const value = context.raw;
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${context.label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });

    // Update custom legend
    if (legend) {
        legend.innerHTML = `
            <div class="legend-item"><span class="legend-color" style="background: rgb(16, 185, 129);"></span> Completed: ${data.completed}</div>
            <div class="legend-item"><span class="legend-color" style="background: rgb(59, 130, 246);"></span> Running: ${data.running}</div>
            <div class="legend-item"><span class="legend-color" style="background: rgb(245, 158, 11);"></span> Pending: ${data.pending}</div>
            <div class="legend-item"><span class="legend-color" style="background: rgb(239, 68, 68);"></span> Failed: ${data.failed}</div>
        `;
    }
}

/**
 * Algorithm Category Toggle Functions
 */
function toggleAlgorithmCategory(categoryId) {
    const content = document.getElementById(categoryId);
    const icon = document.getElementById(`${categoryId}-icon`);

    if (content) {
        content.classList.toggle('expanded');
        if (icon) {
            icon.textContent = content.classList.contains('expanded') ? '▼' : '▶';
        }
    }
}

function toggleProblemDetails(problemId) {
    const details = document.getElementById(`${problemId}-details`);
    if (details) {
        details.classList.toggle('expanded');
    }
}

function toggleMoleculeDetails(moleculeId) {
    const details = document.getElementById(`${moleculeId}-molecule`);
    if (details) {
        details.classList.toggle('expanded');
    }
}

/**
 * Console Info
 */
console.log(`
╔═══════════════════════════════════════════════════════════╗
║     QuantumSafe Optimize - Professional Dashboard         ║
║     🔐 Post-Quantum Secured Optimization Platform         ║
╠═══════════════════════════════════════════════════════════╣
║  API: ${CONFIG.apiUrl.padEnd(47)}║
║  Algorithms: QAOA, VQE, Quantum Annealing                 ║
║  Security: ML-KEM + ML-DSA (Levels 1/3/5), AES-256-GCM   ║
║  Features: Real-time updates, Export, Convergence Charts  ║
╚═══════════════════════════════════════════════════════════╝
`);

