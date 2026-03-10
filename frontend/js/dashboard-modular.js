/**
 * QuantumSafe Optimize - Dashboard JavaScript
 * Professional Quantum Optimization Platform
 * Main Entry Point - ES6 Module Version
 * 
 * This file imports and initializes all modules.
 */

// Core modules
import { CONFIG, STATE } from './modules/config.js';
import { showToast } from './modules/toast.js';
import { initTheme, toggleTheme } from './modules/theme.js';
import { initNavigation, navigateToSection } from './modules/navigation.js';
import { initSearch, initMobileSearch, setLoadJobsCallback, clearFilters } from './modules/search.js';

// Auth and notifications
import {
    initAuth,
    initUserMenu,
    checkAuthStatus,
    updateAuthUI,
    setAuthCallbacks,
    openAuthModal,
    handleLogout
} from './modules/auth.js';
import {
    initNotifications,
    addNotification,
    toggleNotifications,
    clearAllNotifications,
    setViewJobDetailsCallback as setNotificationJobCallback
} from './modules/notifications.js';

// Jobs management
import {
    loadJobs,
    goToPage,
    updateJobsUI,
    updateStats,
    exportJob,
    exportAllJobs,
    setJobsCallbacks,
    cloneJob,
    copySolution,
    exportChartAsPNG
} from './modules/jobs.js?v=2.4.0';
import {
    initJobForm,
    loadTemplate,
    submitJob,
    setJobFormCallbacks
} from './modules/job-form.js?v=2.4.0';
import {
    viewJobDetails,
    initJobDetailActions,
    setJobDetailsCallbacks,
    toggleConfigPanel
} from './modules/job-details.js';

// WebSocket and connectivity
import {
    connectJobWebSocket,
    disconnectJobWebSocket,
    setConnectivityCallback,
    setJobCallbacks as setWebSocketJobCallbacks
} from './modules/websocket.js';
import {
    initConnectivity,
    initPqcStatus,
    checkApiStatus,
    initOfflineDetection,
    setConnectivityCallbacks
} from './modules/connectivity.js';

// Visualizations and charts
import {
    initConvergenceChart,
    updateStatusPieChart
} from './modules/charts.js';
import { updateJobVisualizations } from './modules/visualizations.js';

// Features
import { initSecurityTests, generateMLKEMKeys, registerPublicKey, copyToClipboard } from './modules/security.js';
import { initSettings, applyDefaultSettings } from './modules/settings.js';
import { loadWorkerStatus } from './modules/workers.js';
import { loadWebhookStats } from './modules/webhooks.js';
import { initJobComparison, openCompareModal, closeCompareModal, exportComparison } from './modules/comparison.js';
import {
    initKeyboardShortcuts, setKeyboardCallbacks,
    toggleAlgorithmCategory, toggleProblemDetails, toggleMoleculeDetails
} from './modules/keyboard.js';
import { initModal, setSubmitJobCallback } from './modules/modal.js';
import { analyzeProblem } from './modules/ai-suggestions.js';
import { checkConnection } from './modules/connectivity.js';
import { toggleGraphLabels, resetGraphView } from './modules/visualizations.js';

// Error handling and validation
import { initErrorBoundary } from './modules/error-boundary.js';
import { initAuthValidation } from './modules/validation.js';

/**
 * Wire up module dependencies
 */
function wireModuleDependencies() {
    // Search module needs loadJobs
    setLoadJobsCallback(loadJobs);

    // Auth module needs loadJobs, loadWorkerStatus, loadWebhookStats
    setAuthCallbacks(loadJobs, loadWorkerStatus, loadWebhookStats);

    // Jobs module needs viewJobDetails, updateStatusPieChart
    setJobsCallbacks(viewJobDetails, updateStatusPieChart);

    // Job form needs loadJobs
    setJobFormCallbacks(loadJobs);

    // Job details needs loadJobs, connectWebSocket, updateVisualizations, initConvergenceChart
    setJobDetailsCallbacks(loadJobs, connectJobWebSocket, updateJobVisualizations, initConvergenceChart);

    // WebSocket needs updateConnectivityItem callback and job callbacks
    setConnectivityCallback((service, status, latency, label) => {
        import('./modules/connectivity.js').then(m => m.updateConnectivityItem(service, status, latency, label));
    });
    setWebSocketJobCallbacks(loadJobs, viewJobDetails);

    // Notifications need viewJobDetails
    setNotificationJobCallback(viewJobDetails);

    // Connectivity needs loadJobs
    setConnectivityCallbacks(loadJobs);

    // Keyboard needs loadJobs
    setKeyboardCallbacks(loadJobs);

    // Modal needs submitJob
    setSubmitJobCallback(submitJob);
}

