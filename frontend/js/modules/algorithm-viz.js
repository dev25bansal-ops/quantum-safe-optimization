/**
 * Algorithm-Specific Visualizations Module
 * Provides specialized visualizations for QAOA, VQE, and Annealing
 */

import { STATE } from './config.js';
import { showToast } from './toast.js';

/**
 * Initialize algorithm-specific visualizations
 */
export function initAlgorithmVisualizations() {
    // Called when navigating to algorithm pages
}

/**
 * Render QAOA-specific visualizations
 */
export function renderQAOAVisualizations(job) {
    const container = document.getElementById('qaoa-visualizations');
    if (!container || !job) return;

    const result = job.result || {};
    const config = job.problem_config || {};

    container.innerHTML = `
        <div class="algorithm-viz-panel qaoa">
            <!-- Problem Structure -->
            <div class="viz-section">
                <div class="viz-header">
                    <h4><i class="fas fa-project-diagram"></i> Problem Structure</h4>
                </div>
                <div class="viz-body">
                    <div class="problem-stats">
                        <div class="stat-item">
                            <span class="stat-label">Problem Type</span>
                            <span class="stat-value">${config.problem_type || 'MaxCut'}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Nodes/Qubits</span>
                            <span class="stat-value">${config.num_qubits || config.graph?.length || '-'}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Edges</span>
                            <span class="stat-value">${countEdges(config.graph)}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">P Layers</span>
                            <span class="stat-value">${config.p_layers || config.depth || '-'}</span>
                        </div>
                    </div>

                    ${config.graph ? `
                        <div class="graph-preview">
                            <canvas id="problem-graph-preview" width="300" height="200"></canvas>
                        </div>
                    ` : ''}
                </div>
            </div>

            <!-- Solution Analysis -->
            <div class="viz-section">
                <div class="viz-header">
                    <h4><i class="fas fa-check-circle"></i> Solution Analysis</h4>
                </div>
                <div class="viz-body">
                    <div class="solution-metrics">
                        <div class="metric-card highlight">
                            <span class="metric-label">Cut Value</span>
                            <span class="metric-value">${result.optimal_value?.toFixed(4) || '-'}</span>
                        </div>
                        <div class="metric-card">
                            <span class="metric-label">Approximation Ratio</span>
                            <span class="metric-value">${result.approximation_ratio ? (result.approximation_ratio * 100).toFixed(1) + '%' : '-'}</span>
                        </div>
                        <div class="metric-card">
                            <span class="metric-label">Best Sample</span>
                            <span class="metric-value code">${result.optimal_bitstring?.substring(0, 12) || '-'}...</span>
                        </div>
                        <div class="metric-card">
                            <span class="metric-label">Iterations</span>
                            <span class="metric-value">${result.iterations || result.convergence_history?.length || '-'}</span>
                        </div>
                    </div>

                    ${result.optimal_params ? `
                        <div class="optimal-params">
                            <h5>Optimal Parameters</h5>
                            <div class="params-display">
                                <div class="param-group">
                                    <span class="param-label">γ (gamma)</span>
                                    <div class="param-values">
                                        ${(Array.isArray(result.optimal_params.gamma) ? result.optimal_params.gamma : [result.optimal_params.gamma || 0]).map((g, i) => 
                                            `<span class="param-value">γ${i+1} = ${g.toFixed(4)}</span>`
                                        ).join('')}
                                    </div>
                                </div>
                                <div class="param-group">
                                    <span class="param-label">β (beta)</span>
                                    <div class="param-values">
                                        ${(Array.isArray(result.optimal_params.beta) ? result.optimal_params.beta : [result.optimal_params.beta || 0]).map((b, i) => 
                                            `<span class="param-value">β${i+1} = ${b.toFixed(4)}</span>`
                                        ).join('')}
                                    </div>
                                </div>
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>

            <!-- Measurement Distribution -->
            ${result.counts ? `
                <div class="viz-section">
                    <div class="viz-header">
                        <h4><i class="fas fa-chart-bar"></i> Measurement Distribution</h4>
                    </div>
                    <div class="viz-body">
                        <div class="distribution-chart">
                            <canvas id="qaoa-distribution-chart"></canvas>
                        </div>
                        <div class="distribution-stats">
                            <span>Top outcome probability: ${getTopProbability(result.counts)}%</span>
                            <span>Total unique outcomes: ${Object.keys(result.counts).length}</span>
                        </div>
                    </div>
                </div>
            ` : ''}

            <!-- Circuit Information -->
            <div class="viz-section">
                <div class="viz-header">
                    <h4><i class="fas fa-microchip"></i> Circuit Information</h4>
                </div>
                <div class="viz-body">
                    <div class="circuit-stats">
                        <div class="circuit-stat">
                            <i class="fas fa-layer-group"></i>
                            <span class="stat-text">Depth: ${result.circuit_depth || '-'}</span>
                        </div>
                        <div class="circuit-stat">
                            <i class="fas fa-door-open"></i>
                            <span class="stat-text">Gates: ${result.gate_count || '-'}</span>
                        </div>
                        <div class="circuit-stat">
                            <i class="fas fa-bullseye"></i>
                            <span class="stat-text">Shots: ${job.shots || '-'}</span>
                        </div>
                        <div class="circuit-stat">
                            <i class="fas fa-clock"></i>
                            <span class="stat-text">Time: ${result.execution_time || '-'}s</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Render graph preview if available
    if (config.graph) {
        setTimeout(() => renderProblemGraphPreview(config.graph, result.optimal_bitstring), 100);
    }
}

