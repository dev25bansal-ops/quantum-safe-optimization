/**
 * Dashboard Integration Module
 * Imports and integrates all new dashboard features
 */

// Import all modules
import { initAdvancedSimulatorOptions, getSimulatorConfig } from './advanced-simulator.js';
import { initWebhookManagement, loadWebhookStats, loadWebhookHistory } from './webhooks.js';
import { initAISuggestions, analyzeProblem, getCostEstimate, renderCostEstimate } from './ai-suggestions.js';
import { initKeyManagement } from './key-management.js';
import { 
    renderQAOAVisualizations, 
    renderVQEVisualizations, 
    renderAnnealingVisualizations 
} from './algorithm-viz.js';
import { 
    initConvergenceChart,
    initMeasurementHistogram,
    initStatevectorChart,
    initEnergyDistributionChart,
    initProbabilityChart,
    initParameterChart,
    loadChartJS
} from './charts.js';
import { 
    updateJobVisualizations,
    renderBitstringViz,
    renderGraphVisualization,
    renderVQEEnergyLandscape
} from './visualizations.js';
import { showToast } from './toast.js';
import { apiGet, apiPost } from './api.js';
import { STATE, CONFIG } from './config.js';

// Integration state
const integrationState = {
    modulesLoaded: false,
    currentJobType: null,
    costEstimateShown: false
};

/**
 * Initialize all dashboard enhancements
 */
export async function initDashboardEnhancements() {
    console.log('[Dashboard Integration] Initializing enhancements...');

    // Initialize modules based on current section
    initModulesForSection();

    // Set up event listeners for section navigation
    setupNavigationListeners();

    // Enhance job form with AI suggestions and cost estimation
    enhanceJobForm();

    // Add dashboard homepage widgets
    enhanceDashboardHomepage();

    // Set up real-time updates
    setupRealtimeUpdates();

    // Add accessibility improvements
    enhanceAccessibility();

    // Initialize help and tutorial
    initHelpSystem();

    integrationState.modulesLoaded = true;
    console.log('[Dashboard Integration] All enhancements loaded');
}

/**
 * Initialize modules for current section
 */
function initModulesForSection() {
    const currentSection = STATE.currentSection || 'overview';

    switch (currentSection) {
        case 'new-job':
            initAdvancedSimulatorOptions();
            initAISuggestions();
            break;
        case 'settings':
            initKeyManagement();
            break;
        case 'security':
            initKeyManagement();
            initWebhookManagement();
            break;
    }
}

/**
 * Set up listeners for section navigation
 */
function setupNavigationListeners() {
    document.querySelectorAll('.nav-item[data-section]').forEach(item => {
        item.addEventListener('click', () => {
            const section = item.dataset.section;
            setTimeout(() => initModulesForSection(), 100);
        });
    });
}

/**
 * Enhance job form with AI suggestions and cost estimation
 */
