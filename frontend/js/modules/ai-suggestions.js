/**
 * AI Optimization Suggestions Module
 * Provides intelligent recommendations for quantum optimization based on problem analysis
 */

import { showToast } from './toast.js';
import { apiGet, apiPost } from './api.js';
import { CONFIG, STATE } from './config.js';

const PROBLEM_TEMPLATES = {
    maxcut: {
        name: 'Max-Cut Problem',
        category: 'combinatorial',
        algorithms: ['QAOA', 'VQE', 'Annealing'],
        recommendations: {
            optimal: 'QAOA',
            reason: 'QAOA is specifically designed for combinatorial optimization and excels at Max-Cut'
        }
    },
    tsp: {
        name: 'Traveling Salesman Problem',
        category: 'combinatorial',
        algorithms: ['QAOA', 'Annealing'],
        recommendations: {
            optimal: 'QAOA',
            reason: 'QAOA handles TSP constraints well with appropriate penalty terms'
        }
    },
    portfolio: {
        name: 'Portfolio Optimization',
        category: 'finance',
        algorithms: ['QAOA', 'VQE'],
        recommendations: {
            optimal: 'VQE',
            reason: 'VQE provides better handling of continuous variables and constraints'
        }
    },
    molecule: {
        name: 'Molecular Ground State',
        category: 'chemistry',
        algorithms: ['VQE'],
        recommendations: {
            optimal: 'VQE',
            reason: 'VQE is the standard for quantum chemistry calculations'
        }
    },
    grover: {
        name: 'Unstructured Search',
        category: 'search',
        algorithms: ['Grover'],
        recommendations: {
            optimal: 'Grover',
            reason: 'Grover provides quadratic speedup for unstructured search'
        }
    },
    factoring: {
        name: 'Integer Factorization',
        category: 'cryptography',
        algorithms: ['Shor'],
        recommendations: {
            optimal: 'Shor',
            reason: 'Shor\'s algorithm provides exponential speedup for factoring'
        }
    }
};

const OPTIMIZER_RECOMMENDATIONS = {
    qaoa: {
        small: { qubits: [2, 8], optimizer: 'COBYLA', reason: 'Good for small landscapes' },
        medium: { qubits: [8, 20], optimizer: 'SPSA', reason: 'Robust to noise, fewer evaluations' },
        large: { qubits: [20, null], optimizer: 'ADAM', reason: 'Scales well with parameter count' }
    },
    vqe: {
        small: { qubits: [2, 6], optimizer: 'L-BFGS-B', reason: 'Fast convergence for small systems' },
        medium: { qubits: [6, 12], optimizer: 'SPSA', reason: 'Noise-resilient gradient estimation' },
        large: { qubits: [12, null], optimizer: 'quantum_natural_gradient', reason: 'Optimal quantum landscape' }
    }
};

const HARDWARE_RECOMMENDATIONS = {
    simulator: {
        name: 'Aer Simulator',
        cost_factor: 0,
        suitable_for: ['development', 'testing', 'small_problems'],
        max_qubits: 40
    },
    ibmq_qasm: {
        name: 'IBM Quantum (QASM)',
        cost_factor: 1,
        suitable_for: ['production', 'research'],
        max_qubits: 127
    },
    ibmq_real: {
        name: 'IBM Quantum Hardware',
        cost_factor: 10,
        suitable_for: ['production', 'benchmarking'],
        max_qubits: 127
    },
    dwave: {
        name: 'D-Wave Quantum Annealer',
        cost_factor: 5,
        suitable_for: ['combinatorial', 'large_qubo'],
        max_qubits: 5000
    },
    aws_braket: {
        name: 'AWS Braket',
        cost_factor: 3,
        suitable_for: ['multi_provider', 'research'],
        max_qubits: 79
    }
};

/**
 * Initialize AI suggestions UI
 */
export function initAISuggestions() {
    const container = document.getElementById('ai-suggestions-container');
    if (!container) return;

    renderAISuggestionsUI(container);
}

