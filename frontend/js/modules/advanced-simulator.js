/**
 * Advanced Simulator Options Module
 * Handles noise models, error mitigation, and advanced simulation configurations
 */

import { showToast } from './toast.js';
import { apiGet, apiPost } from './api.js';

const NOISE_MODELS = {
    ibmq_manila: {
        name: 'IBM Quantum Manila',
        qubits: 5,
        single_qubit_error: 0.001,
        two_qubit_error: 0.01,
        readout_error: 0.02,
        t1: 150,
        t2: 100
    },
    ibmq_lima: {
        name: 'IBM Quantum Lima',
        qubits: 5,
        single_qubit_error: 0.0008,
        two_qubit_error: 0.012,
        readout_error: 0.018,
        t1: 120,
        t2: 80
    },
    ibmq_belem: {
        name: 'IBM Quantum Belem',
        qubits: 5,
        single_qubit_error: 0.0006,
        two_qubit_error: 0.009,
        readout_error: 0.015,
        t1: 180,
        t2: 120
    },
    ibmq_quito: {
        name: 'IBM Quantum Quito',
        qubits: 5,
        single_qubit_error: 0.0007,
        two_qubit_error: 0.011,
        readout_error: 0.02,
        t1: 140,
        t2: 90
    },
    custom: {
        name: 'Custom Noise Model',
        qubits: null,
        single_qubit_error: null,
        two_qubit_error: null,
        readout_error: null,
        t1: null,
        t2: null
    }
};

const ERROR_MITIGATION_METHODS = {
    none: {
        name: 'None',
        description: 'No error mitigation applied',
        overhead: 1,
        suitable_for: ['testing', 'development']
    },
    measurement_error_mitigation: {
        name: 'Measurement Error Mitigation',
        description: 'Calibrates readout errors using matrix inversion',
        overhead: 1,
        suitable_for: ['production', 'high-precision']
    },
    zero_noise_extrapolation: {
        name: 'Zero Noise Extrapolation (ZNE)',
        description: 'Extrapolates to zero noise by scaling circuit depth',
        overhead: 3,
        methods: ['linear', 'richardson', 'exponential'],
        suitable_for: ['research', 'high-accuracy']
    },
    probabilistic_error_cancellation: {
        name: 'Probabilistic Error Cancellation (PEC)',
        description: 'Uses quasi-probability distribution to cancel errors',
        overhead: 5,
        suitable_for: ['research', 'benchmarking']
    },
    readout_error_mitigation: {
        name: 'Readout Error Mitigation',
        description: 'Corrects measurement readout errors',
        overhead: 1.2,
        suitable_for: ['nisq', 'production']
    },
    dynamical_decoupling: {
        name: 'Dynamical Decoupling',
        description: 'Inserts pulse sequences to suppress decoherence',
        overhead: 1.1,
        sequences: ['XY4', 'XY8', 'CPMG'],
        suitable_for: ['long-circuits', 'noisy-backends']
    }
};

let simulatorState = {
    noiseModel: 'none',
    errorMitigation: 'none',
    customNoiseConfig: {},
    zneMethod: 'linear',
    ddSequence: 'XY4'
};

/**
 * Initialize advanced simulator options UI
 */
export function initAdvancedSimulatorOptions() {
    const container = document.getElementById('advanced-simulator-config');
    if (!container) return;

    renderSimulatorOptionsUI(container);
    bindSimulatorOptionEvents();
    loadSavedSimulatorConfig();
}

/**
 * Render the simulator options UI
 */
