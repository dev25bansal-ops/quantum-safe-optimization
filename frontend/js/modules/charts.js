/**
 * Charts Module
 * Enhanced Chart.js visualizations for convergence, energy, probabilities, and status
 * Features: zoom, pan, better tooltips, histogram, statevector viz
 */

import { STATE } from './config.js';

let convergenceChart = null;
let energyDistChart = null;
let probabilityChart = null;
let parameterChart = null;
let statusPieChart = null;
let histogramChart = null;
let statevectorChart = null;

const CHART_JS_VERSION = '4.4.0';
const CHART_JS_CDN = `https://cdn.jsdelivr.net/npm/chart.js@${CHART_JS_VERSION}/dist/chart.umd.min.js`;
const ZOOM_PLUGIN_CDN = 'https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js';

let chartLoadPromise = null;
let chartJsLoaded = false;
let chartJsLoading = false;

/**
 * Lazy load Chart.js with zoom plugin
 */
export async function loadChartJS() {
    if (typeof window !== 'undefined' && window.Chart) {
        chartJsLoaded = true;
        return;
    }

    if (chartJsLoaded) return;

    if (chartLoadPromise) return chartLoadPromise;

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
            const zoomScript = document.createElement('script');
            zoomScript.src = ZOOM_PLUGIN_CDN;
            zoomScript.crossOrigin = 'anonymous';
            zoomScript.async = true;

            zoomScript.onload = () => {
                chartJsLoaded = true;
                chartJsLoading = false;
                console.log('Chart.js with zoom plugin loaded');
                resolve();
            };

            zoomScript.onerror = () => {
                chartJsLoaded = true;
                chartJsLoading = false;
                console.warn('Zoom plugin failed, continuing without it');
                resolve();
            };

            document.head.appendChild(zoomScript);
        };

        script.onerror = () => {
            chartJsLoading = false;
            chartLoadPromise = null;
            reject(new Error(`Failed to load Chart.js`));
        };

        document.head.appendChild(script);
    });

    return chartLoadPromise;
}

if (typeof window !== 'undefined') {
    window.loadChartJS = loadChartJS;
    window.chartJsLoaded = () => chartJsLoaded;
}

export function isChartJsLoaded() {
    return typeof window !== 'undefined' && chartJsLoaded && !!window.Chart;
}

/**
 * Initialize Enhanced Convergence Chart
 */
export async function initConvergenceChart(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    try {
        await loadChartJS();
    } catch (error) {
        console.warn('Chart.js not available');
        return;
    }

    if (!window.Chart) return;

    if (convergenceChart) {
        convergenceChart.destroy();
    }

    const ctx = canvas.getContext('2d');

    const theme = document.documentElement.getAttribute('data-theme') || 'dark';
    const colors = {
        grid: theme === 'dark' ? 'rgba(42, 42, 58, 0.5)' : 'rgba(203, 213, 225, 0.5)',
        text: theme === 'dark' ? '#64748b' : '#64748b',
        primary: '#6366f1',
        primaryBg: 'rgba(99, 102, 241, 0.1)',
        success: '#10b981',
        tooltip: theme === 'dark' ? '#1a1a25' : '#ffffff',
        tooltipText: theme === 'dark' ? '#f8fafc' : '#1e293b'
    };

    const gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, colors.primaryBg);
    gradient.addColorStop(1, 'rgba(99, 102, 241, 0)');

    convergenceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map((_, i) => i + 1),
            datasets: [{
                label: 'Energy',
                data: data,
                borderColor: colors.primary,
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.3,
                pointRadius: data.length > 50 ? 0 : 3,
                pointHoverRadius: 6,
                pointBackgroundColor: colors.primary,
                pointBorderColor: '#fff',
                pointBorderWidth: 2
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
                    backgroundColor: colors.tooltip,
                    titleColor: colors.tooltipText,
                    bodyColor: colors.tooltipText === '#f8fafc' ? '#94a3b8' : '#64748b',
                    borderColor: theme === 'dark' ? '#2a2a3a' : '#e2e8f0',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        title: (items) => `Iteration ${items[0].label}`,
                        label: (item) => {
                            const val = item.raw;
                            const min = Math.min(...data);
                            const improvement = data.length > 1
                                ? (((data[0] - val) / Math.abs(data[0])) * 100).toFixed(2)
                                : 0;
                            return [
                                `Energy: ${val.toFixed(6)}`,
                                data.length > 1 && item.dataIndex > 0
                                    ? `Improvement: ${improvement}%`
                                    : 'Starting point'
                            ];
                        }
                    }
                },
                zoom: window.ChartZoom ? {
                    pan: {
                        enabled: true,
                        mode: 'xy'
                    },
                    zoom: {
                        wheel: {
                            enabled: true
                        },
                        pinch: {
                            enabled: true
                        },
                        mode: 'xy'
                    }
                } : undefined
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Iteration',
                        color: colors.text,
                        font: { weight: '500' }
                    },
                    grid: { color: colors.grid },
                    ticks: { color: colors.text }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Energy',
                        color: colors.text,
                        font: { weight: '500' }
                    },
                    grid: { color: colors.grid },
                    ticks: {
                        color: colors.text,
                        callback: (val) => val.toFixed(4)
                    }
                }
            },
            animation: {
                duration: data.length > 100 ? 0 : 750
            }
        }
    });
}

