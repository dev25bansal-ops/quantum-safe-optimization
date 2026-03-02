/**
 * Configuration & State Management Module
 * Core configuration and application state
 */

// Configuration - use current origin to avoid CORS issues
export const CONFIG = {
    apiUrl: localStorage.getItem('apiUrl') || 'http://localhost:8001/api/v1',
    apiBase: localStorage.getItem('apiUrl')?.replace(/\/api\/v1\/?$/, '') || 'http://localhost:8001/api/v1',
    healthCheckInterval: 30000, // 30 seconds for health checks only
    maxRetries: 3
};

// Ansatz mapping for VQE (UI display -> backend value)
export const ANSATZ_MAPPING = {
    'hardware_efficient': 'hardware_efficient',
    'ry': 'hardware_efficient',
    'ryrz': 'hardware_efficient',
    'su2': 'su2',
    'uccsd': 'uccsd'
};

// Application State
export const STATE = {
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
    wasOffline: false,
    // Load failures tracking
    loadJobsFailures: 0,
    lastLoadAttempt: null
};

// Job Templates
export const JOB_TEMPLATES = {
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

// Update CONFIG dynamically
export function updateConfig(key, value) {
    CONFIG[key] = value;
    if (key === 'apiUrl') {
        CONFIG.apiBase = value.replace(/\/api\/v1\/?$/, '') || window.location.origin;
    }
}