function enhanceJobForm() {
    const jobForm = document.getElementById('job-form');
    if (!jobForm) return;

    // Add AI Suggestions container after form
    const formActions = jobForm.querySelector('.form-actions');
    if (formActions && !document.getElementById('ai-suggestions-container')) {
        const aiContainer = document.createElement('div');
        aiContainer.id = 'ai-suggestions-container';
        aiContainer.className = 'ai-suggestions-wrapper';
        formActions.parentNode.insertBefore(aiContainer, formActions);
    }

    // Add Cost Estimate section
    const submitBtn = jobForm.querySelector('button[type="submit"]');
    if (submitBtn && !document.getElementById('cost-estimate-section')) {
        const costSection = document.createElement('div');
        costSection.id = 'cost-estimate-section';
        costSection.className = 'cost-estimate-wrapper';
        submitBtn.parentNode.insertBefore(costSection, submitBtn);
    }

    // Add Analyze button
    const buttonGroup = jobForm.querySelector('.form-actions');
    if (buttonGroup && !document.getElementById('analyze-job-btn')) {
        const analyzeBtn = document.createElement('button');
        analyzeBtn.type = 'button';
        analyzeBtn.id = 'analyze-job-btn';
        analyzeBtn.className = 'btn btn-secondary';
        analyzeBtn.innerHTML = '<i class="fas fa-magic"></i> Analyze Configuration';
        analyzeBtn.addEventListener('click', handleAnalyzeJob);
        buttonGroup.insertBefore(analyzeBtn, buttonGroup.firstChild);
    }

    // Add cost estimation on form changes
    const formInputs = jobForm.querySelectorAll('input, select');
    formInputs.forEach(input => {
        input.addEventListener('change', debounce(updateCostEstimate, 500));
    });

    // Integrate simulator config on submission
    const originalSubmit = window.submitJob;
    if (originalSubmit) {
        window.submitJob = async function() {
            const simulatorConfig = getSimulatorConfig();
            if (simulatorConfig && document.getElementById('backend')?.value === 'advanced_simulator') {
                const jobData = window.buildJobData ? window.buildJobData() : {};
                jobData.simulator_config = simulatorConfig;
            }
            return originalSubmit.call(this);
        };
    }
}

/**
 * Handle analyze job button click
 */
async function handleAnalyzeJob() {
    const problemType = document.getElementById('problem-type')?.value;
    const backend = document.getElementById('backend')?.value;
    const qubits = parseInt(document.getElementById('qubits')?.value) ||
        parseInt(document.getElementById('qaoa-graph')?.value?.length) ||
        parseInt(document.getElementById('anneal-matrix')?.value?.length) || 5;
    const shots = parseInt(document.getElementById('shots')?.value) ||
        parseInt(document.getElementById('qaoa-shots')?.value) ||
        parseInt(document.getElementById('vqe-shots')?.value) || 1024;

    const config = {
        problem_type: problemType,
        backend,
        num_qubits: qubits,
        shots,
        optimizer: document.getElementById('optimizer')?.value || 'COBYLA',
        p_layers: parseInt(document.getElementById('p-layers')?.value) || 2
    };

    await analyzeProblem(config);
    updateCostEstimate();
}

/**
 * Update cost estimate display
 */
async function updateCostEstimate() {
    const backend = document.getElementById('backend')?.value;
    if (!backend) return;

    const config = {
        backend,
        num_qubits: parseInt(document.getElementById('qubits')?.value) || 5,
        shots: parseInt(document.getElementById('shots')?.value) || 1024,
        problem_type: document.getElementById('problem-type')?.value || 'QAOA'
    };

    renderCostEstimate(config);
}

/**
 * Enhance dashboard homepage
 */
