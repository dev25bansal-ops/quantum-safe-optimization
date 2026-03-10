/**
 * Research Module
 * Provides publication-ready analytics, benchmarks, and ablation studies
 */

import { apiRequest } from './api.js';

// Plotly.js version
const PLOTLY_VERSION = '2.27.0';
const PLOTLY_CDN = `https://cdn.plot.ly/plotly-${PLOTLY_VERSION}.min.js`;

let plotlyLoadPromise = null;
let plotlyLoaded = false;

/**
 * Lazy load Plotly.js library
 */
export async function loadPlotlyJS() {
    if (typeof window !== 'undefined' && window.Plotly) {
        plotlyLoaded = true;
        return;
    }

    if (plotlyLoaded) {
        return;
    }

    if (plotlyLoadPromise) {
        return plotlyLoadPromise;
    }

    plotlyLoadPromise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = PLOTLY_CDN;
        script.crossOrigin = 'anonymous';
        script.async = true;

        script.onload = () => {
            plotlyLoaded = true;
            console.log('Plotly.js loaded successfully');
            resolve();
        };

        script.onerror = () => {
            plotlyLoadPromise = null;
            const error = new Error(`Failed to load Plotly.js from ${PLOTLY_CDN}`);
            console.error(error);
            reject(error);
        };

        document.head.appendChild(script);
    });

    return plotlyLoadPromise;
}

/**
 * Get circuit visualization SVG
 */
export async function getCircuitVisualization(projectId, algorithm = 'qaoa', pLayers = 2) {
    const response = await apiRequest(`GET`, `/analytics/projects/${projectId}/circuit?algorithm=${algorithm}&p_layers=${pLayers}`);
    return response;
}

/**
 * Display circuit visualization
 */
export async function displayCircuitVisualization(containerId, projectId, algorithm = 'qaoa', pLayers = 2) {
    const container = document.getElementById(containerId);
    if (!container) return;

    try {
        const data = await getCircuitVisualization(projectId, algorithm, pLayers);

        container.innerHTML = `
            <div class="circuit-visualization">
                <div class="circuit-stats">
                    <div class="stat-item">
                        <span class="stat-label">Circuit Depth:</span>
                        <span class="stat-value">${data.depth}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Qubits:</span>
                        <span class="stat-value">${data.qubit_count}</span>
                    </div>
                </div>
                <div class="gate-counts">
                    <h4>Gate Counts:</h4>
                    ${Object.entries(data.gate_counts).map(([gate, count]) => 
                        `<span class="gate-badge">${gate}: ${count}</span>`
                    ).join(' ')}
                </div>
                <div class="circuit-diagram">
                    ${data.circuit_svg}
                </div>
                <div class="connectivity">
                    <h4>Qubit Connectivity:</h4>
                    <p>${data.connectivity.map(([q1, q2]) => `Q${q1} ↔ Q${q2}`).join(', ')}</p>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Failed to load circuit visualization:', error);
        container.innerHTML = '<div class="error">Failed to load circuit visualization</div>';
    }
}

/**
 * Export job data
 */
export async function exportJobData(jobId, format = 'json') {
    try {
        const response = await apiRequest('GET', `/analytics/jobs/${jobId}/export?format=${format}`, undefined, undefined);
        
        const blob = new Blob([format === 'json' ? JSON.stringify(response, null, 2) : response], {
            type: format === 'json' ? 'application/json' : 'text/csv'
        });
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `job_${jobId}_export.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Failed to export job data:', error);
        throw error;
    }
}

/**
 * Run benchmark comparison
 */
export async function runBenchmarkComparison(
    algorithms,
    problemId,
    problemConfig: any = null,
    pLayersRange: [number, number] = [1, 3]
) {
    const response = await apiRequest('POST', '/analytics/benchmark/compare', {
        algorithms,
        problem_id: problemId,
        problem_config: problemConfig,
        metrics: ['optimal_value', 'iterations', 'convergence_rate'],
        p_layers_range: pLayersRange
    });
    return response;
}

/**
 * Run ablation study
 */
export async function runAblationStudy(
    algorithm,
    pLayersRange: [number, number] = [1, 10],
    optimizers, 'SPSA', 'ADAM'],
    shotsList,
    repetitions,
    randomSeed,
) {
    const response = await apiRequest('POST', '/analytics/benchmark/run-ablation', {
        algorithm,
        p_layers_range: pLayersRange,
        optimizers,
        shots_list: shotsList,
        repetitions,
        random_seed: randomSeed
    });
    return response;
}