function renderSimulatorOptionsUI(container) {
    container.innerHTML = `
        <div class="advanced-simulator-panel">
            <div class="simulator-section">
                <div class="section-header">
                    <h4><i class="fas fa-volume-mute"></i> Noise Model</h4>
                    <button class="btn btn-ghost btn-xs" onclick="window.toggleNoiseHelp()">
                        <i class="fas fa-question-circle"></i>
                    </button>
                </div>
                
                <div class="form-group">
                    <label for="noise-model-select">Select Noise Model</label>
                    <select id="noise-model-select" class="form-select">
                        <option value="none">None (Ideal Simulation)</option>
                        <optgroup label="IBM Quantum Noise Models">
                            ${Object.entries(NOISE_MODELS)
                                .filter(([k]) => k !== 'custom')
                                .map(([key, model]) => 
                                    `<option value="${key}">${model.name} (${model.qubits} qubits)</option>`
                                ).join('')}
                        </optgroup>
                        <option value="custom">Custom Noise Model</option>
                    </select>
                </div>

                <div id="noise-model-details" class="noise-details" style="display: none;">
                    <div class="noise-stats-grid">
                        <div class="noise-stat">
                            <span class="stat-label">Qubits</span>
                            <span class="stat-value" id="noise-qubits">-</span>
                        </div>
                        <div class="noise-stat">
                            <span class="stat-label">1Q Error</span>
                            <span class="stat-value" id="noise-1q">-</span>
                        </div>
                        <div class="noise-stat">
                            <span class="stat-label">2Q Error</span>
                            <span class="stat-value" id="noise-2q">-</span>
                        </div>
                        <div class="noise-stat">
                            <span class="stat-label">Readout Error</span>
                            <span class="stat-value" id="noise-readout">-</span>
                        </div>
                        <div class="noise-stat">
                            <span class="stat-label">T1 (μs)</span>
                            <span class="stat-value" id="noise-t1">-</span>
                        </div>
                        <div class="noise-stat">
                            <span class="stat-label">T2 (μs)</span>
                            <span class="stat-value" id="noise-t2">-</span>
                        </div>
                    </div>
                </div>

                <div id="custom-noise-config" class="custom-noise-panel" style="display: none;">
                    <h5>Custom Noise Parameters</h5>
                    <div class="form-grid">
                        <div class="form-group">
                            <label for="custom-1q-error">Single Qubit Error Rate</label>
                            <input type="number" id="custom-1q-error" step="0.0001" min="0" max="1" value="0.001">
                        </div>
                        <div class="form-group">
                            <label for="custom-2q-error">Two Qubit Error Rate</label>
                            <input type="number" id="custom-2q-error" step="0.001" min="0" max="1" value="0.01">
                        </div>
                        <div class="form-group">
                            <label for="custom-readout-error">Readout Error Rate</label>
                            <input type="number" id="custom-readout-error" step="0.001" min="0" max="1" value="0.02">
                        </div>
                        <div class="form-group">
                            <label for="custom-t1">T1 (μs)</label>
                            <input type="number" id="custom-t1" step="10" min="0" value="150">
                        </div>
                        <div class="form-group">
                            <label for="custom-t2">T2 (μs)</label>
                            <input type="number" id="custom-t2" step="10" min="0" value="100">
                        </div>
                    </div>
                </div>
            </div>

            <div class="simulator-section">
                <div class="section-header">
                    <h4><i class="fas fa-shield-alt"></i> Error Mitigation</h4>
                    <span class="overhead-badge" id="mitigation-overhead">Overhead: 1x</span>
                </div>

                <div class="form-group">
                    <label for="error-mitigation-select">Select Method</label>
                    <select id="error-mitigation-select" class="form-select">
                        ${Object.entries(ERROR_MITIGATION_METHODS).map(([key, method]) => 
                            `<option value="${key}">${method.name}</option>`
                        ).join('')}
                    </select>
                </div>

                <div id="mitigation-description" class="mitigation-description">
                    <p>No error mitigation will be applied to the results.</p>
                </div>

                <div id="zne-options" class="mitigation-options" style="display: none;">
                    <h5>Zero Noise Extrapolation Options</h5>
                    <div class="form-group">
                        <label for="zne-method">Extrapolation Method</label>
                        <select id="zne-method" class="form-select">
                            <option value="linear">Linear</option>
                            <option value="richardson">Richardson</option>
                            <option value="exponential">Exponential</option>
                        </select>
                    </div>
                    <div class="zne-info">
                        <span class="info-icon"><i class="fas fa-info-circle"></i></span>
                        <span>ZNE runs the circuit at multiple noise levels and extrapolates to zero noise.</span>
                    </div>
                </div>

                <div id="dd-options" class="mitigation-options" style="display: none;">
                    <h5>Dynamical Decoupling Options</h5>
                    <div class="form-group">
                        <label for="dd-sequence">Pulse Sequence</label>
                        <select id="dd-sequence" class="form-select">
                            <option value="XY4">XY4 (4 pulses)</option>
                            <option value="XY8">XY8 (8 pulses)</option>
                            <option value="CPMG">CPMG</option>
                        </select>
                    </div>
                </div>
            </div>

            <div class="simulator-section">
                <div class="section-header">
                    <h4><i class="fas fa-cogs"></i> Additional Options</h4>
                </div>
                
                <div class="checkbox-group">
                    <label class="checkbox">
                        <input type="checkbox" id="opt-sim-transpilation">
                        <span class="checkmark"></span>
                        <div class="checkbox-label">
                            <strong>Transpilation Optimization</strong>
                            <small>Optimize circuit depth and gate count</small>
                        </div>
                    </label>
                    <label class="checkbox">
                        <input type="checkbox" id="opt-sim-seed" checked>
                        <span class="checkmark"></span>
                        <div class="checkbox-label">
                            <strong>Fixed Seed</strong>
                            <small>Use deterministic random seed for reproducibility</small>
                        </div>
                    </label>
                    <label class="checkbox">
                        <input type="checkbox" id="opt-sim-fusion">
                        <span class="checkmark"></span>
                        <div class="checkbox-label">
                            <strong>Gate Fusion</strong>
                            <small>Combine gates for faster simulation</small>
                        </div>
                    </label>
                </div>

                <div class="form-group" id="seed-input-group">
                    <label for="simulator-seed">Random Seed</label>
                    <input type="number" id="simulator-seed" value="42" min="0">
                </div>
            </div>

            <div class="simulator-actions">
                <button class="btn btn-primary" onclick="window.applySimulatorConfig()">
                    <i class="fas fa-check"></i> Apply Configuration
                </button>
                <button class="btn btn-ghost" onclick="window.resetSimulatorConfig()">
                    <i class="fas fa-undo"></i> Reset to Defaults
                </button>
            </div>
        </div>
    `;
}