/**
 * Render VQE-specific visualizations
 */
export function renderVQEVisualizations(job) {
    const container = document.getElementById('vqe-visualizations');
    if (!container || !job) return;

    const result = job.result || {};
    const config = job.problem_config || {};

    container.innerHTML = `
        <div class="algorithm-viz-panel vqe">
            <!-- Molecular Information (for chemistry) -->
            ${config.molecule || config.hamiltonian_type === 'molecular' ? `
                <div class="viz-section">
                    <div class="viz-header">
                        <h4><i class="fas fa-atom"></i> Molecular Information</h4>
                    </div>
                    <div class="viz-body">
                        <div class="molecule-display">
                            <div class="molecule-visual" id="molecule-3d">
                                <!-- 3D molecule visualization placeholder -->
                                <div class="molecule-placeholder">
                                    <i class="fas fa-cubes"></i>
                                    <span>${config.molecule || 'H2'}</span>
                                </div>
                            </div>
                            <div class="molecule-info">
                                <div class="info-row">
                                    <span class="label">Molecule</span>
                                    <span class="value">${config.molecule || '-'}</span>
                                </div>
                                <div class="info-row">
                                    <span class="label">Basis Set</span>
                                    <span class="value">${config.basis_set || 'STO-3G'}</span>
                                </div>
                                <div class="info-row">
                                    <span class="label">Active Electrons</span>
                                    <span class="value">${config.active_electrons || '-'}</span>
                                </div>
                                <div class="info-row">
                                    <span class="label">Active Orbitals</span>
                                    <span class="value">${config.active_orbitals || '-'}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            ` : ''}

            <!-- Energy Results -->
            <div class="viz-section">
                <div class="viz-header">
                    <h4><i class="fas fa-bolt"></i> Energy Results</h4>
                </div>
                <div class="viz-body">
                    <div class="energy-results">
                        <div class="energy-card primary">
                            <div class="energy-label">Ground State Energy</div>
                            <div class="energy-value">${result.optimal_value?.toFixed(6) || '-'}</div>
                            <div class="energy-unit">Hartree</div>
                        </div>
                        <div class="energy-card">
                            <div class="energy-label">Energy Variance</div>
                            <div class="energy-value">${result.energy_variance?.toFixed(6) || '-'}</div>
                            <div class="energy-unit">Ha²</div>
                        </div>
                        <div class="energy-card">
                            <div class="energy-label">Fidelity</div>
                            <div class="energy-value">${result.fidelity ? (result.fidelity * 100).toFixed(2) + '%' : '-'}</div>
                            <div class="energy-unit"></div>
                        </div>
                        <div class="energy-card">
                            <div class="energy-label">Iterations</div>
                            <div class="energy-value">${result.iterations || '-'}</div>
                            <div class="energy-unit"></div>
                        </div>
                    </div>

                    ${result.classical_reference ? `
                        <div class="comparison-section">
                            <h5>Classical Reference Comparison</h5>
                            <div class="comparison-bar">
                                <div class="bar-label">
                                    <span>VQE Result</span>
                                    <span>${result.optimal_value?.toFixed(6)} Ha</span>
                                </div>
                                <div class="bar-track">
                                    <div class="bar-fill vqe" style="width: 50%"></div>
                                    <div class="bar-marker classical" style="left: ${calculateComparisonPosition(result.optimal_value, result.classical_reference)}%"></div>
                                </div>
                                <div class="bar-label">
                                    <span>Classical (CCSD)</span>
                                    <span>${result.classical_reference?.toFixed(6)} Ha</span>
                                </div>
                            </div>
                            <div class="error-analysis">
                                <span>Absolute Error: ${Math.abs(result.optimal_value - result.classical_reference)?.toFixed(6)} Ha</span>
                                <span>(${(Math.abs(result.optimal_value - result.classical_reference) * 27.2114).toFixed(4)} eV)</span>
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>

            <!-- Ansatz Information -->
            <div class="viz-section">
                <div class="viz-header">
                    <h4><i class="fas fa-circuit-board"></i> Ansatz Configuration</h4>
                </div>
                <div class="viz-body">
                    <div class="ansatz-info">
                        <div class="ansatz-param">
                            <span class="param-label">Ansatz Type</span>
                            <span class="param-value">${config.ansatz || 'UCCSD'}</span>
                        </div>
                        <div class="ansatz-param">
                            <span class="param-label">Parameters</span>
                            <span class="param-value">${result.num_params || config.num_params || '-'}</span>
                        </div>
                        <div class="ansatz-param">
                            <span class="param-label">Qubits</span>
                            <span class="param-value">${config.num_qubits || '-'}</span>
                        </div>
                        <div class="ansatz-param">
                            <span class="param-label">Entanglement</span>
                            <span class="param-value">${config.entanglement || 'full'}</span>
                        </div>
                    </div>

                    <div class="optimizer-info">
                        <h5>Optimizer Performance</h5>
                        <div class="optimizer-stats">
                            <span>Optimizer: ${config.optimizer || 'SPSA'}</span>
                            <span>Function Evaluations: ${result.function_evaluations || '-'}</span>
                            <span>Gradient Evaluations: ${result.gradient_evaluations || '-'}</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Wavefunction Analysis -->
            ${result.statevector || result.probabilities ? `
                <div class="viz-section">
                    <div class="viz-header">
                        <h4><i class="fas fa-wave-square"></i> Wavefunction Analysis</h4>
                    </div>
                    <div class="viz-body">
                        <div class="wavefunction-viz">
                            <canvas id="vqe-statevector-chart"></canvas>
                        </div>
                        <div class="dominant-states">
                            <h5>Dominant States</h5>
                            <div class="states-list">
                                ${getDominantStates(result.probabilities || result.statevector, 5)}
                            </div>
                        </div>
                    </div>
                </div>
            ` : ''}
        </div>
    `;
}

/**
 * Render Annealing-specific visualizations
 */
export function renderAnnealingVisualizations(job) {
    const container = document.getElementById('annealing-visualizations');
    if (!container || !job) return;

    const result = job.result || {};
    const config = job.problem_config || {};

    container.innerHTML = `
        <div class="algorithm-viz-panel annealing">
            <!-- QUBO/Ising Model -->
            <div class="viz-section">
                <div class="viz-header">
                    <h4><i class="fas fa-shapes"></i> Problem Model</h4>
                </div>
                <div class="viz-body">
                    <div class="model-info">
                        <div class="model-type">
                            <span class="type-badge ${config.model_type || 'qubo'}">${config.model_type || 'QUBO'}</span>
                        </div>
                        <div class="model-stats">
                            <div class="stat">
                                <span class="stat-label">Variables</span>
                                <span class="stat-value">${config.num_variables || config.num_qubits || '-'}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Interactions</span>
                                <span class="stat-value">${config.num_interactions || '-'}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Linear Terms</span>
                                <span class="stat-value">${config.num_linear || '-'}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Quadratic Terms</span>
                                <span class="stat-value">${config.num_quadratic || '-'}</span>
                            </div>
                        </div>
                    </div>

                    ${config.embedding ? `
                        <div class="embedding-info">
                            <h5>Hardware Embedding</h5>
                            <div class="embedding-stats">
                                <span>Chain Length: ${config.embedding.chain_length || '-'}</span>
                                <span>Physical Qubits: ${config.embedding.physical_qubits || '-'}</span>
                                <span>Chain Strength: ${config.embedding.chain_strength || '-'}</span>
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>

            <!-- Annealing Parameters -->
            <div class="viz-section">
                <div class="viz-header">
                    <h4><i class="fas fa-temperature-high"></i> Annealing Schedule</h4>
                </div>
                <div class="viz-body">
                    <div class="anneal-params">
                        <div class="param-card">
                            <span class="param-label">Annealing Time</span>
                            <span class="param-value">${config.annealing_time || 20} μs</span>
                        </div>
                        <div class="param-card">
                            <span class="param-label">Num Reads</span>
                            <span class="param-value">${config.num_reads || job.shots || 1000}</span>
                        </div>
                        <div class="param-card">
                            <span class="param-label">Programming Time</span>
                            <span class="param-value">${result.programming_time || '-'} ms</span>
                        </div>
                        <div class="param-card">
                            <span class="param-label">Readout Time</span>
                            <span class="param-value">${result.readout_time || '-'} ms</span>
                        </div>
                    </div>

                    ${config.anneal_schedule ? `
                        <div class="schedule-viz">
                            <canvas id="anneal-schedule-chart"></canvas>
                        </div>
                    ` : `
                        <div class="schedule-info default">
                            <i class="fas fa-info-circle"></i>
                            <span>Using default linear annealing schedule</span>
                        </div>
                    `}
                </div>
            </div>

            <!-- Solution Quality -->
            <div class="viz-section">
                <div class="viz-header">
                    <h4><i class="fas fa-chart-line"></i> Solution Quality</h4>
                </div>
                <div class="viz-body">
                    <div class="quality-metrics">
                        <div class="metric-card highlight">
                            <span class="metric-label">Best Energy</span>
                            <span class="metric-value">${result.optimal_value?.toFixed(4) || '-'}</span>
                        </div>
                        <div class="metric-card">
                            <span class="metric-label">Mean Energy</span>
                            <span class="metric-value">${result.mean_energy?.toFixed(4) || '-'}</span>
                        </div>
                        <div class="metric-card">
                            <span class="metric-label">Std Dev</span>
                            <span class="metric-value">${result.std_energy?.toFixed(4) || '-'}</span>
                        </div>
                        <div class="metric-card">
                            <span class="metric-label">Success Prob</span>
                            <span class="metric-value">${result.success_probability ? (result.success_probability * 100).toFixed(1) + '%' : '-'}</span>
                        </div>
                    </div>

                    <!-- Energy Histogram -->
                    ${result.energy_distribution || result.energies ? `
                        <div class="energy-histogram">
                            <canvas id="anneal-energy-histogram"></canvas>
                        </div>
                    ` : ''}

                    <!-- Occurrence Frequency -->
                    ${result.occurrences ? `
                        <div class="occurrence-table">
                            <h5>Top Solutions</h5>
                            <table class="mini-table">
                                <thead>
                                    <tr>
                                        <th>Sample</th>
                                        <th>Energy</th>
                                        <th>Occurrences</th>
                                        <th>%</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${Object.entries(result.occurrences).slice(0, 5).map(([sample, data]) => `
                                        <tr>
                                            <td><code>${sample.substring(0, 16)}...</code></td>
                                            <td>${data.energy?.toFixed(4) || '-'}</td>
                                            <td>${data.count}</td>
                                            <td>${((data.count / config.num_reads) * 100).toFixed(1)}%</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    ` : ''}
                </div>
            </div>

            <!-- Timing Breakdown -->
            <div class="viz-section">
                <div class="viz-header">
                    <h4><i class="fas fa-stopwatch"></i> Timing Breakdown</h4>
                </div>
                <div class="viz-body">
                    <div class="timing-bar-chart">
                        <div class="timing-item">
                            <span class="timing-label">QPU Access</span>
                            <div class="timing-bar">
                                <div class="timing-fill" style="width: ${result.qpu_time_percent || 60}%"></div>
                            </div>
                            <span class="timing-value">${result.qpu_time || '-'} ms</span>
                        </div>
                        <div class="timing-item">
                            <span class="timing-label">Programming</span>
                            <div class="timing-bar">
                                <div class="timing-fill" style="width: ${result.programming_percent || 30}%"></div>
                            </div>
                            <span class="timing-value">${result.programming_time || '-'} ms</span>
                        </div>
                        <div class="timing-item">
                            <span class="timing-label">Readout</span>
                            <div class="timing-bar">
                                <div class="timing-fill" style="width: ${result.readout_percent || 10}%"></div>
                            </div>
                            <span class="timing-value">${result.readout_time || '-'} ms</span>
                        </div>
                    </div>

                    <div class="total-time">
                        <span>Total QPU Time: </span>
                        <strong>${result.total_qpu_time || '-'} ms</strong>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Helper functions
function countEdges(graph) {
    if (!graph) return '-';
    if (Array.isArray(graph) && Array.isArray(graph[0])) {
        let count = 0;
        for (let i = 0; i < graph.length; i++) {
            for (let j = i + 1; j < graph[i].length; j++) {
                if (graph[i][j] > 0) count++;
            }
        }
        return count;
    }
    return graph.edges?.length || '-';
}

function getTopProbability(counts) {
    if (!counts) return '-';
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    const max = Math.max(...Object.values(counts));
    return ((max / total) * 100).toFixed(1);
}

function calculateComparisonPosition(vqe, classical) {
    if (!vqe || !classical) return 50;
    const diff = Math.abs(vqe - classical);
    return 50 + Math.min(diff * 1000, 40);
}

function getDominantStates(probs, n) {
    if (!probs) return '<span class="no-data">No data</span>';
    
    const entries = Array.isArray(probs) 
        ? probs.map((p, i) => [i.toString(2), p])
        : Object.entries(probs);
    
    const sorted = entries.sort((a, b) => b[1] - a[1]).slice(0, n);
    
    return sorted.map(([state, prob]) => `
        <div class="state-item">
            <span class="state-name">|${state}⟩</span>
            <span class="state-prob">${(prob * 100).toFixed(2)}%</span>
        </div>
    `).join('');
}

function renderProblemGraphPreview(graph, solution) {
    const canvas = document.getElementById('problem-graph-preview');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    // Simple graph rendering
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = 'rgba(10, 10, 20, 0.5)';
    ctx.fillRect(0, 0, width, height);

    // Would render actual graph here
    ctx.fillStyle = '#6366f1';
    ctx.font = '14px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('Graph Preview', width / 2, height / 2);
}

// Global exports
window.renderQAOAVisualizations = renderQAOAVisualizations;
window.renderVQEVisualizations = renderVQEVisualizations;
window.renderAnnealingVisualizations = renderAnnealingVisualizations;