function enhanceDashboardHomepage() {
    const overviewSection = document.getElementById('section-overview');
    if (!overviewSection) return;

    // Add quick stats if not present
    const statsGrid = overviewSection.querySelector('.stats-grid');
    if (statsGrid && !document.getElementById('quick-stats-enhanced')) {
        const enhancedStats = document.createElement('div');
        enhancedStats.id = 'quick-stats-enhanced';
        enhancedStats.className = 'quick-stats-enhanced';
        enhancedStats.innerHTML = `
            <div class="quick-stat-card">
                <div class="quick-stat-icon">
                    <i class="fas fa-bolt"></i>
                </div>
                <div class="quick-stat-content">
                    <span class="quick-stat-value" id="stat-success-rate">--%</span>
                    <span class="quick-stat-label">Success Rate</span>
                </div>
            </div>
            <div class="quick-stat-card">
                <div class="quick-stat-icon">
                    <i class="fas fa-clock"></i>
                </div>
                <div class="quick-stat-content">
                    <span class="quick-stat-value" id="stat-avg-time">--s</span>
                    <span class="quick-stat-label">Avg. Time</span>
                </div>
            </div>
            <div class="quick-stat-card">
                <div class="quick-stat-icon">
                    <i class="fas fa-server"></i>
                </div>
                <div class="quick-stat-content">
                    <span class="quick-stat-value" id="stat-active-backends">--</span>
                    <span class="quick-stat-label">Active Backends</span>
                </div>
            </div>
        `;
        statsGrid.appendChild(enhancedStats);
    }

    // Add activity feed if not present
    if (!document.getElementById('activity-feed-section')) {
        const activitySection = document.createElement('div');
        activitySection.id = 'activity-feed-section';
        activitySection.className = 'activity-feed-section';
        activitySection.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3><i class="fas fa-stream"></i> Recent Activity</h3>
                    <button class="btn btn-ghost btn-sm" onclick="refreshActivityFeed()">
                        <i class="fas fa-sync"></i>
                    </button>
                </div>
                <div class="card-body">
                    <div id="activity-feed" class="activity-feed">
                        <div class="activity-loading">
                            <i class="fas fa-spinner fa-spin"></i>
                            <span>Loading activity...</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        overviewSection.appendChild(activitySection);
        loadActivityFeed();
    }

    // Add quick actions
    if (!document.getElementById('quick-actions-section')) {
        const quickActions = document.createElement('div');
        quickActions.id = 'quick-actions-section';
        quickActions.className = 'quick-actions-section';
        quickActions.innerHTML = `
            <div class="quick-actions-grid">
                <button class="quick-action-btn" onclick="navigateToSection('new-job')">
                    <i class="fas fa-plus-circle"></i>
                    <span>New Job</span>
                </button>
                <button class="quick-action-btn" onclick="loadTemplate('maxcut')">
                    <i class="fas fa-cut"></i>
                    <span>Max-Cut Demo</span>
                </button>
                <button class="quick-action-btn" onclick="loadTemplate('h2')">
                    <i class="fas fa-atom"></i>
                    <span>H2 Molecule</span>
                </button>
                <button class="quick-action-btn" onclick="navigateToSection('settings')">
                    <i class="fas fa-cog"></i>
                    <span>Settings</span>
                </button>
            </div>
        `;
        overviewSection.insertBefore(quickActions, overviewSection.firstChild.nextSibling);
    }

    updateQuickStats();
}

/**
 * Load activity feed
 */