/**
 * Bind event handlers for simulator options
 */
function bindSimulatorOptionEvents() {
    const noiseSelect = document.getElementById('noise-model-select');
    if (noiseSelect) {
        noiseSelect.addEventListener('change', handleNoiseModelChange);
    }

    const mitigationSelect = document.getElementById('error-mitigation-select');
    if (mitigationSelect) {
        mitigationSelect.addEventListener('change', handleMitigationChange);
    }

    const seedCheckbox = document.getElementById('opt-sim-seed');
    if (seedCheckbox) {
        seedCheckbox.addEventListener('change', (e) => {
            const seedGroup = document.getElementById('seed-input-group');
            if (seedGroup) {
                seedGroup.style.display = e.target.checked ? 'block' : 'none';
            }
        });
    }
}

/**
 * Handle noise model selection change
 */
function handleNoiseModelChange(e) {
    const value = e.target.value;
    simulatorState.noiseModel = value;

    const detailsEl = document.getElementById('noise-model-details');
    const customEl = document.getElementById('custom-noise-config');

    if (value === 'none') {
        detailsEl.style.display = 'none';
        customEl.style.display = 'none';
    } else if (value === 'custom') {
        detailsEl.style.display = 'none';
        customEl.style.display = 'block';
    } else {
        const model = NOISE_MODELS[value];
        if (model) {
            detailsEl.style.display = 'block';
            customEl.style.display = 'none';

            document.getElementById('noise-qubits').textContent = model.qubits;
            document.getElementById('noise-1q').textContent = (model.single_qubit_error * 100).toFixed(2) + '%';
            document.getElementById('noise-2q').textContent = (model.two_qubit_error * 100).toFixed(1) + '%';
            document.getElementById('noise-readout').textContent = (model.readout_error * 100).toFixed(1) + '%';
            document.getElementById('noise-t1').textContent = model.t1;
            document.getElementById('noise-t2').textContent = model.t2;
        }
    }
}

/**
 * Handle error mitigation method change
 */
function handleMitigationChange(e) {
    const value = e.target.value;
    simulatorState.errorMitigation = value;

    const method = ERROR_MITIGATION_METHODS[value];
    const descEl = document.getElementById('mitigation-description');
    const overheadEl = document.getElementById('mitigation-overhead');
    const zneEl = document.getElementById('zne-options');
    const ddEl = document.getElementById('dd-options');

    if (descEl) {
        descEl.innerHTML = `<p>${method.description}</p>
            <div class="suitable-for">
                <span class="label">Suitable for:</span>
                ${method.suitable_for.map(t => `<span class="tag">${t}</span>`).join('')}
            </div>`;
    }

    if (overheadEl) {
        overheadEl.textContent = `Overhead: ${method.overhead}x`;
        overheadEl.className = method.overhead > 1 ? 'overhead-badge warning' : 'overhead-badge';
    }

    if (zneEl) zneEl.style.display = value === 'zero_noise_extrapolation' ? 'block' : 'none';
    if (ddEl) ddEl.style.display = value === 'dynamical_decoupling' ? 'block' : 'none';
}

/**
 * Get current simulator configuration
 */
