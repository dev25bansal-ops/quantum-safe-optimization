/**
 * Visualizations Module
 * Handles custom visualizations: bitstring, graph, statevector, and job visualizations
 * Enhanced with interactive graph rendering and statevector displays
 */

import { STATE } from './config.js';
import {
    initConvergenceChart,
    initEnergyDistributionChart,
    initProbabilityChart,
    initParameterChart,
    initMeasurementHistogram,
    initStatevectorChart
} from './charts.js';

const graphState = {
    showLabels: true,
    hoveredNode: null,
    selectedNode: null,
    zoom: 1,
    panX: 0,
    panY: 0,
    isDragging: false,
    lastMouseX: 0,
    lastMouseY: 0
};

/**
 * Render bitstring visualization grid
 */
export function renderBitstringViz(bitstringStr) {
    const container = document.getElementById('bitstring-viz');
    if (!container) return;

    const bits = bitstringStr.split('').map(Number);
    const cols = Math.ceil(Math.sqrt(bits.length));
    container.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;

    container.innerHTML = bits.map((bit, index) => `
        <div class="bit-cell ${bit === 1 ? 'one' : 'zero'}" 
             title="Qubit ${index}: ${bit}"
             data-index="${index}">
            ${bit}
        </div>
    `).join('');

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

    container.innerHTML = bits.map((bit, index) => {
        const intensity = bit === 1 ? 0.7 + Math.random() * 0.3 : 0.1 + Math.random() * 0.2;
        const hue = bit === 1 ? 270 : 220;
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
 * Render Enhanced Graph Visualization (MaxCut/QAOA/TSP)
 * Features: Interactive pan/zoom, node hover effects, edge highlighting
 */
export function renderGraphVisualization(graph, solution, options = {}) {
    const canvas = document.getElementById('graph-canvas');
    if (!canvas || !graph) return;

    const ctx = canvas.getContext('2d');
    const container = canvas.parentElement;
    const width = canvas.width = container.clientWidth;
    const height = canvas.height = container.clientHeight;

    const solutionBits = typeof solution === 'string' ? solution.split('').map(Number) : solution || [];

    const isAdjacencyMatrix = Array.isArray(graph) && Array.isArray(graph[0]);
    let edges = [];
    let nodeCount;

    if (isAdjacencyMatrix) {
        nodeCount = graph.length;
        for (let i = 0; i < graph.length; i++) {
            for (let j = i + 1; j < graph[i].length; j++) {
                if (graph[i][j] > 0) {
                    edges.push({
                        from: i,
                        to: j,
                        weight: graph[i][j],
                        isCut: solutionBits[i] !== solutionBits[j]
                    });
                }
            }
        }
    } else {
        const edgeList = graph.edges || graph;
        const nodeSet = new Set();
        edgeList.forEach(e => {
            nodeSet.add(e[0]);
            nodeSet.add(e[1]);
        });
        nodeCount = graph.nodes || Math.max(...Array.from(nodeSet)) + 1;

        edges = edgeList.map(e => ({
            from: Array.isArray(e) ? e[0] : e.from,
            to: Array.isArray(e) ? e[1] : e.to,
            weight: Array.isArray(e) ? (e[2] || 1) : (e.weight || 1),
            isCut: solutionBits[Array.isArray(e) ? e[0] : e.from] !== solutionBits[Array.isArray(e) ? e[1] : e.to]
        }));
    }

    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.35 * graphState.zoom;

    const nodes = Array.from({ length: nodeCount }, (_, i) => ({
        id: i,
        x: centerX + radius * Math.cos(2 * Math.PI * i / nodeCount - Math.PI / 2) + graphState.panX,
        y: centerY + radius * Math.sin(2 * Math.PI * i / nodeCount - Math.PI / 2) + graphState.panY,
        set: solutionBits[i] || 0,
        label: i.toString()
    }));

    function draw() {
        ctx.clearRect(0, 0, width, height);

        ctx.fillStyle = 'rgba(10, 10, 20, 0.3)';
        ctx.fillRect(0, 0, width, height);

        edges.forEach(edge => {
            const fromNode = nodes[edge.from];
            const toNode = nodes[edge.to];

            if (!fromNode || !toNode) return;

            ctx.beginPath();
            ctx.moveTo(fromNode.x, fromNode.y);
            ctx.lineTo(toNode.x, toNode.y);

            const isHovered = graphState.hoveredNode === edge.from || graphState.hoveredNode === edge.to;

            if (edge.isCut) {
                ctx.strokeStyle = isHovered ? '#fbbf24' : '#f59e0b';
                ctx.lineWidth = isHovered ? 4 : 3;
                ctx.shadowColor = 'rgba(245, 158, 11, 0.6)';
                ctx.shadowBlur = isHovered ? 15 : 10;
            } else {
                ctx.strokeStyle = isHovered ? 'rgba(148, 163, 184, 0.6)' : 'rgba(100, 116, 139, 0.25)';
                ctx.lineWidth = isHovered ? 2 : 1;
                ctx.shadowBlur = 0;
            }

            ctx.stroke();
            ctx.shadowBlur = 0;

            if (edge.weight !== 1 && graphState.showLabels) {
                const midX = (fromNode.x + toNode.x) / 2;
                const midY = (fromNode.y + toNode.y) / 2;
                ctx.fillStyle = '#94a3b8';
                ctx.font = '10px system-ui';
                ctx.textAlign = 'center';
                ctx.fillText(edge.weight.toFixed(1), midX, midY - 5);
            }
        });

        nodes.forEach((node, i) => {
            const nodeRadius = graphState.hoveredNode === i ? 28 : 22;
            const isHovered = graphState.hoveredNode === i;

            ctx.beginPath();
            ctx.arc(node.x, node.y, nodeRadius, 0, 2 * Math.PI);

            const gradient = ctx.createRadialGradient(
                node.x - nodeRadius * 0.2, node.y - nodeRadius * 0.2, 0,
                node.x, node.y, nodeRadius
            );

            if (node.set === 1) {
                gradient.addColorStop(0, isHovered ? '#a5b4fc' : '#818cf8');
                gradient.addColorStop(1, isHovered ? '#6366f1' : '#4f46e5');
                ctx.shadowColor = isHovered ? 'rgba(99, 102, 241, 0.8)' : 'rgba(99, 102, 241, 0.5)';
            } else {
                gradient.addColorStop(0, isHovered ? '#5eead4' : '#34d399');
                gradient.addColorStop(1, isHovered ? '#10b981' : '#059669');
                ctx.shadowColor = isHovered ? 'rgba(16, 185, 129, 0.8)' : 'rgba(16, 185, 129, 0.5)';
            }

            ctx.fillStyle = gradient;
            ctx.shadowBlur = isHovered ? 20 : 12;
            ctx.fill();
            ctx.shadowBlur = 0;

            ctx.strokeStyle = node.set === 1 ? '#4f46e5' : '#059669';
            ctx.lineWidth = isHovered ? 3 : 2;
            ctx.stroke();

            if (graphState.showLabels) {
                ctx.fillStyle = '#ffffff';
                ctx.font = `bold ${isHovered ? 14 : 12}px Inter, system-ui`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(node.label, node.x, node.y);
            }
        });

        drawLegend();
        drawStats();
    }

    function drawLegend() {
        const legendY = height - 80;
        ctx.font = '11px Inter, system-ui';
        ctx.textAlign = 'left';

        ctx.fillStyle = '#6366f1';
        ctx.beginPath();
        ctx.arc(20, legendY, 8, 0, 2 * Math.PI);
        ctx.fill();
        ctx.fillStyle = '#94a3b8';
        ctx.fillText('Set A (1)', 35, legendY + 4);

        ctx.fillStyle = '#10b981';
        ctx.beginPath();
        ctx.arc(100, legendY, 8, 0, 2 * Math.PI);
        ctx.fill();
        ctx.fillStyle = '#94a3b8';
        ctx.fillText('Set B (0)', 115, legendY + 4);

        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(20, legendY + 25);
        ctx.lineTo(50, legendY + 25);
        ctx.stroke();
        ctx.fillStyle = '#94a3b8';
        ctx.fillText('Cut Edge', 60, legendY + 29);

        ctx.strokeStyle = 'rgba(100, 116, 139, 0.4)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(140, legendY + 25);
        ctx.lineTo(170, legendY + 25);
        ctx.stroke();
        ctx.fillStyle = '#94a3b8';
        ctx.fillText('Same Set', 180, legendY + 29);
    }

    function drawStats() {
        const cutCount = edges.filter(e => e.isCut).length;
        const statsY = 20;

        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fillRect(10, statsY - 5, 150, 60);

        ctx.font = '12px system-ui';
        ctx.fillStyle = '#94a3b8';
        ctx.textAlign = 'left';
        ctx.fillText(`Nodes: ${nodeCount}`, 20, statsY + 12);
        ctx.fillText(`Edges: ${edges.length}`, 20, statsY + 28);
        ctx.fillStyle = '#f59e0b';
        ctx.fillText(`Cut Value: ${cutCount}`, 20, statsY + 44);
    }

    canvas.onmousemove = (e) => {
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        if (graphState.isDragging) {
            graphState.panX += mouseX - graphState.lastMouseX;
            graphState.panY += mouseY - graphState.lastMouseY;
            graphState.lastMouseX = mouseX;
            graphState.lastMouseY = mouseY;
            draw();
            return;
        }

        let hoveredNode = null;
        nodes.forEach((node, i) => {
            const dist = Math.sqrt((mouseX - node.x) ** 2 + (mouseY - node.y) ** 2);
            if (dist < 25) {
                hoveredNode = i;
            }
        });

        if (hoveredNode !== graphState.hoveredNode) {
            graphState.hoveredNode = hoveredNode;
            canvas.style.cursor = hoveredNode !== null ? 'pointer' : 'grab';
            draw();

            if (hoveredNode !== null) {
                const node = nodes[hoveredNode];
                const connectedEdges = edges.filter(e => e.from === hoveredNode || e.to === hoveredNode);
                const cutEdges = connectedEdges.filter(e => e.isCut).length;

                showNodeTooltip(e.clientX, e.clientY, {
                    id: hoveredNode,
                    set: node.set ? 'A' : 'B',
                    degree: connectedEdges.length,
                    cutEdges: cutEdges
                });
            } else {
                hideNodeTooltip();
            }
        }
    };

    canvas.onmousedown = (e) => {
        graphState.isDragging = true;
        graphState.lastMouseX = e.offsetX;
        graphState.lastMouseY = e.offsetY;
        canvas.style.cursor = 'grabbing';
    };

    canvas.onmouseup = () => {
        graphState.isDragging = false;
        canvas.style.cursor = graphState.hoveredNode !== null ? 'pointer' : 'grab';
    };

    canvas.onmouseleave = () => {
        graphState.isDragging = false;
        graphState.hoveredNode = null;
        hideNodeTooltip();
        draw();
    };

    canvas.onwheel = (e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        graphState.zoom = Math.max(0.5, Math.min(3, graphState.zoom * delta));
        draw();
    };

    draw();

    document.getElementById('graph-cut-value').textContent = edges.filter(e => e.isCut).length;
    document.getElementById('graph-node-count').textContent = nodeCount;
    document.getElementById('graph-edge-count').textContent = edges.length;
}

function showNodeTooltip(x, y, data) {
    let tooltip = document.getElementById('graph-tooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.id = 'graph-tooltip';
        tooltip.className = 'graph-tooltip';
        document.body.appendChild(tooltip);
    }

    tooltip.innerHTML = `
        <div class="tooltip-header">Node ${data.id}</div>
        <div class="tooltip-row">
            <span>Partition:</span>
            <span class="tooltip-value set-${data.set.toLowerCase()}">Set ${data.set}</span>
        </div>
        <div class="tooltip-row">
            <span>Degree:</span>
            <span>${data.degree} edges</span>
        </div>
        <div class="tooltip-row">
            <span>Cut Edges:</span>
            <span class="tooltip-value cut">${data.cutEdges}</span>
        </div>
    `;

    tooltip.style.left = `${x + 15}px`;
    tooltip.style.top = `${y + 15}px`;
    tooltip.style.display = 'block';
}

function hideNodeTooltip() {
    const tooltip = document.getElementById('graph-tooltip');
    if (tooltip) {
        tooltip.style.display = 'none';
    }
}

/**
 * Render VQE Energy Landscape (for molecular VQE jobs)
 */
export function renderVQEEnergyLandscape(bondLengths, energies) {
    const canvas = document.getElementById('vqe-energy-canvas');
    if (!canvas || !bondLengths || !energies) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.parentElement.clientWidth;
    const height = canvas.height = 250;

    const padding = { top: 30, right: 30, bottom: 40, left: 60 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;

    const minX = Math.min(...bondLengths);
    const maxX = Math.max(...bondLengths);
    const minY = Math.min(...energies);
    const maxY = Math.max(...energies);

    const scaleX = (x) => padding.left + ((x - minX) / (maxX - minX)) * plotWidth;
    const scaleY = (y) => padding.top + plotHeight - ((y - minY) / (maxY - minY)) * plotHeight;

    ctx.fillStyle = 'rgba(10, 10, 20, 0.5)';
    ctx.fillRect(0, 0, width, height);

    ctx.strokeStyle = 'rgba(148, 163, 184, 0.2)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 10; i++) {
        const y = padding.top + (i / 10) * plotHeight;
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(width - padding.right, y);
        ctx.stroke();
    }

    ctx.strokeStyle = '#6366f1';
    ctx.lineWidth = 2;
    ctx.beginPath();

    const sortedData = bondLengths.map((x, i) => ({ x, y: energies[i] }))
        .sort((a, b) => a.x - b.x);

    sortedData.forEach((point, i) => {
        const px = scaleX(point.x);
        const py = scaleY(point.y);
        if (i === 0) {
            ctx.moveTo(px, py);
        } else {
            ctx.lineTo(px, py);
        }
    });
    ctx.stroke();

    const gradient = ctx.createLinearGradient(0, padding.top, 0, height - padding.bottom);
    gradient.addColorStop(0, 'rgba(99, 102, 241, 0.3)');
    gradient.addColorStop(1, 'rgba(99, 102, 241, 0)');

    ctx.fillStyle = gradient;
    ctx.beginPath();
    sortedData.forEach((point, i) => {
        const px = scaleX(point.x);
        const py = scaleY(point.y);
        if (i === 0) {
            ctx.moveTo(px, py);
        } else {
            ctx.lineTo(px, py);
        }
    });
    ctx.lineTo(scaleX(sortedData[sortedData.length - 1].x), height - padding.bottom);
    ctx.lineTo(scaleX(sortedData[0].x), height - padding.bottom);
    ctx.closePath();
    ctx.fill();

    sortedData.forEach((point, i) => {
        const px = scaleX(point.x);
        const py = scaleY(point.y);

        ctx.beginPath();
        ctx.arc(px, py, 5, 0, 2 * Math.PI);
        ctx.fillStyle = '#6366f1';
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
    });

    const minIdx = energies.indexOf(Math.min(...energies));
    const minPoint = { x: bondLengths[minIdx], y: energies[minIdx] };
    const minPx = scaleX(minPoint.x);
    const minPy = scaleY(minPoint.y);

    ctx.beginPath();
    ctx.arc(minPx, minPy, 8, 0, 2 * Math.PI);
    ctx.fillStyle = '#10b981';
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = '#10b981';
    ctx.font = 'bold 12px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText(`min: ${minPoint.y.toFixed(4)} Ha`, minPx, minPy - 15);

    ctx.fillStyle = '#94a3b8';
    ctx.font = '12px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('Bond Length (Å)', width / 2, height - 10);

    ctx.save();
    ctx.translate(15, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Energy (Hartree)', 0, 0);
    ctx.restore();
}

/**
 * Toggle graph labels visibility
 */
export function toggleGraphLabels() {
    graphState.showLabels = !graphState.showLabels;
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
    graphState.zoom = 1;
    graphState.panX = 0;
    graphState.panY = 0;
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

    const solutionVizSection = document.getElementById('solution-viz-section');
    const vizGridSection = document.getElementById('viz-grid-section');
    const graphVizSection = document.getElementById('graph-viz-section');

    const solution = job.result.optimal_bitstring || job.result.optimal_solution;
    if (solution && typeof solution === 'string' && /^[01]+$/.test(solution)) {
        if (solutionVizSection) solutionVizSection.style.display = 'block';
        renderBitstringViz(solution);
        initVizTabs();
        document.querySelector('.viz-tab[data-viz="bitstring"]')?.classList.add('active');
        document.querySelector('.viz-tab[data-viz="heatmap"]')?.classList.remove('active');
    } else {
        if (solutionVizSection) solutionVizSection.style.display = 'none';
    }

    const hasConvergence = job.result.convergence_history?.length > 0;
    const hasProbabilities = job.result.probabilities || job.result.state_probabilities;
    const hasParams = job.result.optimal_params;
    const hasCounts = job.result.counts || job.result.measurement_counts;

    if (hasConvergence || hasProbabilities || hasParams || hasCounts) {
        if (vizGridSection) vizGridSection.style.display = 'grid';

        if (hasConvergence) {
            await initConvergenceChart('convergence-chart', job.result.convergence_history);
        }

        const energyData = job.result.energy_levels ||
            (hasConvergence && job.result.convergence_history.length > 5 ? job.result.convergence_history : null);
        if (energyData && energyData.length > 0) {
            await initEnergyDistributionChart(energyData);
        }

        if (hasProbabilities) {
            const probs = job.result.probabilities || job.result.state_probabilities;
            await initProbabilityChart(probs);
        }

        if (hasParams) {
            await initParameterChart(job.result.optimal_params);
        }

        if (hasCounts) {
            await initMeasurementHistogram(job.result.counts || job.result.measurement_counts);
        }

        if (job.result.statevector) {
            await initStatevectorChart(job.result.statevector);
        }
    } else {
        if (vizGridSection) vizGridSection.style.display = 'none';
    }

    if (job.problem_type === 'QAOA' && job.problem_config?.graph && solution) {
        if (graphVizSection) graphVizSection.style.display = 'block';
        renderGraphVisualization(job.problem_config.graph, solution);
    } else if (job.problem_type === 'VQE' && job.result.bond_lengths && job.result.energies) {
        if (graphVizSection) graphVizSection.style.display = 'block';
        renderVQEEnergyLandscape(job.result.bond_lengths, job.result.energies);
    } else {
        if (graphVizSection) graphVizSection.style.display = 'none';
    }
}

window.toggleGraphLabels = toggleGraphLabels;
window.resetGraphView = resetGraphView;