/**
 * Initialize Measurement Histogram
 */
export async function initMeasurementHistogram(counts) {
    const canvas = document.getElementById('histogram-chart');
    if (!canvas || !counts) return;

    try {
        await loadChartJS();
    } catch (error) {
        return;
    }

    if (!window.Chart) return;

    if (histogramChart) {
        histogramChart.destroy();
    }

    const ctx = canvas.getContext('2d');
    const theme = document.documentElement.getAttribute('data-theme') || 'dark';
    const colors = {
        grid: theme === 'dark' ? 'rgba(42, 42, 58, 0.5)' : 'rgba(203, 213, 225, 0.5)',
        text: theme === 'dark' ? '#64748b' : '#64748b',
        primary: '#6366f1',
        secondary: '#8b5cf6',
        accent: '#06b6d4'
    };

    const entries = Object.entries(counts);
    const total = entries.reduce((sum, [, count]) => sum + count, 0);
    const sorted = entries.sort((a, b) => b[1] - a[1]).slice(0, 20);
    const maxValue = Math.max(...sorted.map(([, c]) => c));

    const barColors = sorted.map(([, count], i) => {
        if (i === 0) return colors.primary;
        if (i === 1) return colors.secondary;
        if (i === 2) return colors.accent;
        const opacity = 0.8 - (i * 0.03);
        return `rgba(99, 102, 241, ${Math.max(0.3, opacity)})`;
    });

    histogramChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sorted.map(([state]) => state),
            datasets: [{
                label: 'Count',
                data: sorted.map(([, count]) => count),
                backgroundColor: barColors,
                borderColor: barColors.map(c => c.replace('0.8', '1').replace('0.3', '0.6')),
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
                    backgroundColor: theme === 'dark' ? '#1a1a25' : '#ffffff',
                    titleColor: theme === 'dark' ? '#f8fafc' : '#1e293b',
                    bodyColor: theme === 'dark' ? '#94a3b8' : '#64748b',
                    callbacks: {
                        title: (items) => `State: |${items[0].label}⟩`,
                        label: (item) => {
                            const count = item.raw;
                            const prob = ((count / total) * 100).toFixed(2);
                            return [
                                `Count: ${count}`,
                                `Probability: ${prob}%`,
                                count === maxValue ? '🏆 Most probable' : ''
                            ].filter(Boolean);
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Bitstring State',
                        color: colors.text
                    },
                    grid: { display: false },
                    ticks: {
                        color: colors.text,
                        font: { family: 'monospace', size: 10 },
                        maxRotation: 45
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Measurement Count',
                        color: colors.text
                    },
                    grid: { color: colors.grid },
                    ticks: { color: colors.text },
                    beginAtZero: true
                }
            }
        }
    });
}

/**
 * Initialize Statevector Visualization for VQE
 */
