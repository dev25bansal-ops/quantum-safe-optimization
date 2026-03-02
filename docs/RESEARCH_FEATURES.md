# Research Features for QSOP

## Overview

This module provides publication-ready research features for the Quantum-Safe Secure Optimization Platform (QSOP), enabling academic publication with full reproducibility and detailed analytics.

## Key Features

### 1. Deterministic Random Seed Support

All optimization algorithms now support deterministic execution via `random_seed` parameter:

```python
from qsop.application.workflows.qaoa import QAOAWorkflow, QAOAWorkflowConfig
from qsop.application.workflows.vqe import VQEWorkflow, VQEWorkflowConfig
from qsop.optimizers.classical.simulated_annealing import SimulatedAnnealing, SimulatedAnnealingConfig

# QAOA with deterministic seed
qaoa_config = QAOAWorkflowConfig(
    p_layers=2,
    shots=1024,
    random_seed=42  # Ensures reproducibility
)
qaoa_workflow = QAOAWorkflow(config=qaoa_config)

# VQE with deterministic seed
vqe_config = VQEWorkflowConfig(
    ansatz_type="hardware_efficient",
    ansatz_layers=2,
    shots=1024,
    random_seed=42
)
vqe_workflow = VQEWorkflow(config=vqe_config)

# Simulated Annealing with deterministic seed
sa_config = SimulatedAnnealingConfig(
    max_iterations=1000,
    random_seed=42
)
sa_optimizer = SimulatedAnnealing(config=sa_config)
```

**Seeding Applied To:**
- `numpy.random` - All numpy random operations
- `qiskit.qi.random` - Qiskit quantum random operations
- `scipy.optimize` - Classical optimization (where supported)

### 2. Quantum Circuit Visualization

Get SVG circuit diagrams with detailed statistics:

```bash
GET /analytics/projects/{project_id}/circuit?algorithm=qaoa&p_layers=2
```

**Response:**
```json
{
  "circuit_svg": "<svg>...</svg>",
  "depth": 15,
  "gate_counts": {
    "h": 5,
    "cx": 8,
    "rz": 10,
    "rx": 5,
    "measure": 5
  },
  "qubit_count": 5,
  "connectivity": [[0,1], [1,2], [2,3], [3,4]]
}
```

### 3. Research Data Export

Export job results in multiple formats for reproducibility:

**JSON Export (full metadata):**
```bash
GET /analytics/jobs/{job_id}/export?format=json
```

```json
{
  "job_id": "...",
  "tenant_id": "...",
  "algorithm": "qaoa",
  "backend": "qiskit_aer",
  "parameters": {
    "p_layers": 2,
    "random_seed": 42
  },
  "results": {
    "optimal_value": -10.5,
    "optimal_parameters": {"gamma_0": 0.5, "beta_0": 0.25},
    "iterations": 100,
    "objective_history": [-9.0, -9.5, -10.0, -10.5]
  },
  "reproducibility": {
    "version": "1.0.0",
    "random_seed": 42,
    "platform": "research_ready"
  }
}
```

**CSV Export (convergence data):**
```bash
GET /analytics/jobs/{job_id}/export?format=csv
```

```csv
job_id,algorithm,iteration,objective_value,parameters,timestamp_ms,wall_time_seconds
550e8400-e29b-41d4-a716-446655440000,qaoa,0,-9.0,{\"gamma\":0.5},0,5.0
550e8400-e29b-41d4-a716-446655440000,qaoa,1,-9.5,{\"gamma\":0.55},100,5.0
...
```

### 4. Benchmark Comparison Dashboard

Compare multiple algorithms side-by-side using Plotly.js:

```bash
POST /analytics/benchmark/compare
```

**Request:**
```json
{
  "algorithms": ["qaoa", "vqe", "ga", "sa"],
  "problem_id": null,
  "problem_config": {
    "type": "maxcut",
    "n_nodes": 10,
    "edges": [[0,1], [1,2], [2,3]]
  },
  "metrics": ["optimal_value", "iterations", "convergence_rate"],
  "p_layers_range": [1, 3]
}
```

**Response:**
```json
{
  "results": [
    {
      "algorithm": "qaoa",
      "p_layers": 1,
      "optimizer": "COBYLA",
      "optimal_value": -10.5,
      "iterations": 50,
      "convergence_rate": 0.95,
      "execution_time_ms": 500,
      "memory_usage_mb": 128
    }
  ],
  "summary": {
    "mean_optimal_value": -9.8,
    "best_algorithm": "qaoa",
    "total_benchmarks": 18
  }
}
```