/**
 * Get research metrics
 */
export async function getResearchMetrics(days, algorithm,) {
    const params = new URLSearchParams({ days: days.toString() });
    if (algorithm) params.append('algorithm', algorithm);
    
    const response = await apiRequest('GET', `/analytics/research/metrics?${params.toString()}`);
    return response;
}

/**
 * Get publication metadata
 */
export async function getPublicationMetadata() {
    const response = await apiRequest('GET', '/analytics/research/publication-metadata');
    return response;
}

/**
 * Create convergence comparison chart using Plotly
 */
export async function createConvergenceChart(
    containerId,
    data: { algorithm,
) {
    await loadPlotlyJS();

    const container = document.getElementById(containerId);
    if (!container) return;

    const algorithms = [...new Set(data.map(d => d.algorithm))];

    const traces = algorithms.map(algo => {
        const algoData = data.filter(d => d.algorithm === algo);
        return {
            x: algoData.map(d => d.iterations),
            y: algoData.map(d => d.optimal_value),
            name: algo.toUpperCase(),
            mode: 'lines+markers',
            line: { width: 2 },
            marker: { size: 6 }
        };
    });

    const layout = {
        title: {
            text: 'Convergence Comparison',
            font: { size: 18, color: '#161b22' }
        },
        xaxis: {
            title: ' iterations',
            titlefont: { size: 14, color: '#64748b' },
            tickfont: { size: 12, color: '#64748b' },
            gridcolor: 'rgba(48, 54, 61, 0.5)',
            zerolinecolor: 'rgba(48, 54, 61, 0.8)'
        },
        yaxis: {
            title: 'Optimal Value',
            titlefont: { size: 14, color: '#64748b' },
            tickfont: { size: 12, color: '#64748b' },
            gridcolor: 'rgba(48, 54, 61, 0.5)',
            zerolinecolor: 'rgba(48, 54, 61, 0.8)'
        },
        legend: {
            font: { size: 12, color: '#64748b' },
            bgcolor: 'rgba(248, 250, 252, 0.8)',
            bordercolor: '#30363d',
            borderwidth: 1
        },
        plot_bgcolor: 'rgba(248, 250, 252, 0.5)',
        paper_bgcolor: 'rgba(255, 255, 255, 0)'
    };

    const config = {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['select2d', 'lasso2d', 'hoverClosestCartesian']
    };

    (window as any).Plotly.newPlot(containerId, traces, layout, config);
}

/**
 * Create algorithm performance comparison chart
 */
export async function createPerformanceChart(
    containerId,
    data: { algorithm,
) {
    await loadPlotlyJS();

    const container = document.getElementById(containerId);
    if (!container) return;

    const algorithms = [...new Set(data.map(d => d.algorithm))];
    const pLayers = [...new Set(data.map(d => d.p_layers))];

    const traces = algorithms.map((algo, idx) => {
        const algoData = data.filter(d => d.algorithm === algo);
        const colors = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];
        
        return {
            x: algoData.map(d => d.p_layers),
            y: algoData.map(d => -d.optimal_value),  // Negate for maximization
            name: algo.toUpperCase(),
            type: 'bar',
            marker: {
                color: colors[idx % colors.length],
                opacity: 0.8,
                line: { color: 'rgba(0,0,0,0.3)', width: 1 }
            },
            text: algoData.map(d => `${(-d.optimal_value).toFixed(2)}`),
            textposition: 'auto'
        };
    });

    const layout = {
        title: {
            text: 'Solution Quality vs Problem Size',
            font: { size: 18, color: '#161b22' }
        },
        xaxis: {
            title: 'p layers',
            titlefont: { size: 14, color: '#64748b' },
            tickfont: { size: 12, color: '#64748b' },
            gridcolor: 'rgba(48, 54, 61, 0.5)',
            type: 'category'
        },
        yaxis: {
            title: 'Objective Value (maximized)',
            titlefont: { size: 14, color: '#64748b' },
            tickfont: { size: 12, color: '#64748b' },
            gridcolor: 'rgba(48, 54, 61, 0.5)'
        },
        barmode: 'group',
        legend: {
            font: { size: 12, color: '#64748b' },
            bgcolor: 'rgba(248, 250, 252, 0.8)',
            bordercolor: '#30363d',
            borderwidth: 1
        },
        plot_bgcolor: 'rgba(248, 250, 252, 0.5)',
        paper_bgcolor: 'rgba(255, 255, 255, 0)'
    };

    const config = {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['select2d', 'lasso2d']
    };

    (window as any).Plotly.newPlot(containerId, traces, layout, config);
}

/**
 * Create ablation study heat map
 */
export async function createAblationHeatmap(
    containerId,
    data: { p_layers,
) {
    await loadPlotlyJS();

    const container = document.getElementById(containerId);
    if (!container) return;

    const pLayers = [...new Set(data.map(d => d.p_layers))].sort((a, b) => a - b);
    const optimizers = [...new Set(data.map(d => d.optimizer))];

    const zValues = optimizers.map(optimizer => {
        return pLayers.map(p => {
            const entry = data.find(d => d.p_layers === p && d.optimizer === optimizer);
            return entry ? -entry.optimal_value : 0;
        });
    });

    const hoverTexts = optimizers.map(optimizer => {
        return pLayers.map(p => {
            const entry = data.find(d => d.p_layers === p && d.optimizer === optimizer);
            return entry ? 
                `p=${p}<br>Optimizer: ${optimizer}<br>Value: ${(-entry.optimal_value).toFixed(2)}<br>Time: ${entry.execution_time_ms.toFixed(0)}ms` : 
                '';
        });
    });

    const trace = {
        z: zValues,
        x: pLayers,
        y: optimizers,
        type: 'heatmap',
        colorscale: 'Viridis',
        hovertext: hoverTexts,
        hoverinfo: 'text',
        colorbar: {
            title: 'Objective Value',
            titlefont: { size: 14, color: '#64748b' },
            tickfont: { size: 12, color: '#64748b' }
        }
    };

    const layout = {
        title: {
            text: 'Ablation Study: p-layers vs Optimizer',
            font: { size: 18, color: '#161b22' }
        },
        xaxis: {
            title: 'p layers',
            titlefont: { size: 14, color: '#64748b' },
            tickfont: { size: 12, color: '#64748b' }
        },
        yaxis: {
            title: 'Optimizer',
            titlefont: { size: 14, color: '#64748b' },
            tickfont: { size: 12, color: '#64748b' }
        },
        plot_bgcolor: 'rgba(248, 250, 252, 0.5)',
        paper_bgcolor: 'rgba(255, 255, 255, 0)'
    };

    const config = {
        responsive: true,
        displayModeBar: true
    };

    (window as any).Plotly.newPlot(containerId, [trace], layout, config);
}

/**
 * Create side-by-side benchmark comparison chart
 */
export async function createSideBySideComparison(
    containerId,
    data: { algorithm,
) {
    await loadPlotlyJS();

    const container = document.getElementById(containerId);
    if (!container) return;

    const algorithms = [...new Set(data.map(d => d.algorithm))];

    const trace1 = {
        x: algorithms,
        y: data.map(d => -d.optimal_value),
        name: 'Optimal Value',
        type: 'bar',
        marker: { color: '#6366f1', opacity: 0.8 },
        xaxis: 'x',
        yaxis: 'y'
    };

    const trace2 = {
        x: algorithms,
        y: data.map(d => d.iterations),
        name: 'Iterations',
        type: 'bar',
        marker: { color: '#10b981', opacity: 0.8 },
        xaxis: 'x2',
        yaxis: 'y2'
    };

    const trace3 = {
        x: algorithms,
        y: data.map(d => d.execution_time_ms),
        name: 'Execution Time (ms)',
        type: 'bar',
        marker: { color: '#f59e0b', opacity: 0.8 },
        xaxis: 'x3',
        yaxis: 'y3'
    };

    const layout = {
        title: {
            text: 'Algorithm Comparison',
            font: { size: 18, color: '#161b22' },
            x: 0.5
        },
        grid: {
            rows: 1,
            columns: 3,
            pattern: 'independent'
        },
        xaxis: {
            domain: [0, 0.33],
            title: 'Algorithm',
            tickangle: -45
        },
        xaxis2: {
            domain: [0.33, 0.66],
            title: 'Algorithm',
            tickangle: -45
        },
        xaxis3: {
            domain: [0.66, 1],
            title: 'Algorithm',
            tickangle: -45
        },
        yaxis: {
            domain: [0, 1],
            title: 'Objective Value'
        },
        yaxis2: {
            domain: [0, 1],
            title: 'Iterations'
        },
        yaxis3: {
            domain: [0, 1],
            title: 'Time (ms)'
        },
        plot_bgcolor: 'rgba(248, 250, 252, 0.5)',
        paper_bgcolor: 'rgba(255, 255, 255, 0)',
        showlegend: true,
        legend: {
            orientation: 'h',
            y: -0.15
        }
    };

    const config = {
        responsive: true,
        displayModeBar: true
    };

    (window as any).Plotly.newPlot(containerId, [trace1, trace2, trace3], layout, config);
}

/**
 * Initialize research dashboard
 */
export async function initializeResearchDashboard(tenantId,) {
    try {
        const metrics = await getResearchMetrics();
        const metadata = await getPublicationMetadata();

        // Update metrics display
        const metricsContainer = document.getElementById('research-metrics');
        if (metricsContainer) {
            metricsContainer.innerHTML = `
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-value">${metrics.total_jobs_run}</div>
                        <div class="metric-label">Total Jobs</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">${(metrics.average_convergence_rate * 100).toFixed(1)}%</div>
                        <div class="metric-label">Avg Convergence</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">${metrics.reproducibility.correlation_coefficient.toFixed(3)}</div>
                        <div class="metric-label">Reproducibility</div>
                    </div>
                </div>
            `;
        }

        // Display bibliography
        const biblioContainer = document.getElementById('bibliography');
        if (biblioContainer) {
            biblioContainer.innerHTML = `
                <h3>Bibliography</h3>
                ${metadata.bibliography.map((ref,) => 
                    `<p class="bib-entry"><code>${ref}</code></p>`
                ).join('')}
            `;
        }

    } catch (error) {
        console.error('Failed to initialize research dashboard:', error);
    }
}

/**
 * Create animated convergence plot
 */
export async function createAnimatedConvergence(
    containerId,
    convergenceData: { algorithm,
) {
    await loadPlotlyJS();

    const container = document.getElementById(containerId);
    if (!container) return;

    const maxHistory = Math.max(...convergenceData.map(d => d.history.length));

    const traces = convergenceData.map((data, idx) => {
        const colors = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];
        return {
            x: Array.from({ length: maxHistory }, (_, i) => i + 1),
            y: [...data.history, ...Array(maxHistory - data.history.length).fill(null)],
            name: data.algorithm.toUpperCase(),
            mode: 'lines+markers',
            line: { width: 2, color: colors[idx % colors.length] },
            marker: { size: 6 },
            opacity: 0
        };
    });

    const layout = {
        title: 'Real-time Convergence',
        xaxis: { title: 'Iteration', range: [0, maxHistory] },
        yaxis: { title: 'Objective Value' },
        hovermode: 'closest',
        plot_bgcolor: 'rgba(248, 250, 252, 0.5)',
        paper_bgcolor: 'rgba(255, 255, 255, 0)',
        updatemenus: [{
            buttons: [
                { label: 'Play', method: 'animate', args: [null, { frame: { duration: 100, redraw: true }, fromcurrent: true }] },
                { label: 'Pause', method: 'animate', args: [[null], { mode: 'immediate', frame: { duration: 0, redraw: false } }] }
            ]
        }]
    };

    const frames = Array.from({ length: maxHistory }, (_, i) => ({
        name: i,
        data: traces.map(trace => ({
            x: trace.x.slice(0, i + 1),
            y: trace.y.slice(0, i + 1),
            opacity: 1
        }))
    }));

    const config = {
        responsive: true,
        displayModeBar: true
    };

    (window as any).Plotly.newPlot(containerId, traces, layout, config);
    (window as any).Plotly.addFrames(containerId, frames);
}

// Export for global use
if (typeof window !== 'undefined') {
    (window as any).ResearchModule = {
        loadPlotlyJS,
        displayCircuitVisualization,
        exportJobData,
        runBenchmarkComparison,
        runAblationStudy,
        createConvergenceChart,
        createPerformanceChart,
        createAblationHeatmap,
        createSideBySideComparison,
        createAnimatedConvergence,
        initializeResearchDashboard
    };
}