export async function initStatevectorChart(statevector) {
    const canvas = document.getElementById('statevector-chart');
    if (!canvas || !statevector) return;

    try {
        await loadChartJS();
    } catch (error) {
        return;
    }

    if (!window.Chart) return;

    if (statevectorChart) {
        statevectorChart.destroy();
    }

    const ctx = canvas.getContext('2d');
    const theme = document.documentElement.getAttribute('data-theme') || 'dark';
    const colors = {
        grid: theme === 'dark' ? 'rgba(42, 42, 58, 0.5)' : 'rgba(203, 213, 225, 0.5)',
        text: theme === 'dark' ? '#64748b' : '#64748b',
        primary: '#6366f1',
        success: '#10b981',
        warning: '#f59e0b',
        error: '#ef4444'
    };

    const amplitudes = Array.isArray(statevector)
        ? statevector.map((v, i) => ({
            state: i.toString(2).padStart(Math.log2(statevector.length), '0'),
            amplitude: typeof v === 'object' ? v.amplitude : Math.abs(v),
            phase: typeof v === 'object' ? v.phase : 0,
            real: typeof v === 'object' ? v.real : v.real || v,
            imag: typeof v === 'object' ? v.imag : v.imag || 0
        }))
        : Object.entries(statevector).map(([state, amp]) => ({
            state,
            amplitude: typeof amp === 'object' ? amp.amplitude : Math.abs(amp),
            phase: typeof amp === 'object' ? amp.phase : 0,
            real: typeof amp === 'object' ? amp.real : amp.real || amp,
            imag: typeof amp === 'object' ? amp.imag : amp.imag || 0
        }));

    const probabilities = amplitudes.map(a => ({
        state: a.state,
        prob: a.amplitude ** 2
    })).filter(a => a.prob > 0.001).sort((a, b) => b.prob - a.prob).slice(0, 20);

    const barColors = probabilities.map((p, i) => {
        const hue = 250 - (i * 15);
        return `hsla(${hue}, 70%, 60%, 0.85)`;
    });

    statevectorChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: probabilities.map(p => p.state),
            datasets: [{
                label: 'Probability',
                data: probabilities.map(p => p.prob),
                backgroundColor: barColors,
                borderColor: barColors.map(c => c.replace('0.85', '1')),
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                title: {
                    display: true,
                    text: 'Statevector Probability Distribution',
                    color: colors.text,
                    font: { size: 14, weight: '600' }
                },
                tooltip: {
                    backgroundColor: theme === 'dark' ? '#1a1a25' : '#ffffff',
                    callbacks: {
                        title: (items) => `|${items[0].label}⟩`,
                        label: (item) => {
                            const prob = item.raw;
                            const amp = amplitudes.find(a => a.state === item.label);
                            return [
                                `Probability: ${(prob * 100).toFixed(4)}%`,
                                `Amplitude: ${amp?.amplitude?.toFixed(6) || 'N/A'}`,
                                prob > 0.5 ? '🎯 Dominant state' : ''
                            ].filter(Boolean);
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Quantum State',
                        color: colors.text
                    },
                    grid: { display: false },
                    ticks: {
                        color: colors.text,
                        font: { family: 'monospace', size: 9 }
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Probability |ψ|²',
                        color: colors.text
                    },
                    grid: { color: colors.grid },
                    ticks: {
                        color: colors.text,
                        callback: (v) => `${(v * 100).toFixed(1)}%`
                    },
                    max: 1
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
    const theme = document.documentElement.getAttribute('data-theme') || 'dark';

    energyDistChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Frequency',
                data: bins,
                backgroundColor: 'rgba(16, 185, 129, 0.6)',
                borderColor: 'rgba(16, 185, 129, 1)',
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
                    backgroundColor: theme === 'dark' ? '#1a1a25' : '#ffffff',
                    callbacks: {
                        label: (item) => `Count: ${item.raw} samples`
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Energy',
                        color: theme === 'dark' ? '#64748b' : '#64748b'
                    },
                    grid: { display: false },
                    ticks: {
                        color: theme === 'dark' ? '#64748b' : '#64748b',
                        maxRotation: 45
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Count',
                        color: theme === 'dark' ? '#64748b' : '#64748b'
                    },
                    grid: { color: theme === 'dark' ? 'rgba(42, 42, 58, 0.5)' : 'rgba(203, 213, 225, 0.5)' },
                    ticks: { color: theme === 'dark' ? '#64748b' : '#64748b' }
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

    let sortedData;
    if (Array.isArray(probabilities)) {
        sortedData = probabilities.map((p, i) => ({ state: i.toString(), prob: p }))
            .filter(d => d.prob > 0.001);
    } else {
        sortedData = Object.entries(probabilities)
            .map(([state, prob]) => ({ state, prob }))
            .filter(d => d.prob > 0.001);
    }

    sortedData.sort((a, b) => b.prob - a.prob);
    sortedData = sortedData.slice(0, 20);

    const ctx = canvas.getContext('2d');
    const theme = document.documentElement.getAttribute('data-theme') || 'dark';

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
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: theme === 'dark' ? '#1a1a25' : '#ffffff',
                    titleColor: theme === 'dark' ? '#f8fafc' : '#1e293b',
                    bodyColor: theme === 'dark' ? '#94a3b8' : '#64748b',
                    callbacks: {
                        label: ctx => `Probability: ${(ctx.raw * 100).toFixed(2)}%`
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Probability',
                        color: theme === 'dark' ? '#64748b' : '#64748b'
                    },
                    grid: { color: theme === 'dark' ? 'rgba(42, 42, 58, 0.5)' : 'rgba(203, 213, 225, 0.5)' },
                    ticks: {
                        color: theme === 'dark' ? '#64748b' : '#64748b',
                        callback: v => (v * 100).toFixed(0) + '%'
                    },
                    max: 1
                },
                y: {
                    grid: { display: false },
                    ticks: {
                        color: theme === 'dark' ? '#64748b' : '#64748b',
                        font: { family: 'monospace', size: 10 }
                    }
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

    const gamma = params.gamma || params.gammas || [];
    const beta = params.beta || params.betas || [];

    const ctx = canvas.getContext('2d');
    const theme = document.documentElement.getAttribute('data-theme') || 'dark';

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
                    tension: 0.3,
                    pointRadius: 5,
                    pointHoverRadius: 8
                },
                {
                    label: 'β (beta)',
                    data: beta,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 5,
                    pointHoverRadius: 8
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
                    labels: {
                        color: theme === 'dark' ? '#94a3b8' : '#64748b',
                        boxWidth: 12,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    backgroundColor: theme === 'dark' ? '#1a1a25' : '#ffffff',
                    titleColor: theme === 'dark' ? '#f8fafc' : '#1e293b',
                    bodyColor: theme === 'dark' ? '#94a3b8' : '#64748b',
                    callbacks: {
                        label: (item) => `${item.dataset.label}: ${item.raw.toFixed(4)}`
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: theme === 'dark' ? 'rgba(42, 42, 58, 0.5)' : 'rgba(203, 213, 225, 0.5)' },
                    ticks: { color: theme === 'dark' ? '#64748b' : '#64748b' }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Parameter Value',
                        color: theme === 'dark' ? '#64748b' : '#64748b'
                    },
                    grid: { color: theme === 'dark' ? 'rgba(42, 42, 58, 0.5)' : 'rgba(203, 213, 225, 0.5)' },
                    ticks: { color: theme === 'dark' ? '#64748b' : '#64748b' }
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

    try {
        await loadChartJS();
    } catch (error) {
        console.error('Failed to load Chart.js for pie chart');
        return;
    }

    if (!window.Chart) return;

    if (statusPieChart) {
        statusPieChart.destroy();
    }

    const ctx = canvas.getContext('2d');
    const theme = document.documentElement.getAttribute('data-theme') || 'dark';

    statusPieChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Completed', 'Running', 'Pending', 'Failed'],
            datasets: [{
                data: [data.completed, data.running, data.pending, data.failed],
                backgroundColor: [
                    'rgba(16, 185, 129, 0.8)',
                    'rgba(59, 130, 246, 0.8)',
                    'rgba(245, 158, 11, 0.8)',
                    'rgba(239, 68, 68, 0.8)'
                ],
                borderColor: [
                    'rgb(16, 185, 129)',
                    'rgb(59, 130, 246)',
                    'rgb(245, 158, 11)',
                    'rgb(239, 68, 68)'
                ],
                borderWidth: 2,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: theme === 'dark' ? '#1a1a25' : '#ffffff',
                    titleColor: theme === 'dark' ? '#f8fafc' : '#1e293b',
                    bodyColor: theme === 'dark' ? '#94a3b8' : '#64748b',
                    borderColor: theme === 'dark' ? '#2a2a3a' : '#e2e8f0',
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
    if (histogramChart) {
        histogramChart.destroy();
        histogramChart = null;
    }
    if (statevectorChart) {
        statevectorChart.destroy();
        statevectorChart = null;
    }
}
