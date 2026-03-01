/**
 * Visualizations Module
 * Handles custom visualizations: bitstring, graph, and job visualizations
 */

import { STATE } from './config.js';
import { initConvergenceChart, initEnergyDistributionChart, initProbabilityChart, initParameterChart } from './charts.js';

// Graph visualization state
const graphState = {
    showLabels: true
};

/**
 * Render bitstring visualization grid
 */
export function renderBitstringViz(bitstringStr) {
    const container = document.getElementById('bitstring-viz');
    if (!container) return;

    const bits = bitstringStr.split('').map(Number);

    // Calculate grid dimensions (aim for roughly square)
    const cols = Math.ceil(Math.sqrt(bits.length));
    container.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;

    container.innerHTML = bits.map((bit, index) => `
        <div class="bit-cell ${bit === 1 ? 'one' : 'zero'}" title="Qubit ${index}: ${bit}">
            ${bit}
        </div>
    `).join('');

    // Update solution summary
    const solutionSummary = document.getElementById('solution-summary');
    if (solutionSummary) {
        const ones = bits.filter(b => b === 1).length;
        const zeros = bits.length - ones;
        solutionSummary.innerHTML = `
            <span class="summary-item"><strong>${bits.length}</strong> qubits</span>
            <span class="summary-item"><span class="bit-indicator one"></span>${ones} ones</span>
            <span class="summary-item"><span class="bit-indicator zero"></span>${zeros} zeros</span>
        `;
    }
}

/**
 * Render heatmap visualization
 */
export function renderHeatmapViz(bitstringStr, probabilities = null) {
    const container = document.getElementById('bitstring-viz');
    if (!container) return;

    const bits = bitstringStr.split('').map(Number);
    const cols = Math.ceil(Math.sqrt(bits.length));
    container.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;

    // Generate heatmap with intensity based on bit value and position
    container.innerHTML = bits.map((bit, index) => {
        // Calculate a pseudo-intensity (in real case, would use probability data)
        const intensity = bit === 1 ? 0.7 + Math.random() * 0.3 : 0.1 + Math.random() * 0.2;
        const hue = bit === 1 ? 270 : 220; // Purple for 1, blue for 0
        const saturation = 80;
        const lightness = Math.round(30 + intensity * 40);

        return `
            <div class="bit-cell heatmap-cell" 
                 title="Qubit ${index}: ${bit} (${(intensity * 100).toFixed(0)}%)"
                 style="background: hsl(${hue}, ${saturation}%, ${lightness}%); 
                        box-shadow: 0 0 ${intensity * 10}px hsla(${hue}, ${saturation}%, ${lightness}%, 0.5);">
                ${bit}
            </div>
        `;
    }).join('');
}

/**
 * Initialize viz tab handlers
 */
export function initVizTabs() {
    const tabs = document.querySelectorAll('.viz-tab');
    const bitstringContainer = document.getElementById('bitstring-viz');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Update active tab
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            const vizType = tab.dataset.viz;
            const currentBitstring = STATE.selectedJob?.result?.optimal_bitstring ||
                STATE.selectedJob?.result?.optimal_solution || '';

            if (currentBitstring) {
                if (vizType === 'heatmap') {
                    renderHeatmapViz(currentBitstring, STATE.selectedJob?.result?.probabilities);
                } else {
                    renderBitstringViz(currentBitstring);
                }
            }
        });
    });
}

/**
 * Render Graph Visualization (MaxCut/QAOA)
 */
export function renderGraphVisualization(graph, solution) {
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
export function toggleGraphLabels() {
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
export function resetGraphView() {
    const job = STATE.jobs.find(j => j.job_id === STATE.selectedJobId);
    if (job?.problem_config?.graph && job?.result?.optimal_bitstring) {
        renderGraphVisualization(job.problem_config.graph, job.result.optimal_bitstring);
    }
}

/**
 * Update all job visualizations
 */
export async function updateJobVisualizations(job) {
    if (!job || job.status !== 'completed' || !job.result) return;

    // Show solution visualization section
    const solutionVizSection = document.getElementById('solution-viz-section');
    const vizGridSection = document.getElementById('viz-grid-section');
    const graphVizSection = document.getElementById('graph-viz-section');

    // Render bitstring visualization
    const solution = job.result.optimal_bitstring || job.result.optimal_solution;
    if (solution && typeof solution === 'string' && /^[01]+$/.test(solution)) {
        if (solutionVizSection) solutionVizSection.style.display = 'block';
        renderBitstringViz(solution);
        // Initialize viz tab handlers for bitstring/heatmap toggle
        initVizTabs();
        // Reset to bitstring tab
        document.querySelector('.viz-tab[data-viz="bitstring"]')?.classList.add('active');
        document.querySelector('.viz-tab[data-viz="heatmap"]')?.classList.remove('active');
    } else {
        if (solutionVizSection) solutionVizSection.style.display = 'none';
    }

    // Show visualization grid if we have chart data
    const hasConvergence = job.result.convergence_history?.length > 0;
    const hasProbabilities = job.result.probabilities || job.result.state_probabilities;
    const hasParams = job.result.optimal_params;

    if (hasConvergence || hasProbabilities || hasParams) {
        if (vizGridSection) vizGridSection.style.display = 'grid';

        // Convergence chart
        if (hasConvergence) {
            await initConvergenceChart('convergence-chart', job.result.convergence_history);
        }

        // Energy distribution (use energy_levels if available, fallback to convergence history)
        const energyData = job.result.energy_levels ||
            (hasConvergence && job.result.convergence_history.length > 5 ? job.result.convergence_history : null);
        if (energyData && energyData.length > 0) {
            await initEnergyDistributionChart(energyData);
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
        if (vizGridSection) vizGridSection.style.display = 'none';
    }

    // Graph visualization for MaxCut/QAOA with graph config
    if (job.problem_config?.graph && solution) {
        if (graphVizSection) graphVizSection.style.display = 'block';
        renderGraphVisualization(job.problem_config.graph, solution);
    } else {
        if (graphVizSection) graphVizSection.style.display = 'none';
    }
}

// Make functions globally accessible
window.toggleGraphLabels = toggleGraphLabels;
window.resetGraphView = resetGraphView;