async function loadActivityFeed() {
    const feed = document.getElementById('activity-feed');
    if (!feed) return;

    try {
        let activities;
        try {
            activities = await apiGet('/activity/recent');
        } catch (e) {
            activities = getDemoActivity();
        }

        if (activities.length === 0) {
            feed.innerHTML = `
                <div class="activity-empty">
                    <i class="fas fa-inbox"></i>
                    <p>No recent activity</p>
                </div>
            `;
            return;
        }

        feed.innerHTML = activities.map(activity => `
            <div class="activity-item ${activity.type}">
                <div class="activity-icon">
                    <i class="fas ${getActivityIcon(activity.type)}"></i>
                </div>
                <div class="activity-content">
                    <span class="activity-title">${escapeHtml(activity.title)}</span>
                    <span class="activity-description">${escapeHtml(activity.description)}</span>
                    <span class="activity-time">${formatRelativeTime(activity.timestamp)}</span>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Failed to load activity feed:', error);
        feed.innerHTML = `
            <div class="activity-error">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Failed to load activity</p>
            </div>
        `;
    }
}

function getDemoActivity() {
    return [
        { type: 'job', title: 'QAOA job completed', description: 'Max-Cut optimization finished', timestamp: new Date(Date.now() - 300000).toISOString() },
        { type: 'key', title: 'Key generated', description: 'ML-KEM-768 keypair created', timestamp: new Date(Date.now() - 600000).toISOString() },
        { type: 'system', title: 'Backend connected', description: 'IBM Quantum backend online', timestamp: new Date(Date.now() - 900000).toISOString() },
        { type: 'job', title: 'VQE job submitted', description: 'H2 molecule ground state', timestamp: new Date(Date.now() - 1200000).toISOString() }
    ];
}

function getActivityIcon(type) {
    const icons = {
        job: 'fa-tasks',
        key: 'fa-key',
        system: 'fa-server',
        webhook: 'fa-bolt',
        user: 'fa-user'
    };
    return icons[type] || 'fa-circle';
}

function formatRelativeTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    const mins = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${days}d ago`;
}

/**
 * Update quick stats
 */
function updateQuickStats() {
    const jobs = STATE.jobs || [];
    
    if (jobs.length > 0) {
        const completed = jobs.filter(j => j.status === 'completed').length;
        const total = jobs.length;
        const successRate = total > 0 ? Math.round((completed / total) * 100) : 0;

        const successEl = document.getElementById('stat-success-rate');
        if (successEl) successEl.textContent = `${successRate}%`;

        const avgTimeEl = document.getElementById('stat-avg-time');
        if (avgTimeEl) {
            const times = jobs
                .filter(j => j.result?.execution_time)
                .map(j => parseFloat(j.result.execution_time));
            const avgTime = times.length > 0 
                ? (times.reduce((a, b) => a + b, 0) / times.length).toFixed(1)
                : '--';
            avgTimeEl.textContent = `${avgTime}s`;
        }
    }

    // Update active backends
    const activeBackends = document.querySelectorAll('.backend-status-indicator.online').length;
    const backendsEl = document.getElementById('stat-active-backends');
    if (backendsEl) backendsEl.textContent = activeBackends.toString();
}

/**
 * Set up real-time updates
 */
function setupRealtimeUpdates() {
    // Live metrics update interval
    setInterval(() => {
        updateQuickStats();
    }, 30000);

    // Activity feed refresh
    setInterval(() => {
        loadActivityFeed();
    }, 60000);
}

/**
 * Enhance accessibility
 */
function enhanceAccessibility() {
    // Add ARIA labels to interactive elements
    document.querySelectorAll('button:not([aria-label])').forEach(btn => {
        const text = btn.textContent?.trim() || btn.getAttribute('title');
        if (text) {
            btn.setAttribute('aria-label', text);
        }
    });

    // Add role attributes
    document.querySelectorAll('.nav-item').forEach(item => {
        item.setAttribute('role', 'button');
        item.setAttribute('tabindex', '0');
    });

    // Add keyboard navigation for custom elements
    document.querySelectorAll('.job-item, .worker-card, .webhook-item').forEach(item => {
        item.setAttribute('tabindex', '0');
        item.setAttribute('role', 'button');
        item.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                item.click();
            }
        });
    });

    // Add skip link
    if (!document.getElementById('skip-link')) {
        const skipLink = document.createElement('a');
        skipLink.id = 'skip-link';
        skipLink.href = '#main-content';
        skipLink.className = 'skip-link';
        skipLink.textContent = 'Skip to main content';
        document.body.insertBefore(skipLink, document.body.firstChild);
    }

    // Improve focus indicators
    const style = document.createElement('style');
    style.textContent = `
        .skip-link {
            position: absolute;
            top: -40px;
            left: 0;
            background: var(--primary);
            color: white;
            padding: 8px 16px;
            z-index: 10000;
            transition: top 0.3s;
        }
        .skip-link:focus {
            top: 0;
        }
        *:focus-visible {
            outline: 2px solid var(--primary);
            outline-offset: 2px;
        }
    `;
    document.head.appendChild(style);
}

/**
 * Initialize help system
 */