**Visualizations:**
- Convergence curves (algorithm vs iterations)
- Solution quality vs problem size
- Side-by-side multi-metric comparison
- Interactive plots with pan/zoom

### 5. Ablation Study Infrastructure

Run systematic hyperparameter sensitivity analysis:

```bash
POST /analytics/benchmark/run-ablation
```

**Request:**
```json
{
  "algorithm": "qaoa",
  "p_layers_range": [1, 10],
  "optimizers": ["COBYLA", "SPSA", "ADAM"],
  "shots_list": [1024, 2048],
  "repetitions": 3,
  "random_seed": 42
}
```

**Features:**
- Grid search over p-layers (1-10)
- Multiple optimizer comparison
- Shot number sweeps
- Multiple repetitions with different seeds
- Automated statistical analysis

**Visualization:**
- Heat maps: p-layers vs optimizer
- Sensitivity analysis plots
- Standard deviation charts
- Correlation matrices

### 6. Research API Endpoints

**Get Research Metrics:**
```bash
GET /analytics/research/metrics?days=30&algorithm=qaoa
```

```json
{
  "total_jobs_run": 150,
  "completed_jobs": 135,
  "average_convergence_rate": 0.87,
  "algorithms_used": ["qaoa", "vqe", "ga", "sa"],
  "performance_summary": {
    "qaoa": {"avg_iterations": 75, "success_rate": 0.85},
    "vqe": {"avg_iterations": 90, "success_rate": 0.82}
  },
  "reproducibility": {
    "jobs_with_seed": 120,
    "duplicate_runs": 45,
    "correlation_coefficient": 0.98
  }
}
```

**Get Publication Metadata:**
```bash
GET /analytics/research/publication-metadata
```

```json
{
  "software_environment": {
    "name": "QSOP",
    "version": "1.0.0",
    "python_version": "3.11",
    "dependencies": {
      "qiskit": "0.45.0",
      "numpy": "1.24.0",
      "scipy": "1.10.0"
    }
  },
  "algorithms": {
    "qaoa": {
      "reference": "Farhi et al., 2014",
      "description": "Quantum Approximate Optimization Algorithm"
    }
  },
  "bibliography": [
    "@article{farhi2014qaoa,...}",
    "@article{peruzzo2014vqe,...}"
  ]
}
```

## Frontend Integration

Using the research module:

```javascript
import { 
  loadPlotlyJS,
  displayCircuitVisualization,
  exportJobData,
  runBenchmarkComparison,
  createConvergenceChart,
  createAblationHeatmap
} from './frontend/js/modules/research.js';

// Display circuit visualization
await displayCircuitVisualization(
  'circuit-container',
  projectId,
  'qaoa',  // algorithm
  2        // p_layers
);

// Run benchmark comparison
const benchmarkResults = await runBenchmarkComparison(
  ['qaoa', 'vqe', 'ga'],
  null,
  null,
  [1, 3]  // p_layers_range
);

// Create convergence chart
await createConvergenceChart('convergence-chart', benchmarkResults);

// Export data
await exportJobData(jobId, 'json');  // or 'csv'
```

## Demo Dashboard

Access the research dashboard:

```bash
# Open the demo file
open frontend/research-demo.html

# Or serve with a local web server
python -m http.server 8000
# Then visit http://localhost:8000/frontend/research-demo.html
```

## Testing

Run tests for research features:

```bash
pytest tests/unit/test_research_features.py -v
```

## Publication Requirements Met

✅ **Reproducibility**
- Deterministic random seeds
- Full configuration export
- Version tracking
- Environment metadata

✅ **Transparency**
- Circuit visualization
- Detailed convergence data
- Parameter tracking
- Execution timing

✅ **Rigorous Analysis**
- Statistical tests
- Multiple repetitions
- Sensitivity analysis (ablation studies)
- Benchmark comparisons

✅ **Publication Quality**
- High-resolution plots (Plotly.js)
- Exportable figures (SVG/PNG)
- Citation-ready bibliography
- Standardized formats

## Citation

If you use QSOP for your research, please cite:

```bibtex
@software{qsop2024,
  title={Quantum-Safe Secure Optimization Platform},
  author={Your Name},
  year={2024},
  version={1.0.0},
  url={https://github.com/yourusername/qsop}
}
```

## License

Research features are part of the QSOP project. See main LICENSE file for details.