/**
 * Initialize all app modules
 */
async function initializeApp() {
    // Initialize error boundary first to catch any startup errors
    initErrorBoundary();

    console.log('🚀 Initializing QuantumSafe Optimize Dashboard...');

    // Wire up module dependencies first
    wireModuleDependencies();

    // Apply default settings
    applyDefaultSettings();

    // Initialize theme
    initTheme();

    // Initialize navigation
    initNavigation();

    // Initialize search
    initSearch();
    initMobileSearch();

    // Initialize authentication
    initAuth();
    initUserMenu();
    initAuthValidation();  // Enable form validation on auth fields

    // Initialize notifications
    initNotifications();

    // Initialize job form
    initJobForm();

    // Initialize job detail actions
    initJobDetailActions();

    // Initialize modals
    initModal();

    // Initialize settings
    initSettings();

    // Initialize security tests
    initSecurityTests();

    // Initialize job comparison
    initJobComparison();

    // Initialize keyboard shortcuts
    initKeyboardShortcuts();

    // Initialize connectivity monitoring
    initConnectivity();
    initPqcStatus();
    initOfflineDetection();

    // Check authentication status
    await checkAuthStatus();

    // Load initial data
    await loadJobs(true);

    // Start periodic health checks
    setInterval(checkApiStatus, CONFIG.healthCheckInterval);

    console.log('✅ Dashboard initialized successfully');
}

// Make key functions globally accessible for HTML onclick handlers
window.STATE = STATE;
window.CONFIG = CONFIG;
window.showToast = showToast;
window.toggleTheme = toggleTheme;
window.navigateToSection = navigateToSection;
window.loadJobs = loadJobs;
window.goToPage = goToPage;
window.viewJobDetails = viewJobDetails;
window.exportJob = exportJob;
window.exportAllJobs = exportAllJobs;
window.loadTemplate = loadTemplate;
window.checkApiStatus = checkApiStatus;
window.addNotification = addNotification;

// Auth and notifications
window.openAuthModal = openAuthModal;
window.handleLogout = handleLogout;
window.toggleNotifications = toggleNotifications;
window.clearAllNotifications = clearAllNotifications;

// Job management
window.cloneJob = cloneJob;
window.copySolution = copySolution;
window.exportChartAsPNG = exportChartAsPNG;
window.toggleConfigPanel = toggleConfigPanel;
window.clearFilters = clearFilters;

// Comparison
window.openCompareModal = openCompareModal;
window.closeCompareModal = closeCompareModal;
window.exportComparison = exportComparison;

// Security and crypto
window.generateMLKEMKeys = generateMLKEMKeys;
window.registerPublicKey = registerPublicKey;
window.copyToClipboard = copyToClipboard;

// Connectivity
window.checkConnection = checkConnection;

// Workers and webhooks
window.loadWorkerStatus = loadWorkerStatus;
window.loadWebhookStats = loadWebhookStats;

// Visualization
window.toggleGraphLabels = toggleGraphLabels;
window.resetGraphView = resetGraphView;

// Algorithm info toggles
window.toggleAlgorithmCategory = toggleAlgorithmCategory;
window.toggleProblemDetails = toggleProblemDetails;
window.toggleMoleculeDetails = toggleMoleculeDetails;

// AI suggestions
window.analyzeProblem = analyzeProblem;

// Testing stubs (no separate module - define inline)
window.runTests = function() {
    showToast('info', 'Tests', 'Running security tests...');
    if (typeof initSecurityTests === 'function') initSecurityTests();
};
window.runBenchmarks = function() {
    showToast('info', 'Benchmarks', 'Benchmarking feature coming soon');
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}

/**
 * Console Info Banner
 */
console.log(`
╔═══════════════════════════════════════════════════════════╗
║     QuantumSafe Optimize - Professional Dashboard         ║
║     🔐 Post-Quantum Secured Optimization Platform         ║
╠═══════════════════════════════════════════════════════════╣
║  Architecture: ES6 Modular                                ║
║  Algorithms: QAOA, VQE, Quantum Annealing                 ║
║  Security: ML-KEM + ML-DSA (Levels 1/3/5), AES-256-GCM   ║
║  Features: Real-time updates, Export, Convergence Charts  ║
╚═══════════════════════════════════════════════════════════╝
`);