/**
 * Render AI suggestions UI placeholder
 */
function renderAISuggestionsUI(container) {
    container.innerHTML = `
        <div class="ai-suggestions-panel">
            <div class="ai-header">
                <div class="ai-icon">
                    <i class="fas fa-brain"></i>
                </div>
                <div class="ai-title">
                    <h4>AI-Powered Optimization Suggestions</h4>
                    <p>Get intelligent recommendations based on your problem configuration</p>
                </div>
            </div>

            <div id="suggestions-content" class="suggestions-content">
                <div class="suggestion-placeholder">
                    <div class="placeholder-icon">
                        <i class="fas fa-lightbulb"></i>
                    </div>
                    <p>Configure your job parameters and click "Analyze" to receive AI-powered suggestions</p>
                    <button class="btn btn-primary" onclick="window.analyzeProblem()">
                        <i class="fas fa-magic"></i> Analyze Problem
                    </button>
                </div>
            </div>
        </div>
    `;
}

/**
 * Analyze problem and generate suggestions
 */
export async function analyzeProblem(config = null) {
    const contentEl = document.getElementById('suggestions-content');
    if (!contentEl) return;

    // Get current form values if config not provided
    const problemConfig = config || {
        problem_type: document.getElementById('problem-type')?.value,
        backend: document.getElementById('backend')?.value,
        num_qubits: parseInt(document.getElementById('qubits')?.value) || 5,
        optimizer: document.getElementById('optimizer')?.value,
        shots: parseInt(document.getElementById('shots')?.value) || 1024,
        p_layers: parseInt(document.getElementById('p-layers')?.value) || 2
    };

    contentEl.innerHTML = `
        <div class="suggestions-loading">
            <div class="spinner"></div>
            <p>Analyzing problem configuration...</p>
        </div>
    `;

    try {
        // Generate suggestions locally first (fast)
        const localSuggestions = generateLocalSuggestions(problemConfig);

        // Try to get AI-enhanced suggestions from backend
        let aiSuggestions = null;
        try {
            aiSuggestions = await apiPost('/ai/suggestions', problemConfig);
        } catch (e) {
            // Backend AI not available, use local
            aiSuggestions = null;
        }

        const suggestions = aiSuggestions || localSuggestions;

        renderSuggestions(contentEl, suggestions, problemConfig);

    } catch (error) {
        console.error('Error analyzing problem:', error);
        contentEl.innerHTML = `
            <div class="suggestions-error">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Failed to analyze problem. Using basic recommendations.</p>
                <button class="btn btn-outline" onclick="window.analyzeProblem()">Retry</button>
            </div>
        `;
        
        // Fall back to local suggestions
        setTimeout(() => {
            const localSuggestions = generateLocalSuggestions(problemConfig);
            renderSuggestions(contentEl, localSuggestions, problemConfig);
        }, 1000);
    }
}

/**
 * Generate local suggestions based on heuristics
 */