function initHelpSystem() {
    // Add help button to header
    const header = document.querySelector('.topbar .topbar-right');
    if (header && !document.getElementById('help-btn')) {
        const helpBtn = document.createElement('button');
        helpBtn.id = 'help-btn';
        helpBtn.className = 'btn btn-ghost btn-sm';
        helpBtn.innerHTML = '<i class="fas fa-question-circle"></i>';
        helpBtn.title = 'Help & Documentation';
        helpBtn.setAttribute('aria-label', 'Help and Documentation');
        helpBtn.addEventListener('click', showHelpPanel);
        header.insertBefore(helpBtn, header.firstChild);
    }

    // Create help panel
    if (!document.getElementById('help-panel')) {
        const helpPanel = document.createElement('div');
        helpPanel.id = 'help-panel';
        helpPanel.className = 'help-panel';
        helpPanel.innerHTML = `
            <div class="help-panel-content">
                <div class="help-header">
                    <h3><i class="fas fa-book"></i> Help & Documentation</h3>
                    <button class="btn btn-ghost btn-sm" onclick="closeHelpPanel()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="help-body">
                    <div class="help-section">
                        <h4>Quick Start</h4>
                        <ol>
                            <li>Select a problem type (QAOA, VQE, or Annealing)</li>
                            <li>Configure your problem parameters</li>
                            <li>Choose a quantum backend</li>
                            <li>Click "Submit Job" to run</li>
                        </ol>
                    </div>
                    <div class="help-section">
                        <h4>Keyboard Shortcuts</h4>
                        <div class="help-shortcuts">
                            <div class="shortcut"><kbd>N</kbd> New Job</div>
                            <div class="shortcut"><kbd>J</kbd> Jobs List</div>
                            <div class="shortcut"><kbd>O</kbd> Overview</div>
                            <div class="shortcut"><kbd>R</kbd> Refresh</div>
                            <div class="shortcut"><kbd>T</kbd> Toggle Theme</div>
                            <div class="shortcut"><kbd>?</kbd> Show Shortcuts</div>
                        </div>
                    </div>
                    <div class="help-section">
                        <h4>Resources</h4>
                        <ul class="help-links">
                            <li><a href="#" onclick="showTutorial()"><i class="fas fa-graduation-cap"></i> Interactive Tutorial</a></li>
                            <li><a href="/docs" target="_blank"><i class="fas fa-book"></i> API Documentation</a></li>
                            <li><a href="#" onclick="showKeyboardShortcutsHelp()"><i class="fas fa-keyboard"></i> Keyboard Shortcuts</a></li>
                        </ul>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(helpPanel);
    }
}

function showHelpPanel() {
    const panel = document.getElementById('help-panel');
    if (panel) {
        panel.classList.add('active');
    }
}

function closeHelpPanel() {
    const panel = document.getElementById('help-panel');
    if (panel) {
        panel.classList.remove('active');
    }
}

function showTutorial() {
    closeHelpPanel();
    showToast('info', 'Tutorial', 'Interactive tutorial coming soon!');
}

// Global functions
window.refreshActivityFeed = loadActivityFeed;
window.closeHelpPanel = closeHelpPanel;
window.showTutorial = showTutorial;
window.showHelpPanel = showHelpPanel;

/**
 * Enhance job details with algorithm-specific visualizations
 */
export function enhanceJobDetailsView(job) {
    if (!job) return;

    const algorithm = job.problem_type;
    const result = job.result;

    // Add algorithm-specific visualization container if not present
    const vizContainer = document.getElementById('algorithm-viz-container');
    if (!vizContainer) {
        const detailsSection = document.getElementById('section-job-details');
        if (detailsSection) {
            const container = document.createElement('div');
            container.id = 'algorithm-viz-container';
            container.className = 'algorithm-viz-container';
            detailsSection.appendChild(container);
        }
    }

    // Render algorithm-specific visualizations
    const targetContainer = document.getElementById('algorithm-viz-container');
    if (!targetContainer) return;

    switch (algorithm) {
        case 'QAOA':
            renderQAOAVisualizations(job);
            break;
        case 'VQE':
            renderVQEVisualizations(job);
            break;
        case 'ANNEALING':
            renderAnnealingVisualizations(job);
            break;
    }
}

/**
 * Debounce helper
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Escape HTML helper
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize on DOM load
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(initDashboardEnhancements, 500);
    });
}

export default {
    initDashboardEnhancements,
    enhanceJobDetailsView,
    loadActivityFeed,
    updateQuickStats,
    showHelpPanel,
    closeHelpPanel
};