export function getSimulatorConfig() {
    return {
        noise_model: simulatorState.noiseModel === 'none' ? null : {
            type: simulatorState.noiseModel,
            ...(simulatorState.noiseModel === 'custom' ? {
                single_qubit_error: parseFloat(document.getElementById('custom-1q-error')?.value || 0.001),
                two_qubit_error: parseFloat(document.getElementById('custom-2q-error')?.value || 0.01),
                readout_error: parseFloat(document.getElementById('custom-readout-error')?.value || 0.02),
                t1: parseInt(document.getElementById('custom-t1')?.value || 150),
                t2: parseInt(document.getElementById('custom-t2')?.value || 100)
            } : (NOISE_MODELS[simulatorState.noiseModel] || {}))
        },
        error_mitigation: simulatorState.errorMitigation === 'none' ? null : {
            method: simulatorState.errorMitigation,
            zne_method: simulatorState.zneMethod,
            dd_sequence: simulatorState.ddSequence
        },
        options: {
            transpilation_optimization: document.getElementById('opt-sim-transpilation')?.checked || false,
            fixed_seed: document.getElementById('opt-sim-seed')?.checked || false,
            seed: parseInt(document.getElementById('simulator-seed')?.value || 42),
            gate_fusion: document.getElementById('opt-sim-fusion')?.checked || false
        }
    };
}

/**
 * Apply simulator configuration
 */
function applySimulatorConfig() {
    const config = getSimulatorConfig();
    localStorage.setItem('simulatorConfig', JSON.stringify(config));
    showToast('success', 'Configuration Applied', 'Advanced simulator options saved');
}

/**
 * Reset simulator configuration to defaults
 */
function resetSimulatorConfig() {
    localStorage.removeItem('simulatorConfig');
    simulatorState = {
        noiseModel: 'none',
        errorMitigation: 'none',
        customNoiseConfig: {},
        zneMethod: 'linear',
        ddSequence: 'XY4'
    };

    document.getElementById('noise-model-select').value = 'none';
    document.getElementById('error-mitigation-select').value = 'none';
    document.getElementById('noise-model-details').style.display = 'none';
    document.getElementById('custom-noise-config').style.display = 'none';

    showToast('info', 'Configuration Reset', 'Simulator options restored to defaults');
}

/**
 * Load saved simulator configuration
 */
function loadSavedSimulatorConfig() {
    const saved = localStorage.getItem('simulatorConfig');
    if (saved) {
        try {
            const config = JSON.parse(saved);
            if (config.noise_model) {
                simulatorState.noiseModel = config.noise_model.type || 'none';
                document.getElementById('noise-model-select').value = simulatorState.noiseModel;
                handleNoiseModelChange({ target: { value: simulatorState.noiseModel } });
            }
            if (config.error_mitigation) {
                simulatorState.errorMitigation = config.error_mitigation.method || 'none';
                document.getElementById('error-mitigation-select').value = simulatorState.errorMitigation;
                handleMitigationChange({ target: { value: simulatorState.errorMitigation } });
            }
        } catch (e) {
            console.warn('Failed to load saved simulator config:', e);
        }
    }
}

/**
 * Render error mitigation results in job details
 */
export function renderErrorMitigationResults(result) {
    if (!result || !result.error_mitigation) return null;

    const em = result.error_mitigation;
    return `
        <div class="error-mitigation-results">
            <div class="em-header">
                <h4><i class="fas fa-shield-alt"></i> Error Mitigation Results</h4>
                <span class="em-method-badge">${ERROR_MITIGATION_METHODS[em.method]?.name || em.method}</span>
            </div>
            
            <div class="em-metrics">
                ${em.zne_data ? `
                    <div class="em-section">
                        <h5>Zero Noise Extrapolation</h5>
                        <div class="zne-chart" id="zne-chart-container">
                            <canvas id="zne-chart"></canvas>
                        </div>
                        <div class="zne-values">
                            <div class="zne-value">
                                <span class="label">Extrapolated Value</span>
                                <span class="value">${em.zne_data.extrapolated_value?.toFixed(6) || '-'}</span>
                            </div>
                            <div class="zne-value">
                                <span class="label">Raw Value</span>
                                <span class="value">${em.zne_data.raw_value?.toFixed(6) || '-'}</span>
                            </div>
                            <div class="zne-value">
                                <span class="label">Improvement</span>
                                <span class="value improvement">${em.zne_data.improvement ? 
                                    `${(em.zne_data.improvement * 100).toFixed(2)}%` : '-'}</span>
                            </div>
                        </div>
                    </div>
                ` : ''}
                
                ${em.readout_correction ? `
                    <div class="em-section">
                        <h5>Readout Error Correction</h5>
                        <div class="correction-matrix">
                            <span class="label">Calibration Matrix Applied</span>
                            <span class="badge">Conditioned</span>
                        </div>
                        <div class="correction-stats">
                            <span>Correlated errors corrected: ${em.readout_correction.correlated_errors || 'N/A'}</span>
                        </div>
                    </div>
                ` : ''}
            </div>
        </div>
    `;
}

// Global functions for UI
window.toggleNoiseHelp = () => {
    showToast('info', 'Noise Models', 'Select a backend noise profile or create a custom one for realistic simulation');
};

window.applySimulatorConfig = applySimulatorConfig;
window.resetSimulatorConfig = resetSimulatorConfig;
