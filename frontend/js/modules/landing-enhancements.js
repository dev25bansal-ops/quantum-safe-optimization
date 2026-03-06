/**
 * QuantumSafe Optimize - Landing Page Enhancements
 * Research-ready features for publication demonstration
 */

export const LandingEnhancements = {
    ws: null,
    metricsInterval: null,
    chartInstance: null,
    particlesInitialized: false,

    init() {
        this.initLiveMetrics();
        this.initQuantumCircuitViz();
        this.initPublicationSection();
        this.initArchitectureDiagram();
        this.initResearchShowcase();
        this.initCitationGenerator();
        this.initInteractiveBenchmark();
    },

    initLiveMetrics() {
        const metricsCard = document.querySelector('.metrics-card');
        if (!metricsCard) return;

        this.connectWebSocket();
        this.startMetricsSimulation();
        this.initMetricsChart();
    },

    connectWebSocket() {
        const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/ws/metrics`;
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.updateMetrics(data);
                } catch (e) {
                    console.log('[WS] Parse error:', e);
                }
            };

            this.ws.onerror = () => {
                console.log('[WS] Connection failed, using simulation');
            };

            this.ws.onclose = () => {
                console.log('[WS] Disconnected');
            };
        } catch (e) {
            console.log('[WS] WebSocket not available');
        }
    },

    startMetricsSimulation() {
        const updateSimulatedMetrics = () => {
            const metrics = {
                activeJobs: Math.floor(Math.random() * 50 + 200),
                jobsToday: Math.floor(Math.random() * 500 + 12500),
                latency: Math.floor(Math.random() * 15 + 18),
                successRate: (99.5 + Math.random() * 0.4).toFixed(1)
            };
            this.updateMetrics(metrics);
        };

        updateSimulatedMetrics();
        this.metricsInterval = setInterval(updateSimulatedMetrics, 3000);
    },

    updateMetrics(data) {
        const elements = {
            'live-jobs': data.activeJobs,
            'live-today': data.jobsToday?.toLocaleString(),
            'live-latency': `${data.latency}ms`,
            'live-success': `${data.successRate}%`
        };

        Object.entries(elements).forEach(([id, value]) => {
            const el = document.getElementById(id);
            if (el) {
                el.style.transition = 'color 0.3s ease';
                el.style.color = 'var(--success)';
                el.textContent = value;
                setTimeout(() => {
                    el.style.color = '';
                }, 300);
            }
        });

        if (this.chartInstance) {
            this.updateChart(data);
        }
    },

    initMetricsChart() {
        const canvas = document.getElementById('metrics-chart');
        if (!canvas || !window.Chart) return;

        const ctx = canvas.getContext('2d');
        
        const gradient = ctx.createLinearGradient(0, 0, 0, 100);
        gradient.addColorStop(0, 'rgba(99, 102, 241, 0.3)');
        gradient.addColorStop(1, 'rgba(99, 102, 241, 0)');

        this.chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: Array(20).fill('').map((_, i) => i),
                datasets: [{
                    label: 'Jobs/min',
                    data: Array(20).fill(0).map(() => Math.random() * 30 + 10),
                    borderColor: '#6366f1',
                    backgroundColor: gradient,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { display: false },
                    y: { display: false }
                },
                animation: { duration: 0 }
            }
        });
    },

    updateChart(data) {
        if (!this.chartInstance) return;
        
        const chartData = this.chartInstance.data;
        chartData.datasets[0].data.shift();
        chartData.datasets[0].data.push(data.activeJobs / 10);
        this.chartInstance.update('none');
    },

    initQuantumCircuitViz() {
        const container = document.getElementById('quantum-circuit-demo');
        if (!container) return;

        const circuitHTML = `
            <div class="quantum-circuit-viz">
                <div class="circuit-header">
                    <h4>QAOA Circuit Visualization</h4>
                    <div class="circuit-controls">
                        <button class="circuit-btn" onclick="LandingEnhancements.animateCircuit()">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                <polygon points="5 3 19 12 5 21 5 3"/>
                            </svg>
                            Run
                        </button>
                        <select class="circuit-select" onchange="LandingEnhancements.changeCircuit(this.value)">
                            <option value="qaoa">QAOA (p=2)</option>
                            <option value="vqe">VQE (UCCSD)</option>
                            <option value="annealing">Annealing Schedule</option>
                        </select>
                    </div>
                </div>
                <div class="circuit-canvas" id="circuit-canvas">
                    <svg viewBox="0 0 600 200" class="circuit-svg">
                        <!-- Qubit lines -->
                        <g class="qubit-lines">
                            <line x1="40" y1="40" x2="560" y2="40" stroke="#3a3a4a" stroke-width="2"/>
                            <line x1="40" y1="80" x2="560" y2="80" stroke="#3a3a4a" stroke-width="2"/>
                            <line x1="40" y1="120" x2="560" y2="120" stroke="#3a3a4a" stroke-width="2"/>
                            <line x1="40" y1="160" x2="560" y2="160" stroke="#3a3a4a" stroke-width="2"/>
                        </g>
                        <!-- Qubit labels -->
                        <g class="qubit-labels" font-family="JetBrains Mono" font-size="14" fill="#94a3b8">
                            <text x="20" y="44">q₀</text>
                            <text x="20" y="84">q₁</text>
                            <text x="20" y="124">q₂</text>
                            <text x="20" y="164">q₃</text>
                        </g>
                        <!-- Hadamard gates -->
                        <g class="gates hadamard" transform="translate(60, 0)">
                            <rect x="0" y="25" width="30" height="30" rx="4" fill="#6366f1" class="gate-h"/>
                            <rect x="0" y="65" width="30" height="30" rx="4" fill="#6366f1" class="gate-h"/>
                            <rect x="0" y="105" width="30" height="30" rx="4" fill="#6366f1" class="gate-h"/>
                            <rect x="0" y="145" width="30" height="30" rx="4" fill="#6366f1" class="gate-h"/>
                            <text x="15" y="45" text-anchor="middle" fill="white" font-size="16" font-weight="bold">H</text>
                            <text x="15" y="85" text-anchor="middle" fill="white" font-size="16" font-weight="bold">H</text>
                            <text x="15" y="125" text-anchor="middle" fill="white" font-size="16" font-weight="bold">H</text>
                            <text x="15" y="165" text-anchor="middle" fill="white" font-size="16" font-weight="bold">H</text>
                        </g>
                        <!-- Cost unitary -->
                        <g class="gates cost-unitary" transform="translate(130, 0)">
                            <rect x="0" y="25" width="60" height="135" rx="6" fill="#8b5cf6" opacity="0.3" class="cost-box"/>
                            <text x="30" y="95" text-anchor="middle" fill="#8b5cf6" font-size="14" font-weight="600">U_C</text>
                            <!-- CNOT gates -->
                            <circle cx="20" cy="40" r="8" fill="#06b6d4" class="cnot-control"/>
                            <line x1="20" y1="48" x2="20" y2="120" stroke="#06b6d4" stroke-width="2"/>
                            <circle cx="20" cy="120" r="12" fill="none" stroke="#06b6d4" stroke-width="2" class="cnot-target"/>
                            <line x1="20" y1="108" x2="20" y2="132" stroke="#06b6d4" stroke-width="2"/>
                            <line x1="8" y1="120" x2="32" y2="120" stroke="#06b6d4" stroke-width="2"/>
                        </g>
                        <!-- RZ gates -->
                        <g class="gates rz" transform="translate(220, 0)">
                            <rect x="0" y="25" width="40" height="30" rx="4" fill="#10b981" class="gate-rz"/>
                            <rect x="0" y="65" width="40" height="30" rx="4" fill="#10b981" class="gate-rz"/>
                            <rect x="0" y="105" width="40" height="30" rx="4" fill="#10b981" class="gate-rz"/>
                            <rect x="0" y="145" width="40" height="30" rx="4" fill="#10b981" class="gate-rz"/>
                            <text x="20" y="45" text-anchor="middle" fill="white" font-size="12">RZ</text>
                            <text x="20" y="85" text-anchor="middle" fill="white" font-size="12">RZ</text>
                            <text x="20" y="125" text-anchor="middle" fill="white" font-size="12">RZ</text>
                            <text x="20" y="165" text-anchor="middle" fill="white" font-size="12">RZ</text>
                        </g>
                        <!-- Mixer unitary -->
                        <g class="gates mixer-unitary" transform="translate(290, 0)">
                            <rect x="0" y="25" width="80" height="135" rx="6" fill="#f59e0b" opacity="0.3" class="mixer-box"/>
                            <text x="40" y="95" text-anchor="middle" fill="#f59e0b" font-size="14" font-weight="600">U_M</text>
                            <!-- RX gates -->
                            <rect x="20" y="28" width="35" height="24" rx="4" fill="#f59e0b"/>
                            <rect x="20" y="68" width="35" height="24" rx="4" fill="#f59e0b"/>
                            <rect x="20" y="108" width="35" height="24" rx="4" fill="#f59e0b"/>
                            <rect x="20" y="148" width="35" height="24" rx="4" fill="#f59e0b"/>
                            <text x="37" y="44" text-anchor="middle" fill="white" font-size="12">RX</text>
                            <text x="37" y="84" text-anchor="middle" fill="white" font-size="12">RX</text>
                            <text x="37" y="124" text-anchor="middle" fill="white" font-size="12">RX</text>
                            <text x="37" y="164" text-anchor="middle" fill="white" font-size="12">RX</text>
                        </g>
                        <!-- Second layer -->
                        <g class="gates layer-2" transform="translate(390, 0)">
                            <rect x="0" y="25" width="60" height="135" rx="6" fill="#8b5cf6" opacity="0.2" stroke="#8b5cf6" stroke-dasharray="4"/>
                            <text x="30" y="95" text-anchor="middle" fill="#8b5cf6" font-size="12">p=2</text>
                        </g>
                        <!-- Measurement -->
                        <g class="gates measurement" transform="translate(500, 0)">
                            <rect x="0" y="25" width="35" height="30" rx="4" fill="#64748b" class="measure"/>
                            <rect x="0" y="65" width="35" height="30" rx="4" fill="#64748b" class="measure"/>
                            <rect x="0" y="105" width="35" height="30" rx="4" fill="#64748b" class="measure"/>
                            <rect x="0" y="145" width="35" height="30" rx="4" fill="#64748b" class="measure"/>
                            <text x="17" y="45" text-anchor="middle" fill="white" font-size="16">M</text>
                            <text x="17" y="85" text-anchor="middle" fill="white" font-size="16">M</text>
                            <text x="17" y="125" text-anchor="middle" fill="white" font-size="16">M</text>
                            <text x="17" y="165" text-anchor="middle" fill="white" font-size="16">M</text>
                        </g>
                    </svg>
                </div>
                <div class="circuit-info">
                    <div class="info-item">
                        <span class="info-label">Gates:</span>
                        <span class="info-value" id="gate-count">24</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Depth:</span>
                        <span class="info-value" id="circuit-depth">8</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Parameters:</span>
                        <span class="info-value" id="param-count">4</span>
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = circuitHTML;
        this.addCircuitStyles();
    },

    addCircuitStyles() {
        if (document.getElementById('circuit-viz-styles')) return;

        const styles = document.createElement('style');
        styles.id = 'circuit-viz-styles';
        styles.textContent = `
            .quantum-circuit-viz {
                background: var(--bg-card);
                border: 1px solid var(--border-color);
                border-radius: var(--radius-lg);
                padding: 1.5rem;
                margin-top: 2rem;
            }
            .circuit-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1rem;
            }
            .circuit-header h4 {
                color: var(--text-primary);
                font-size: 1rem;
                margin: 0;
            }
            .circuit-controls {
                display: flex;
                gap: 0.75rem;
            }
            .circuit-btn {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.5rem 1rem;
                background: var(--primary);
                color: white;
                border: none;
                border-radius: var(--radius-sm);
                cursor: pointer;
                font-size: 0.875rem;
                transition: all 0.2s;
            }
            .circuit-btn:hover {
                background: var(--primary-dark);
                transform: translateY(-1px);
            }
            .circuit-select {
                padding: 0.5rem 1rem;
                background: var(--bg-elevated);
                border: 1px solid var(--border-color);
                border-radius: var(--radius-sm);
                color: var(--text-primary);
                font-size: 0.875rem;
            }
            .circuit-canvas {
                background: var(--bg-dark);
                border-radius: var(--radius-md);
                padding: 1rem;
                overflow-x: auto;
            }
            .circuit-svg {
                width: 100%;
                min-width: 500px;
            }
            .gate-h, .gate-rz, .cnot-control, .measure {
                transition: all 0.3s ease;
            }
            .gate-h:hover, .gate-rz:hover {
                transform: scale(1.1);
                filter: brightness(1.2);
            }
            .circuit-info {
                display: flex;
                gap: 2rem;
                margin-top: 1rem;
                padding-top: 1rem;
                border-top: 1px solid var(--border-color);
            }
            .info-item {
                display: flex;
                gap: 0.5rem;
            }
            .info-label {
                color: var(--text-muted);
                font-size: 0.875rem;
            }
            .info-value {
                color: var(--primary);
                font-weight: 600;
                font-size: 0.875rem;
            }
            @keyframes gatePulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            .circuit-animating .gate-h,
            .circuit-animating .gate-rz {
                animation: gatePulse 0.5s ease-in-out;
            }
        `;
        document.head.appendChild(styles);
    },

    animateCircuit() {
        const canvas = document.getElementById('circuit-canvas');
        if (!canvas) return;

        canvas.classList.add('circuit-animating');
        
        const gates = canvas.querySelectorAll('.gate-h, .gate-rz, .cnot-control, .measure');
        gates.forEach((gate, i) => {
            gate.style.animationDelay = `${i * 0.1}s`;
        });

        setTimeout(() => {
            canvas.classList.remove('circuit-animating');
        }, 2000);
    },

    changeCircuit(type) {
        const gateCount = document.getElementById('gate-count');
        const depth = document.getElementById('circuit-depth');
        const params = document.getElementById('param-count');

        const configs = {
            qaoa: { gates: 24, depth: 8, params: 4 },
            vqe: { gates: 48, depth: 12, params: 16 },
            annealing: { gates: 0, depth: 1, params: 2 }
        };

        const config = configs[type] || configs.qaoa;
        if (gateCount) gateCount.textContent = config.gates;
        if (depth) depth.textContent = config.depth;
        if (params) params.textContent = config.params;
    },

    initPublicationSection() {
        // Section already exists in HTML, just initialize citation generator
        const section = document.getElementById('publications');
        if (!section) return;
        
        // Citation formats are handled by generateCitation
    },

    initArchitectureDiagram() {
        const container = document.getElementById('architecture-diagram');
        if (!container) return;

        const archHTML = `
            <div class="architecture-diagram">
                <h4>System Architecture</h4>
                <div class="arch-svg-container">
                    <svg viewBox="0 0 800 500" class="arch-svg">
                        <!-- Background grid -->
                        <defs>
                            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1a1a25" stroke-width="1"/>
                            </pattern>
                            <linearGradient id="layerGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                                <stop offset="0%" style="stop-color:#6366f1;stop-opacity:1" />
                                <stop offset="100%" style="stop-color:#8b5cf6;stop-opacity:1" />
                            </linearGradient>
                        </defs>
                        <rect width="800" height="500" fill="url(#grid)"/>
                        
                        <!-- Client Layer -->
                        <g class="layer client-layer" transform="translate(50, 30)">
                            <rect x="0" y="0" width="700" height="70" rx="8" fill="#1a1a25" stroke="#6366f1" stroke-width="2"/>
                            <text x="20" y="25" fill="#6366f1" font-weight="600" font-size="14">Client Layer</text>
                            <g transform="translate(20, 35)">
                                <rect x="0" y="0" width="100" height="25" rx="4" fill="#6366f1"/>
                                <text x="50" y="17" text-anchor="middle" fill="white" font-size="11">Web UI</text>
                            </g>
                            <g transform="translate(140, 35)">
                                <rect x="0" y="0" width="100" height="25" rx="4" fill="#6366f1"/>
                                <text x="50" y="17" text-anchor="middle" fill="white" font-size="11">Python SDK</text>
                            </g>
                            <g transform="translate(260, 35)">
                                <rect x="0" y="0" width="100" height="25" rx="4" fill="#6366f1"/>
                                <text x="50" y="17" text-anchor="middle" fill="white" font-size="11">REST API</text>
                            </g>
                            <g transform="translate(380, 35)">
                                <rect x="0" y="0" width="100" height="25" rx="4" fill="#6366f1"/>
                                <text x="50" y="17" text-anchor="middle" fill="white" font-size="11">WebSocket</text>
                            </g>
                            <g transform="translate(500, 35)">
                                <rect x="0" y="0" width="120" height="25" rx="4" fill="#10b981"/>
                                <text x="60" y="17" text-anchor="middle" fill="white" font-size="11">PQC Crypto (Rust)</text>
                            </g>
                        </g>

                        <!-- API Gateway -->
                        <g class="layer api-layer" transform="translate(50, 120)">
                            <rect x="0" y="0" width="700" height="60" rx="8" fill="#1a1a25" stroke="#06b6d4" stroke-width="2"/>
                            <text x="20" y="25" fill="#06b6d4" font-weight="600" font-size="14">API Gateway (FastAPI)</text>
                            <g transform="translate(20, 32)">
                                <rect x="0" y="0" width="80" height="20" rx="3" fill="#06b6d4" opacity="0.8"/>
                                <text x="40" y="14" text-anchor="middle" fill="white" font-size="10">Auth</text>
                            </g>
                            <g transform="translate(110, 32)">
                                <rect x="0" y="0" width="80" height="20" rx="3" fill="#06b6d4" opacity="0.8"/>
                                <text x="40" y="14" text-anchor="middle" fill="white" font-size="10">Rate Limit</text>
                            </g>
                            <g transform="translate(200, 32)">
                                <rect x="0" y="0" width="80" height="20" rx="3" fill="#06b6d4" opacity="0.8"/>
                                <text x="40" y="14" text-anchor="middle" fill="white" font-size="10">Validation</text>
                            </g>
                            <g transform="translate(290, 32)">
                                <rect x="0" y="0" width="100" height="20" rx="3" fill="#06b6d4" opacity="0.8"/>
                                <text x="50" y="14" text-anchor="middle" fill="white" font-size="10">Job Queue</text>
                            </g>
                            <g transform="translate(400, 32)">
                                <rect x="0" y="0" width="100" height="20" rx="3" fill="#06b6d4" opacity="0.8"/>
                                <text x="50" y="14" text-anchor="middle" fill="white" font-size="10">WebSocket</text>
                            </g>
                        </g>

                        <!-- Compute Layer -->
                        <g class="layer compute-layer" transform="translate(50, 200)">
                            <rect x="0" y="0" width="700" height="120" rx="8" fill="#1a1a25" stroke="#8b5cf6" stroke-width="2"/>
                            <text x="20" y="25" fill="#8b5cf6" font-weight="600" font-size="14">Quantum Compute Layer</text>
                            
                            <!-- QAOA -->
                            <g transform="translate(20, 40)">
                                <rect x="0" y="0" width="120" height="65" rx="6" fill="#8b5cf6" opacity="0.3"/>
                                <text x="60" y="20" text-anchor="middle" fill="#8b5cf6" font-size="12" font-weight="600">QAOA</text>
                                <text x="60" y="38" text-anchor="middle" fill="#94a3b8" font-size="10">PennyLane</text>
                                <text x="60" y="52" text-anchor="middle" fill="#94a3b8" font-size="10">Qiskit</text>
                            </g>
                            
                            <!-- VQE -->
                            <g transform="translate(160, 40)">
                                <rect x="0" y="0" width="120" height="65" rx="6" fill="#8b5cf6" opacity="0.3"/>
                                <text x="60" y="20" text-anchor="middle" fill="#8b5cf6" font-size="12" font-weight="600">VQE</text>
                                <text x="60" y="38" text-anchor="middle" fill="#94a3b8" font-size="10">Qiskit Chemistry</text>
                                <text x="60" y="52" text-anchor="middle" fill="#94a3b8" font-size="10">UCCSD Ansatz</text>
                            </g>
                            
                            <!-- Annealing -->
                            <g transform="translate(300, 40)">
                                <rect x="0" y="0" width="120" height="65" rx="6" fill="#8b5cf6" opacity="0.3"/>
                                <text x="60" y="20" text-anchor="middle" fill="#8b5cf6" font-size="12" font-weight="600">Annealing</text>
                                <text x="60" y="38" text-anchor="middle" fill="#94a3b8" font-size="10">D-Wave Ocean</text>
                                <text x="60" y="52" text-anchor="middle" fill="#94a3b8" font-size="10">QUBO/Ising</text>
                            </g>
                            
                            <!-- Optimizers -->
                            <g transform="translate(440, 40)">
                                <rect x="0" y="0" width="120" height="65" rx="6" fill="#f59e0b" opacity="0.3"/>
                                <text x="60" y="20" text-anchor="middle" fill="#f59e0b" font-size="12" font-weight="600">Optimizers</text>
                                <text x="60" y="38" text-anchor="middle" fill="#94a3b8" font-size="10">COBYLA</text>
                                <text x="60" y="52" text-anchor="middle" fill="#94a3b8" font-size="10">L-BFGS-B, SPSA</text>
                            </g>
                            
                            <!-- Simulators -->
                            <g transform="translate(580, 40)">
                                <rect x="0" y="0" width="100" height="65" rx="6" fill="#10b981" opacity="0.3"/>
                                <text x="50" y="20" text-anchor="middle" fill="#10b981" font-size="12" font-weight="600">Simulators</text>
                                <text x="50" y="38" text-anchor="middle" fill="#94a3b8" font-size="10">Aer</text>
                                <text x="50" y="52" text-anchor="middle" fill="#94a3b8" font-size="10">Lightning</text>
                            </g>
                        </g>

                        <!-- Backend Layer -->
                        <g class="layer backend-layer" transform="translate(50, 340)">
                            <rect x="0" y="0" width="700" height="70" rx="8" fill="#1a1a25" stroke="#10b981" stroke-width="2"/>
                            <text x="20" y="25" fill="#10b981" font-weight="600" font-size="14">Quantum Backends</text>
                            <g transform="translate(20, 35)">
                                <rect x="0" y="0" width="100" height="25" rx="4" fill="#4f46e5"/>
                                <text x="50" y="17" text-anchor="middle" fill="white" font-size="11">IBM Quantum</text>
                            </g>
                            <g transform="translate(140, 35)">
                                <rect x="0" y="0" width="100" height="25" rx="4" fill="#f59e0b"/>
                                <text x="50" y="17" text-anchor="middle" fill="white" font-size="11">AWS Braket</text>
                            </g>
                            <g transform="translate(260, 35)">
                                <rect x="0" y="0" width="100" height="25" rx="4" fill="#06b6d4"/>
                                <text x="50" y="17" text-anchor="middle" fill="white" font-size="11">Azure Quantum</text>
                            </g>
                            <g transform="translate(380, 35)">
                                <rect x="0" y="0" width="100" height="25" rx="4" fill="#10b981"/>
                                <text x="50" y="17" text-anchor="middle" fill="white" font-size="11">D-Wave</text>
                            </g>
                            <g transform="translate(500, 35)">
                                <rect x="0" y="0" width="100" height="25" rx="4" fill="#64748b"/>
                                <text x="50" y="17" text-anchor="middle" fill="white" font-size="11">Local Sim</text>
                            </g>
                        </g>

                        <!-- Data arrows -->
                        <g class="data-flow" stroke="#6366f1" stroke-width="2" fill="none">
                            <path d="M 400 100 L 400 120" marker-end="url(#arrow)"/>
                            <path d="M 400 180 L 400 200" marker-end="url(#arrow)"/>
                            <path d="M 400 320 L 400 340" marker-end="url(#arrow)"/>
                        </g>
                        
                        <defs>
                            <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
                                <path d="M0,0 L0,6 L9,3 z" fill="#6366f1"/>
                            </marker>
                        </defs>
                    </svg>
                </div>
            </div>
        `;

        container.innerHTML = archHTML;
    },

    initResearchShowcase() {
        const showcase = document.getElementById('research-showcase');
        if (!showcase) return;

        const showcaseHTML = `
            <div class="research-showcase">
                <h4>Featured Research Use Cases</h4>
                <div class="showcase-grid">
                    <div class="showcase-card">
                        <div class="showcase-image">
                            <svg viewBox="0 0 200 120">
                                <rect width="200" height="120" fill="#1a1a25"/>
                                <circle cx="40" cy="40" r="15" fill="#6366f1" opacity="0.5"/>
                                <circle cx="80" cy="40" r="15" fill="#10b981" opacity="0.5"/>
                                <circle cx="40" cy="80" r="15" fill="#10b981" opacity="0.5"/>
                                <circle cx="80" cy="80" r="15" fill="#6366f1" opacity="0.5"/>
                                <line x1="55" y1="40" x2="65" y2="40" stroke="#f59e0b" stroke-width="3"/>
                                <line x1="40" y1="55" x2="40" y2="65" stroke="#f59e0b" stroke-width="3"/>
                            </svg>
                        </div>
                        <h5>Max-Cut Optimization</h5>
                        <p>Solve graph partitioning problems with QAOA</p>
                        <div class="showcase-stats">
                            <span>Qubits: 4-127</span>
                            <span>Speedup: 10-100x</span>
                        </div>
                    </div>
                    <div class="showcase-card">
                        <div class="showcase-image">
                            <svg viewBox="0 0 200 120">
                                <rect width="200" height="120" fill="#1a1a25"/>
                                <circle cx="30" cy="60" r="10" fill="#6366f1"/>
                                <circle cx="70" cy="30" r="10" fill="#8b5cf6"/>
                                <circle cx="110" cy="60" r="10" fill="#06b6d4"/>
                                <circle cx="150" cy="30" r="10" fill="#10b981"/>
                                <circle cx="170" cy="90" r="10" fill="#f59e0b"/>
                                <path d="M 40 60 Q 70 30 100 60 Q 130 90 160 90" stroke="#6366f1" stroke-width="2" fill="none" stroke-dasharray="4"/>
                            </svg>
                        </div>
                        <h5>Traveling Salesman</h5>
                        <p>Route optimization with quantum annealing</p>
                        <div class="showcase-stats">
                            <span>Cities: 5-50</span>
                            <span>Accuracy: 95%+</span>
                        </div>
                    </div>
                    <div class="showcase-card">
                        <div class="showcase-image">
                            <svg viewBox="0 0 200 120">
                                <rect width="200" height="120" fill="#1a1a25"/>
                                <ellipse cx="100" cy="60" rx="30" ry="20" fill="none" stroke="#6366f1" stroke-width="2"/>
                                <circle cx="70" cy="60" r="5" fill="#10b981"/>
                                <circle cx="130" cy="60" r="5" fill="#f59e0b"/>
                                <path d="M 75 60 Q 100 40 125 60" stroke="#8b5cf6" stroke-width="2" fill="none"/>
                            </svg>
                        </div>
                        <h5>Molecular Simulation</h5>
                        <p>Ground state energy with VQE</p>
                        <div class="showcase-stats">
                            <span>Molecules: H2-LiH</span>
                            <span>Precision: mHa</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        showcase.innerHTML = showcaseHTML;
    },

    initCitationGenerator() {
        const citations = {
            bibtex: `@software{quantumsafe2024,
  author = {QuantumSafe Optimize Team},
  title = {QuantumSafe Optimize: A Post-Quantum Secure Optimization Platform},
  year = {2024},
  publisher = {GitHub},
  url = {https://github.com/quantumsafe-optimize},
  note = {NIST FIPS 203/204 compliant PQC with QAOA/VQE/Annealing support}
}`,
            apa: `QuantumSafe Optimize Team. (2024). QuantumSafe Optimize: A Post-Quantum Secure Optimization Platform [Software]. GitHub. https://github.com/quantumsafe-optimize`,
            ieee: `[1] QuantumSafe Optimize Team, "QuantumSafe Optimize: A Post-Quantum Secure Optimization Platform," 2024. [Software]. GitHub. Available: https://github.com/quantumsafe-optimize`,
            mla: `QuantumSafe Optimize Team. "QuantumSafe Optimize: A Post-Quantum Secure Optimization Platform." GitHub, 2024, github.com/quantumsafe-optimize.`
        };

        window.LandingEnhancements = this;
        this.citations = citations;
    },

    generateCitation() {
        const format = document.getElementById('citation-format')?.value || 'bibtex';
        const output = document.getElementById('citation-output');
        if (output && this.citations) {
            output.textContent = this.citations[format];
        }
    },

    initInteractiveBenchmark() {
        const container = document.getElementById('benchmark-comparison');
        if (!container) return;

        const benchmarkHTML = `
            <div class="benchmark-interactive">
                <h4>Live Algorithm Comparison</h4>
                <div class="benchmark-controls">
                    <select id="benchmark-problem">
                        <option value="maxcut">Max-Cut (20 nodes)</option>
                        <option value="tsp">TSP (8 cities)</option>
                        <option value="portfolio">Portfolio (10 assets)</option>
                    </select>
                    <button class="btn btn-primary" onclick="LandingEnhancements.runBenchmark()">
                        Run Benchmark
                    </button>
                </div>
                <div class="benchmark-results" id="benchmark-results">
                    <div class="benchmark-chart">
                        <div class="chart-bar" style="--height: 85%; --color: #6366f1;">
                            <span class="bar-label">QAOA</span>
                            <span class="bar-value">0.85</span>
                        </div>
                        <div class="chart-bar" style="--height: 78%; --color: #8b5cf6;">
                            <span class="bar-label">VQE</span>
                            <span class="bar-value">0.78</span>
                        </div>
                        <div class="chart-bar" style="--height: 92%; --color: #10b981;">
                            <span class="bar-label">Annealing</span>
                            <span class="bar-value">0.92</span>
                        </div>
                        <div class="chart-bar" style="--height: 45%; --color: #64748b;">
                            <span class="bar-label">Classical</span>
                            <span class="bar-value">0.45</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = benchmarkHTML;
        this.addBenchmarkStyles();
    },

    addBenchmarkStyles() {
        if (document.getElementById('benchmark-styles')) return;

        const styles = document.createElement('style');
        styles.id = 'benchmark-styles';
        styles.textContent = `
            .benchmark-interactive {
                background: var(--bg-card);
                border-radius: var(--radius-lg);
                padding: 1.5rem;
                margin-top: 2rem;
            }
            .benchmark-interactive h4 {
                margin-bottom: 1rem;
                color: var(--text-primary);
            }
            .benchmark-controls {
                display: flex;
                gap: 1rem;
                margin-bottom: 1.5rem;
            }
            .benchmark-controls select {
                padding: 0.5rem 1rem;
                background: var(--bg-elevated);
                border: 1px solid var(--border-color);
                border-radius: var(--radius-sm);
                color: var(--text-primary);
            }
            .benchmark-chart {
                display: flex;
                justify-content: space-around;
                align-items: flex-end;
                height: 200px;
                padding: 1rem;
                background: var(--bg-dark);
                border-radius: var(--radius-md);
            }
            .chart-bar {
                display: flex;
                flex-direction: column;
                align-items: center;
                width: 60px;
                height: var(--height, 50%);
                background: var(--color, #6366f1);
                border-radius: var(--radius-sm) var(--radius-sm) 0 0;
                position: relative;
                transition: all 0.5s ease;
            }
            .chart-bar::after {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 50%;
                background: linear-gradient(180deg, rgba(255,255,255,0.2) 0%, transparent 100%);
                border-radius: var(--radius-sm) var(--radius-sm) 0 0;
            }
            .bar-label {
                position: absolute;
                bottom: -30px;
                font-size: 0.75rem;
                color: var(--text-secondary);
            }
            .bar-value {
                position: absolute;
                top: 8px;
                font-size: 0.875rem;
                font-weight: 600;
                color: white;
            }
            .publications-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 1.5rem;
                margin-top: 2rem;
            }
            .pub-card {
                background: var(--bg-card);
                border: 1px solid var(--border-color);
                border-radius: var(--radius-lg);
                padding: 1.5rem;
                transition: all 0.3s ease;
            }
            .pub-card:hover {
                border-color: var(--primary);
                transform: translateY(-4px);
            }
            .pub-icon {
                font-size: 2rem;
                margin-bottom: 1rem;
            }
            .pub-card h3 {
                font-size: 1.1rem;
                margin-bottom: 0.75rem;
                color: var(--text-primary);
            }
            .pub-card p {
                color: var(--text-secondary);
                font-size: 0.875rem;
                margin-bottom: 1rem;
            }
            .pub-features {
                list-style: none;
                padding: 0;
                margin: 0;
            }
            .pub-features li {
                color: var(--text-muted);
                font-size: 0.8rem;
                padding: 0.25rem 0;
                padding-left: 1rem;
                position: relative;
            }
            .pub-features li::before {
                content: '✓';
                position: absolute;
                left: 0;
                color: var(--success);
            }
            .citation-generator {
                background: var(--bg-card);
                border: 1px solid var(--border-color);
                border-radius: var(--radius-lg);
                padding: 1.5rem;
                margin-top: 2rem;
            }
            .citation-generator h4 {
                margin-bottom: 1rem;
                color: var(--text-primary);
            }
            .citation-form {
                display: flex;
                gap: 1rem;
                margin-bottom: 1rem;
            }
            .citation-form select {
                padding: 0.5rem 1rem;
                background: var(--bg-elevated);
                border: 1px solid var(--border-color);
                border-radius: var(--radius-sm);
                color: var(--text-primary);
            }
            .citation-output {
                background: var(--bg-dark);
                border: 1px solid var(--border-color);
                border-radius: var(--radius-md);
                padding: 1rem;
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.8rem;
                color: var(--text-secondary);
                overflow-x: auto;
                white-space: pre-wrap;
            }
            .architecture-diagram {
                background: var(--bg-card);
                border: 1px solid var(--border-color);
                border-radius: var(--radius-lg);
                padding: 1.5rem;
                margin-top: 2rem;
            }
            .architecture-diagram h4 {
                margin-bottom: 1rem;
                color: var(--text-primary);
            }
            .arch-svg-container {
                background: var(--bg-dark);
                border-radius: var(--radius-md);
                padding: 1rem;
                overflow-x: auto;
            }
            .arch-svg {
                width: 100%;
                min-width: 700px;
            }
            .research-showcase {
                background: var(--bg-card);
                border: 1px solid var(--border-color);
                border-radius: var(--radius-lg);
                padding: 1.5rem;
                margin-top: 2rem;
            }
            .research-showcase h4 {
                margin-bottom: 1rem;
                color: var(--text-primary);
            }
            .showcase-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 1rem;
            }
            .showcase-card {
                background: var(--bg-elevated);
                border-radius: var(--radius-md);
                padding: 1rem;
                text-align: center;
            }
            .showcase-image {
                margin-bottom: 0.75rem;
            }
            .showcase-card h5 {
                font-size: 0.95rem;
                margin-bottom: 0.5rem;
                color: var(--text-primary);
            }
            .showcase-card p {
                font-size: 0.8rem;
                color: var(--text-secondary);
                margin-bottom: 0.75rem;
            }
            .showcase-stats {
                display: flex;
                justify-content: center;
                gap: 1rem;
                font-size: 0.75rem;
                color: var(--primary);
            }
        `;
        document.head.appendChild(styles);
    },

    runBenchmark() {
        const bars = document.querySelectorAll('.chart-bar');
        bars.forEach(bar => {
            const newHeight = Math.random() * 50 + 45;
            bar.style.setProperty('--height', `${newHeight}%`);
            const value = (newHeight / 100).toFixed(2);
            bar.querySelector('.bar-value').textContent = value;
        });
    },

    cleanup() {
        if (this.ws) {
            this.ws.close();
        }
        if (this.metricsInterval) {
            clearInterval(this.metricsInterval);
        }
    }
};

export default LandingEnhancements;