function generateLocalSuggestions(config) {
    const suggestions = {
        algorithm: null,
        optimizer: null,
        hardware: null,
        parameters: null,
        warnings: [],
        tips: []
    };

    const { problem_type, backend, num_qubits, optimizer, shots, p_layers } = config;

    // Algorithm suggestions
    if (problem_type === 'QAOA' || problem_type === 'MaxCut') {
        suggestions.algorithm = {
            current: problem_type,
            recommended: 'QAOA',
            confidence: 0.95,
            reasoning: 'QAOA is optimal for combinatorial optimization with quadratic objective functions'
        };
    } else if (problem_type === 'VQE') {
        suggestions.algorithm = {
            current: problem_type,
            recommended: 'VQE',
            confidence: 0.90,
            reasoning: 'VQE is ideal for quantum chemistry and continuous optimization problems'
        };
    }

    // Optimizer suggestions
    const optRecs = OPTIMIZER_RECOMMENDATIONS[problem_type?.toLowerCase()] || OPTIMIZER_RECOMMENDATIONS.qaoa;
    let optimizerSuggestion = optRecs.medium;

    if (num_qubits <= 8) {
        optimizerSuggestion = optRecs.small;
    } else if (num_qubits >= 20) {
        optimizerSuggestion = optRecs.large;
    }

    if (optimizer && optimizer !== optimizerSuggestion.optimizer) {
        suggestions.optimizer = {
            current: optimizer,
            recommended: optimizerSuggestion.optimizer,
            confidence: 0.85,
            reasoning: optimizerSuggestion.reason
        };
    }

    // Hardware suggestions
    if (num_qubits > 30 && backend?.includes('simulator')) {
        suggestions.hardware = {
            current: backend,
            recommended: 'ibmq_qasm',
            confidence: 0.80,
            reasoning: 'Large qubit counts may benefit from real hardware with error mitigation'
        };
    } else if (problem_type === 'Annealing' && backend !== 'dwave') {
        suggestions.hardware = {
            current: backend,
            recommended: 'dwave',
            confidence: 0.90,
            reasoning: 'D-Wave quantum annealers are optimized for QUBO problems'
        };
    }

    // Parameter suggestions
    suggestions.parameters = {
        shots: analyzeShots(shots, num_qubits),
        p_layers: analyzePLayers(p_layers, num_qubits)
    };

    // Warnings
    if (num_qubits > 20 && shots < 8192) {
        suggestions.warnings.push({
            type: 'warning',
            message: `Low shot count (${shots}) for ${num_qubits} qubits may result in poor statistics`,
            recommendation: 'Consider increasing shots to at least 8192'
        });
    }

    if (p_layers > 5 && num_qubits > 10) {
        suggestions.warnings.push({
            type: 'info',
            message: `High p (${p_layers}) with ${num_qubits} qubits creates a challenging optimization landscape`,
            recommendation: 'Consider starting with p=2-3 and increasing if needed'
        });
    }

    // Tips
    suggestions.tips = generateTips(config);

    return suggestions;
}

/**
 * Analyze shot count
 */
function analyzeShots(shots, qubits) {
    const min_shots = Math.max(1024, Math.pow(2, Math.min(qubits, 10)));
    const optimal_shots = Math.max(4096, Math.pow(2, Math.min(qubits, 12)));

    if (shots < min_shots) {
        return {
            current: shots,
            recommended: optimal_shots,
            reason: `Increase shots for better statistics with ${qubits} qubits`
        };
    }
    return { current: shots, recommended: shots, reason: 'Shot count is appropriate' };
}

/**
 * Analyze p layers
 */
function analyzePLayers(p, qubits) {
    const optimal_p = Math.max(1, Math.min(Math.ceil(qubits / 4), 4));

    if (p < optimal_p) {
        return {
            current: p,
            recommended: optimal_p,
            reason: `Increase p for better solution quality`
        };
    } else if (p > optimal_p + 2) {
        return {
            current: p,
            recommended: optimal_p,
            reason: `Lower p may converge faster with similar quality`
        };
    }
    return { current: p, recommended: p, reason: 'Layer count is optimal' };
}

/**
 * Generate tips based on configuration
 */
function generateTips(config) {
    const tips = [];

    if (config.num_qubits >= 10) {
        tips.push({
            icon: 'fas fa-chart-line',
            text: 'Use convergence plotting to monitor optimization progress'
        });
    }

    if (config.shots >= 4096) {
        tips.push({
            icon: 'fas fa-shield-alt',
            text: 'Consider error mitigation techniques like ZNE for better accuracy'
        });
    }

    if (config.problem_type === 'QAOA') {
        tips.push({
            icon: 'fas fa-random',
            text: 'Try multiple random initial points to avoid local minima'
        });
    }

    if (config.backend?.includes('ibmq')) {
        tips.push({
            icon: 'fas fa-clock',
            text: 'Check queue times and select less busy backends for faster execution'
        });
    }

    return tips;
}

/**
 * Render suggestions
 */
