/**
 * Charts Module
 * Handles Chart.js visualizations for convergence, energy, probabilities, and status
 */

import { STATE } from './config.js';

// Chart instances
let convergenceChart = null;
let energyDistChart = null;
let probabilityChart = null;
let parameterChart = null;
let statusPieChart = null;

// Chart.js module-level singleton loading promise
const CHART_JS_VERSION = '4.4.0';
const CHART_JS_CDN = `https://cdn.jsdelivr.net/npm/chart.js@${CHART_JS_VERSION}/dist/chart.umd.min.js`;

let chartLoadPromise = null;
let chartJsLoaded = false;
let chartJsLoading = false;

/**
 * Lazy load Chart.js library with module-level singleton pattern.
 * This ensures Chart.js is only loaded once per session, even when navigating between pages.
 *
 * The singleton pattern prevents:
 * 1. Redundant network requests for the same CDN resource
 * 2. Memory leaks from multiple Chart.js instances
 * 3. Version conflicts from loading different versions
 */
export async function loadChartJS() {
    if (typeof window !== 'undefined' && window.Chart) {
        chartJsLoaded = true;
        return;
    }

    if (chartJsLoaded) {
        return;
    }

    if (chartLoadPromise) {
        return chartLoadPromise;
    }

    if (chartJsLoading) {
        return new Promise(resolve => {
            const checkInterval = setInterval(() => {
                if (chartJsLoaded) {
                    clearInterval(checkInterval);
                    resolve();
                }
            }, 50);
        });
    }

    chartJsLoading = true;

    chartLoadPromise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = CHART_JS_CDN;
        script.crossOrigin = 'anonymous';
        script.async = true;

        script.onload = () => {
            chartJsLoaded = true;
            chartJsLoading = false;
            console.log('Chart.js loaded successfully');
            resolve();
        };

        script.onerror = () => {
            chartJsLoading = false;
            chartLoadPromise = null;
            const error = new Error(`Failed to load Chart.js from ${CHART_JS_CDN}`);
            console.error(error);
            reject(error);
        };

        document.head.appendChild(script);
    });

    return chartLoadPromise;
}

// Make loadChartJS globally accessible for dashboard.js
if (typeof window !== 'undefined') {
    window.loadChartJS = loadChartJS;
    window.chartJsLoaded = () => chartJsLoaded;
}

export function isChartJsLoaded() {
    return typeof window !== 'undefined' && chartJsLoaded && !!window.Chart;
}

/**
 * Initialize Convergence Chart
 */
export async function initConvergenceChart(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    // Lazy load Chart.js
    try {
        await loadChartJS();
    } catch (error) {
        console.warn('Chart.js not available');
        return;
    }

    if (!window.Chart) return;

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
                borderColor: 'rgba(99, 102, 241, 1)',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.3,
                pointRadius: data.length > 50 ? 0 : 2,
                pointHoverRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#1a1a25',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8',
                    borderColor: '#2a2a3a',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Iteration', color: '#64748b' },
                    grid: { color: 'rgba(42, 42, 58, 0.5)' },
                    ticks: { color: '#64748b' }
                },
                y: {
                    title: { display: true, text: 'Energy', color: '#64748b' },
                    grid: { color: 'rgba(42, 42, 58, 0.5)' },
                    ticks: { color: '#64748b' }
                }
            }
        }
    });
}

/**
 * Initialize Energy Distribution Histogram
 */
export async function initEnergyDistributionChart(data) {
    const canvas = document.getElementById('energy-distribution-chart');
    if (!canvas || !data || data.length === 0) return;

    try {
        await loadChartJS();
    } catch (error) {
        return;
    }

    if (!window.Chart) return;

    if (energyDistChart) {
        energyDistChart.destroy();
    }

    // Create histogram bins
    const min = Math.min(...data);
    const max = Math.max(...data);
    const binCount = Math.min(20, Math.ceil(Math.sqrt(data.length)));
    const binWidth = (max - min) / binCount || 1;

    const bins = Array(binCount).fill(0);
    data.forEach(value => {
        const binIndex = Math.min(Math.floor((value - min) / binWidth), binCount - 1);
        bins[binIndex]++;
    });

    const labels = Array(binCount).fill().map((_, i) =>
        (min + (i + 0.5) * binWidth).toFixed(2)
    );

    const ctx = canvas.getContext('2d');
    energyDistChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Frequency',
                data: bins,
                backgroundColor: 'rgba(16, 185, 129, 0.6)',
                borderColor: 'rgba(16, 185, 129, 1)',
                borderWidth: 1
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
                    grid: { display: false },
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
export async function initProbabilityChart(probabilities) {
    const canvas = document.getElementById('probability-chart');
    if (!canvas || !probabilities) return;

    try {
        await loadChartJS();
    } catch (error) {
        return;
    }

    if (!window.Chart) return;

    if (probabilityChart) {
        probabilityChart.destroy();
    }

    // Convert object to sorted array if needed
    let sortedData;
    if (Array.isArray(probabilities)) {
        sortedData = probabilities.map((p, i) => ({ state: i.toString(), prob: p }))
            .filter(d => d.prob > 0.001);
    } else {
        sortedData = Object.entries(probabilities)
            .map(([state, prob]) => ({ state, prob }))
            .filter(d => d.prob > 0.001);
    }

    // Sort by probability descending and take top 20
    sortedData.sort((a, b) => b.prob - a.prob);
    sortedData = sortedData.slice(0, 20);

    const ctx = canvas.getContext('2d');
    probabilityChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sortedData.map(d => d.state),
            datasets: [{
                label: 'Probability',
                data: sortedData.map(d => d.prob),
                backgroundColor: sortedData.map((_, i) =>
                    i === 0 ? 'rgba(99, 102, 241, 0.8)' : 'rgba(99, 102, 241, 0.4)'
                ),
                borderColor: 'rgba(99, 102, 241, 1)',
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1a1a25',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8',
                    callbacks: {
                        label: ctx => `Probability: ${(ctx.raw * 100).toFixed(2)}%`
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
export async function initParameterChart(params) {
    const canvas = document.getElementById('parameter-chart');
    if (!canvas || !params) return;

    try {
        await loadChartJS();
    } catch (error) {
        return;
    }

    if (!window.Chart) return;

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
 * Update Status Pie Chart
 */
export async function updateStatusPieChart(data) {
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

    // Lazy load Chart.js
    try {
        await loadChartJS();
    } catch (error) {
        console.error('Failed to load Chart.js for pie chart');
        return;
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
 * Destroy all chart instances
 */
export function destroyAllCharts() {
    if (convergenceChart) {
        convergenceChart.destroy();
        convergenceChart = null;
    }
    if (energyDistChart) {
        energyDistChart.destroy();
        energyDistChart = null;
    }
    if (probabilityChart) {
        probabilityChart.destroy();
        probabilityChart = null;
    }
    if (parameterChart) {
        parameterChart.destroy();
        parameterChart = null;
    }
    if (statusPieChart) {
        statusPieChart.destroy();
        statusPieChart = null;
    }
}