function renderSuggestions(container, suggestions, config) {
    container.innerHTML = `
        <div class="suggestions-results">
            <!-- Algorithm Suggestion -->
            ${suggestions.algorithm ? `
                <div class="suggestion-card algorithm">
                    <div class="suggestion-header">
                        <div class="suggestion-icon">
                            <i class="fas fa-atom"></i>
                        </div>
                        <div class="suggestion-title">
                            <h5>Algorithm</h5>
                            <span class="confidence-badge ${getConfidenceClass(suggestions.algorithm.confidence)}">
                                ${(suggestions.algorithm.confidence * 100).toFixed(0)}% confidence
                            </span>
                        </div>
                    </div>
                    <div class="suggestion-body">
                        <div class="comparison">
                            <div class="current">
                                <span class="label">Current</span>
                                <span class="value">${suggestions.algorithm.current}</span>
                            </div>
                            <div class="arrow">
                                ${suggestions.algorithm.current !== suggestions.algorithm.recommended ? '→' : '='}
                            </div>
                            <div class="recommended">
                                <span class="label">Recommended</span>
                                <span class="value ${suggestions.algorithm.current !== suggestions.algorithm.recommended ? 'highlight' : ''}">${suggestions.algorithm.recommended}</span>
                            </div>
                        </div>
                        <p class="reasoning">${suggestions.algorithm.reasoning}</p>
                        ${suggestions.algorithm.current !== suggestions.algorithm.recommended ? `
                            <button class="btn btn-sm btn-primary" onclick="window.applySuggestion('algorithm', '${suggestions.algorithm.recommended}')">
                                Apply Recommendation
                            </button>
                        ` : ''}
                    </div>
                </div>
            ` : ''}

            <!-- Optimizer Suggestion -->
            ${suggestions.optimizer ? `
                <div class="suggestion-card optimizer">
                    <div class="suggestion-header">
                        <div class="suggestion-icon">
                            <i class="fas fa-sliders-h"></i>
                        </div>
                        <div class="suggestion-title">
                            <h5>Optimizer</h5>
                            <span class="confidence-badge ${getConfidenceClass(suggestions.optimizer.confidence)}">
                                ${(suggestions.optimizer.confidence * 100).toFixed(0)}% confidence
                            </span>
                        </div>
                    </div>
                    <div class="suggestion-body">
                        <div class="comparison">
                            <div class="current">
                                <span class="label">Current</span>
                                <span class="value">${suggestions.optimizer.current}</span>
                            </div>
                            <div class="arrow">→</div>
                            <div class="recommended">
                                <span class="label">Recommended</span>
                                <span class="value highlight">${suggestions.optimizer.recommended}</span>
                            </div>
                        </div>
                        <p class="reasoning">${suggestions.optimizer.reasoning}</p>
                        <button class="btn btn-sm btn-primary" onclick="window.applySuggestion('optimizer', '${suggestions.optimizer.recommended}')">
                            Apply Recommendation
                        </button>
                    </div>
                </div>
            ` : ''}

            <!-- Hardware Suggestion -->
            ${suggestions.hardware ? `
                <div class="suggestion-card hardware">
                    <div class="suggestion-header">
                        <div class="suggestion-icon">
                            <i class="fas fa-server"></i>
                        </div>
                        <div class="suggestion-title">
                            <h5>Backend</h5>
                            <span class="confidence-badge ${getConfidenceClass(suggestions.hardware.confidence)}">
                                ${(suggestions.hardware.confidence * 100).toFixed(0)}% confidence
                            </span>
                        </div>
                    </div>
                    <div class="suggestion-body">
                        <div class="comparison">
                            <div class="current">
                                <span class="label">Current</span>
                                <span class="value">${suggestions.hardware.current}</span>
                            </div>
                            <div class="arrow">→</div>
                            <div class="recommended">
                                <span class="label">Recommended</span>
                                <span class="value highlight">${suggestions.hardware.recommended}</span>
                            </div>
                        </div>
                        <p class="reasoning">${suggestions.hardware.reasoning}</p>
                        <button class="btn btn-sm btn-primary" onclick="window.applySuggestion('backend', '${suggestions.hardware.recommended}')">
                            Apply Recommendation
                        </button>
                    </div>
                </div>
            ` : ''}

            <!-- Parameter Suggestions -->
            <div class="suggestion-card parameters">
                <div class="suggestion-header">
                    <div class="suggestion-icon">
                        <i class="fas fa-cogs"></i>
                    </div>
                    <div class="suggestion-title">
                        <h5>Parameters</h5>
                    </div>
                </div>
                <div class="suggestion-body">
                    <div class="param-grid">
                        <div class="param-item">
                            <span class="param-label">Shots</span>
                            <div class="param-value-group">
                                <span class="current">${suggestions.parameters?.shots?.current || config.shots}</span>
                                ${suggestions.parameters?.shots?.current !== suggestions.parameters?.shots?.recommended ? `
                                    <span class="arrow">→</span>
                                    <span class="recommended">${suggestions.parameters?.shots?.recommended}</span>
                                ` : ''}
                            </div>
                        </div>
                        <div class="param-item">
                            <span class="param-label">P Layers</span>
                            <div class="param-value-group">
                                <span class="current">${suggestions.parameters?.p_layers?.current || config.p_layers}</span>
                                ${suggestions.parameters?.p_layers?.current !== suggestions.parameters?.p_layers?.recommended ? `
                                    <span class="arrow">→</span>
                                    <span class="recommended">${suggestions.parameters?.p_layers?.recommended}</span>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Warnings -->
            ${suggestions.warnings?.length > 0 ? `
                <div class="suggestions-warnings">
                    ${suggestions.warnings.map(w => `
                        <div class="warning-item ${w.type}">
                            <div class="warning-icon">
                                <i class="fas ${w.type === 'warning' ? 'fa-exclamation-triangle' : 'fa-info-circle'}"></i>
                            </div>
                            <div class="warning-content">
                                <p class="warning-message">${w.message}</p>
                                <p class="warning-recommendation">${w.recommendation}</p>
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : ''}

            <!-- Tips -->
            ${suggestions.tips?.length > 0 ? `
                <div class="suggestions-tips">
                    <h5><i class="fas fa-lightbulb"></i> Tips</h5>
                    <ul class="tips-list">
                        ${suggestions.tips.map(t => `
                            <li>
                                <i class="${t.icon}"></i>
                                <span>${t.text}</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
            ` : ''}

            <!-- Actions -->
            <div class="suggestions-actions">
                <button class="btn btn-ghost" onclick="window.analyzeProblem()">
                    <i class="fas fa-sync"></i> Re-analyze
                </button>
                <button class="btn btn-primary" onclick="window.applyAllSuggestions()">
                    <i class="fas fa-check-double"></i> Apply All Recommendations
                </button>
            </div>
        </div>
    `;
}

/**
 * Get confidence class for styling
 */
function getConfidenceClass(confidence) {
    if (confidence >= 0.9) return 'high';
    if (confidence >= 0.7) return 'medium';
    return 'low';
}

/**
 * Apply a single suggestion
 */
function applySuggestion(field, value) {
    const fieldMap = {
        algorithm: 'problem-type',
        optimizer: 'optimizer',
        backend: 'backend',
        shots: 'shots',
        p_layers: 'p-layers'
    };

    const elementId = fieldMap[field];
    const element = document.getElementById(elementId);

    if (element) {
        element.value = value;
        element.dispatchEvent(new Event('change'));
        showToast('success', 'Applied', `${field} set to ${value}`);
    }
}

/**
 * Apply all recommendations
 */
function applyAllSuggestions() {
    const suggestions = window.currentSuggestions || {};
    let applied = 0;

    if (suggestions.algorithm?.recommended) {
        applySuggestion('algorithm', suggestions.algorithm.recommended);
        applied++;
    }
    if (suggestions.optimizer?.recommended) {
        applySuggestion('optimizer', suggestions.optimizer.recommended);
        applied++;
    }
    if (suggestions.hardware?.recommended) {
        applySuggestion('backend', suggestions.hardware.recommended);
        applied++;
    }

    if (applied > 0) {
        showToast('success', 'Applied', `${applied} recommendations applied`);
    } else {
        showToast('info', 'No Changes', 'Your current configuration is already optimal');
    }
}

/**
 * Get cost estimate for problem
 */
export async function getCostEstimate(config) {
    try {
        const response = await apiPost('/costs/estimate', config);
        return response;
    } catch (error) {
        // Return estimated costs based on heuristics
        return estimateCostsLocally(config);
    }
}

/**
 * Estimate costs locally
 */
function estimateCostsLocally(config) {
    const { problem_type, backend, num_qubits, shots, p_layers } = config;

    let cost = {
        estimated_credits: 0,
        estimated_time_seconds: 0,
        breakdown: {}
    };

    // Base cost calculation
    const circuitDepth = p_layers * 2 + 10; // rough estimate
    const gateCount = num_qubits * circuitDepth;

    if (backend?.includes('simulator')) {
        cost.estimated_credits = 0;
        cost.estimated_time_seconds = Math.ceil((shots * gateCount) / 10000);
        cost.breakdown = {
            'Computation': 'Free (simulator)',
            'Queue Time': '0s'
        };
    } else if (backend?.includes('dwave')) {
        cost.estimated_credits = Math.ceil(shots / 100);
        cost.estimated_time_seconds = 30;
        cost.breakdown = {
            'Annealing Time': '~30s',
            'Readout': '~5s',
            'Queue': 'Varies'
        };
    } else if (backend?.includes('ibmq') || backend?.includes('ibm')) {
        const minutes = Math.ceil((shots * circuitDepth) / 5000);
        cost.estimated_credits = minutes;
        cost.estimated_time_seconds = minutes * 60;
        cost.breakdown = {
            'Execution': `${minutes} min`,
            'Queue': '5-30 min (varies)',
            'Readout': '~2s'
        };
    } else if (backend?.includes('braket')) {
        const minutes = Math.ceil((shots * circuitDepth) / 5000);
        cost.estimated_credits = minutes * 2;
        cost.estimated_time_seconds = minutes * 60;
        cost.breakdown = {
            'Task Execution': `$${(minutes * 0.30).toFixed(2)}`,
            'Per-shot': `$${(shots * 0.0001).toFixed(2)}`,
            'Total': `$${(minutes * 0.30 + shots * 0.0001).toFixed(2)}`
        };
    }

    return cost;
}

/**
 * Render cost estimate display
 */
export function renderCostEstimate(config) {
    const container = document.getElementById('cost-estimate-section');
    if (!container) return null;

    getCostEstimate(config).then(cost => {
        container.innerHTML = `
            <div class="cost-estimate-card">
                <div class="cost-header">
                    <h4><i class="fas fa-coins"></i> Estimated Cost</h4>
                    <span class="backend-name">${config.backend || 'Simulator'}</span>
                </div>
                <div class="cost-body">
                    <div class="cost-main">
                        <span class="cost-value">${cost.estimated_credits}</span>
                        <span class="cost-unit">credits</span>
                    </div>
                    <div class="cost-time">
                        <i class="fas fa-clock"></i>
                        <span>~${formatTime(cost.estimated_time_seconds)}</span>
                    </div>
                </div>
                <div class="cost-breakdown">
                    ${Object.entries(cost.breakdown).map(([key, value]) => `
                        <div class="breakdown-item">
                            <span class="breakdown-key">${key}</span>
                            <span class="breakdown-value">${value}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    });
}

/**
 * Format time nicely
 */
function formatTime(seconds) {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

// Global exports
window.analyzeProblem = analyzeProblem;
window.applySuggestion = applySuggestion;
window.applyAllSuggestions = applyAllSuggestions;
window.currentSuggestions = null;
