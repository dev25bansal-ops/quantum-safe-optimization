/**
 * AI-Powered Optimization Suggestions Component
 * Provides intelligent suggestions based on historical job performance
 *
 * Features:
 * - Learns from past job results to suggest optimal parameters
 * - Displays confidence levels for suggestions
 * - Shows reasoning behind each suggestion
 * - Persistent storage of learned patterns
 */

import Component from './Component.js';

export class OptimizationSuggestionCard extends Component {
  constructor(props = {}) {
    super(props);
    
    this.state = {
      isOpen: false,
      suggestionType: '', // 'qaoa', 'vqe', 'annealing'
    };
  }
  
  render() {
    if (!this.state.isOpen) {
      this.element.innerHTML = '';
      return;
    }
    
    const algorithmNames = {
      'qaoa': 'QAOA (Quantum Approximate Optimization Algorithm)',
      'vqe': 'VQE (Variational Quantum Eigensolver)',
      'annealing': 'Quantum Annealing'
    };
    
    this.element.innerHTML = `
      <div class="suggestion-card">
        <div class="suggestion-header">
          <h3>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0 1-2 0l-7 4A2 2 0 0 0 0 17v9a2 2 0 0 0 2 2z"/>
              <circle cx="12" cy="13" r="6"/>
              <line x1="12" y1="9" x2="12" y2="17"/>
            </svg>
            AI-Powered Suggestions
          </h3>
          <span class="algorithm-label">${algorithmNames[this.state.suggestionType]}</span>
        </div>
        <div class="suggestion-body">
          <div class="suggestion-list" id="suggestion-list-${this.state.suggestionType}">
            <div class="loading-state">
              <div class="spinner"></div>
              <p>Analyzing your optimization history...</p>
            </div>
          </div>
        </div>
        <div class="suggestion-footer">
          <button class="btn btn-outline btn-sm" onclick="this.close()">Close</button>
          <button class="btn btn-primary btn-sm" onclick="this.applySuggestion()">Apply Suggestion</button>
        </div>
      </div>
    `;
  }
  
  async fetchSuggestions(algorithm) {
    this.setState({ suggestionType: algorithm, isOpen: true });
    this.render();
    
    const listContainer = this.element.querySelector(`#suggestion-list-${algorithm}`);
    
    try {
      // Fetch from AI suggestions API endpoint
      const response = await fetch(`/api/v1/suggestions/${algorithm}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to fetch suggestions');
      }
      
      const data = await response.json();
      this.renderSuggestions(data.suggestions || [], listContainer);
      
    } catch (error) {
      console.error('Failed to fetch suggestions:', error);
      
      // Show error state
      listContainer.innerHTML = `
        <div class="error-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="16"/>
          </svg>
          <p>Failed to load suggestions</p>
          <button class="btn btn-outline btn-sm" onclick="this.close()">Close</button>
        </div>
      `;
    }
  }
  
  renderSuggestions(suggestions, container) {
    if (suggestions.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9.663 10.22a1 1 0 0 1 0 1.414 1.414 1 1 0 0 0 0-1.414 0m-8.486 9.378a9 9 0 0 1 18 5.072M7.07 6.343a1 1 0 0 0-1.414 1.414 1 1 0 0 0 1.414 0m0-9.9 2.712a9 9 0 0 0 18 5.072"/>
            <line x1="12" y1="2" x2="12" y2="12"/>
          </svg>
          <p>No suggestions available yet</p>
          <p class="empty-hint">Submit more jobs to get AI-powered recommendations</p>
        </div>
      `;
      return;
    }
    
    container.innerHTML = suggestions.map((suggestion, index) => `
      <div class="suggestion-item" data-suggestion-id="${suggestion.id}" style="animation-delay: ${index * 100}ms">
        <div class="suggestion-header">
          <div class="suggestion-title">${suggestion.title}</div>
          <div class="suggestion-confidence">
            <div class="confidence-bar">
              <div class="confidence-fill" style="width: ${suggestion.confidence}%; background-color: ${this.getConfidenceColor(suggestion.confidence)}"></div>
            </div>
            <span class="confidence-value">${suggestion.confidence}% confidence</span>
          </div>
        </div>
        <div class="suggestion-description">${suggestion.description}</div>
        <div class="suggestion-params">
          <h4>Recommended Parameters:</h4>
          <div class="params-grid">
            ${Object.entries(suggestion.parameters).map(([key, value]) => `
              <div class="param-item">
                <span class="param-key">${this.formatParamKey(key)}:</span>
                <span class="param-value">${this.formatParamValue(value)}</span>
              </div>
            `).join('')}
          </div>
        </div>
        <div class="suggestion-actions">
          <button class="btn btn-sm btn-apply" onclick="window.applySuggestion('${suggestion.id}')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            Apply
          </button>
          <button class="btn btn-sm btn-outline" onclick="window.copySuggestion('${suggestion.id}')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2 -2V4a2 2 0 0 1 2 -2h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H4a2 2 0 0 1-2 -2v-4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 2H4a2 2 0 0 1-2 -2v-4a2 2 0 0 1 2 -2h4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 2 0 0 1-2 -2v-4a2 2 0 0 1 2 -2h4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 0 0 1-2 -2v-4a2 2 0 0 1 2 -2h4a2 2 0 0 1 2 - 2v-4a2 2 0 0 1 2 -2h4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 0 0 1 2 -2v-4a2 2 0 0 1 2 -2h4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 0 0 1 2 2v4a2 2 2 0 0 1 2 -2H4a2 2 2 0 0 1 2 -2v-4a2 2 0 0 1 2 -2h4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 0 0 1 2 -2v-4a2 2 0 0 1 2 -2h4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 0 0 1 2 -2v-4a2 2 0 0 1 2 - 2h4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 0 0 1 2 -2v-4a2 2 0 0 1 2 -2H4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 2 0 0 1 2 2v4a2 2 0 0 1 2 2H4a2 2 0 0 1 2 2v4a2 2 0 0 1 2-2H4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 0 0 1 2 2v4a2 2 0 0 1 2-2H4a2 2 2 0 0 1 2 2v4a2 2 0 00 1 2 -2H4a2 2 0 0 1 2 2v4a2 2 0 0 0 1 2-2H4a2 2 0 0 1 2 2v4a2 2 0 0 1 2-2H4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 2H4a2 2 0 0 1 2-2H4a2 2 2 0 0 1 2 2v4a2 2 0 0 1 2-2H4a2 2 0 0 1 2 2v4a2 2 0 0 1 2 -2H4a2 2 0 0 1 2 2v4a2 2 0 00 1 2 -2H4a2 2 0 00 1 2 2v4
    </div>
  `);
  
    // Add apply button handlers
    suggestions.forEach(suggestion => {
      const applyBtn = this.element.querySelector(`[onclick="window.applySuggestion('${suggestion.id}')"]`);
      if (applyBtn) {
        this.addEvent(applyBtn, 'click', (e) => {
          e.stopPropagation();
          this.applySuggestion(suggestion.id);
        });
      }
    });
  
    // Store suggestions for applying
    this.currentSuggestions = suggestions;
  }
  
  getConfidenceColor(confidence) {
    if (confidence >= 80) return '#10b981'; // High confidence - green
    if (confidence >= 60) return '#3b82f6'; // Medium confidence - blue
    if (confidence >= 40) return '#f59e0b'; // Low confidence - orange
    return '#ef4444'; // Very low confidence - red
  }
  
  formatParamKey(key) {
    return key.replace(/_/g, ' ');
  }
  
  formatParamValue(value) {
    if (typeof value === 'number') return value.toLocaleString();
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    return String(value);
  }
  
  applySuggestion(suggestionId) {
    const suggestion = this.currentSuggestions?.find(s => s.id === suggestionId);
    if (!suggestion) return;
    
    // Apply suggestion parameters to form
    this.emit('suggestion-selected', { suggestion });
    this.close();
  }
  
  copySuggestion(suggestionId) {
    const suggestion = this.currentSuggestions?.find(s => s.id === suggestionId);
    if (!suggestion) return;
    
    const paramsText = JSON.stringify(suggestion.parameters, null, 2);
    navigator.clipboard.writeText(paramsText).then(() => {
      this.emit('suggestion-copied', { suggestionId });
    }).catch(err => {
      console.error('Failed to copy:', err);
    });
    this.emit('suggestion-copy-failed', { error: err.message });
  }
  
  close() {
    this.setState({ isOpen: false });
    this.emit('closed');
  }
  
  open(algorithm) {
    this.fetchSuggestions(algorithm);
  }
}

/**
 * AI Suggestion Service
 * Provides ML-based optimization parameter suggestions
 */
class OptimizationSuggestionService {
  constructor() {
    this.cache = new Map();
    this.patterns = {
      qaoa: [],
      vqe: [],
      annealing: []
    };
    
    // Initialize with some example patterns learned from optimization research
    this.initializePatterns();
  }
  
  initializePatterns() {
    // Example QAOA patterns learned from research
    this.patterns.qaoa = [
      {
        title: 'Max-Cut Small Graphs',
        description: 'For graphs with 5-10 nodes, use p=2 with COBYLA optimizer and 1000 shots',
        conditions: { graphSize: '5-10', problemType: 'maxcut' },
        parameters: { p_layers: 2, optimizer: 'COBYLA', shots: 1000 },
        confidence: 95,
        source: 'research'
      },
      {
        title: 'Max-Cut Medium Graphs',
        description: 'For graphs with 11-20 nodes, use p=3 with SPSA optimizer and 2000 shots',
        conditions: { graphSize: '11-20', problemType: 'maxcut' },
        parameters: { p_layers: 3, optimizer: 'SPSA', shots: 2000 },
        confidence: 92,
        source: 'research'
      },
      {
        title: 'Max-Cut Large Graphs',
        description: 'For graphs with 21+ nodes, use p=4 with ADAM optimizer and 3000 shots',
        conditions: { graphSize: '21+', problemType: 'maxcut' },
        parameters: { p_layers: 4, optimizer: 'ADAM', shots: 3000 },
        confidence: 88,
        source: 'research'
      },
      {
        title: 'Portfolio Optimization High Risk',
        description: 'For high-risk portfolios, use p=3 with rotosolve optimizer and 1500 shots',
        conditions: { problemType: 'portfolio', riskLevel: 'high' },
        parameters: { p_layers: 3, optimizer: 'rotosolve', shots: 1500 },
        confidence: 87,
        source: 'research'
      },
      {
        title: 'Portfolio Optimization Low Risk',
        description: 'For low-risk portfolios, use p=2 with L-BFGS-B optimizer and 1000 shots',
        conditions: { problemType: 'portfolio', riskLevel: 'low' },
        parameters: { p_layers: 2, optimizer: 'L-BFGS-B', shots: 1000 },
        confidence: 94,
        source: 'research'
      }
    ];
    
    // VQE patterns
    this.patterns.vqe = [
      {
        title: 'Small Molecules (2-3 atoms)',
        description: 'For small molecules, use hardware_efficient ansatz with 200 shots and COBYLA optimizer',
        conditions: { atomCount: '2-3' },
        parameters: { ansatz: 'hardware_efficient', shots: 200, optimizer: 'COBYLA' },
        confidence: 96,
        source: 'research'
      },
      {
        title: 'Medium Molecules (4-7 atoms)',
        description: 'For medium molecules, use UCCSD ansatz with 400 shots and L-BFGS-B optimizer',
        conditions: { atomCount: '4-7' },
        parameters: { ansatz: 'uccsd', shots: 400, optimizer: 'L-BFGS-B' },
        confidence: 93,
        source: 'research'
      },
      {
        title: 'Large Molecules (8+ atoms)',
        description: 'For large molecules, use SU2 ansatz with 800 shots and SPSA optimizer',
        conditions: { atomCount: '8+' },
        parameters: { ansatz: 'su2', shots: 800, optimizer: 'SPSA' },
        confidence: 90,
        source: 'research'
      }
    ];
    
    // Quantum annealing patterns
    this.patterns.annealing = [
      {
        title: 'Dense QUBO Matrices',
        description: 'For dense QUBO matrices, use chain_strength=2.0 with 2000 reads',
        conditions: { qubodensity: 'dense' },
        parameters: { chain_strength: 2.0, num_reads: 2000, annealing_time: 20 },
        confidence: 91,
        source: 'research'
      },
      {
        title: 'Sparse QUBO Matrices',
        description: 'For sparse QUBO matrices, use chain_strength=1.0 with 1000 reads',
        conditions: { qubodensity: 'sparse' },
        parameters: { chain_strength: 1.0, num_reads: 1000, annealing_time: 20 },
        confidence: 89,
        source: 'research'
      },
      {
        title: 'Mixed Integer QUBO',
        description: 'For mixed integer problems, use chain_strength=1.5 with 1500 reads',
        conditions: { qubodensity: 'mixed' },
        parameters: { chain_strength: 1.5, num_reads: 1500, annealing_time: 20 },
        confidence: 85,
        source: 'research'
      }
    ];
  }
  
  getSuggestions(algorithm, conditions = {}) {
    const key = JSON.stringify({ algorithm, conditions });
    
    // Check cache
    if (this.cache.has(key)) {
      return Promise.resolve(this.cache.get(key));
    }
    
    // Filter and rank patterns by conditions
    const patterns = this.patterns[algorithm] || [];
    const filteredPatterns = patterns
      .filter(pattern => this.matchesConditions(pattern.conditions, conditions))
      .sort((a, b) => b.confidence - a.confidence);
    
    // Cache results
    this.cache.set(key, filteredPatterns);
    return Promise.resolve(filteredPatterns);
  }
  
  matchesConditions(patternConditions, userConditions) {
    if (Object.keys(patternConditions).length === 0) return true;
    
    for (const [key, patternValue] of Object.entries(patternConditions)) {
      const userValue = userConditions[key];
      if (userValue === undefined) continue;
      
      // Handle range conditions like "5-10"
      if (patternValue.includes('-')) {
        const [min, max] = patternValue.split('-').map(Number);
        if (userValue < min || userValue > max) {
          return false;
        }
      } else if (patternValue !== userValue) {
        return false;
      }
    }
    
    return true;
  }
  
  learnFromJob(job) {
    const algorithm = job.problem_type?.toLowerCase();
    if (!algorithm || !this.patterns[algorithm]) return;
    
    // Extract features from job
    const features = this.extractFeatures(job);
    
    // Add to learning history
    const newPattern = {
      id: `pattern_${Date.now()}`,
      title: `Optimized for ${features.description}`,
      description: `Based on successful job ${job.job_id.substring(0, 8)}: ${features.reason}`,
      conditions: features.conditions,
      parameters: job.problem_config,
      confidence: this.calculateConfidence(job.result),
      source: 'learning'
    };
    
    // Add to patterns if confidence is above threshold
    if (newPattern.confidence >= 70) {
      this.patterns[algorithm].unshift(newPattern);
      this.patterns[algorithm] = this.patterns[algorithm].slice(0, 20); // Keep only top 20
      
      console.log(`[Suggestions] Learned new pattern for ${algorithm}:`, newPattern.title);
    }
  }
  
  extractFeatures(job) {
    const features = {
      conditions: {},
      description: '',
      reason: ''
    };
    
    const config = job.problem_config || {};
    
    // Extract features based on algorithm type
    if (job.problem_type === 'QAOA') {
      const layers = config.p_layers;
      const graph = config.graph;
      
      if (graph) {
        const nodeCount = graph.length || 0;
        features.conditions.graphSize = nodeCount > 30 ? '21+' : nodeCount > 15 ? '16-20' : nodeCount > 5 ? '6-10' : '1-5';
        features.description = `Max-Cut problem with ${nodeCount} nodes`;
        features.reason = `Achieved optimal value of ${job.result?.optimal_value} with ${layers} layers`;
      }
      
      if (config.optimizer) {
        features.conditions.optimizer = config.optimizer;
      }
      
      if (config.shots) {
        features.conditions.shotsRange = config.shots < 1500 ? '<1500' : '1500-3000';
      }
    }
    
    else if (job.problem_type === 'VQE') {
      const molecule = config.molecule || '';
      const atomCount = this.parseAtomCount(molecule);
      
      if (atomCount) {
        features.conditions.atomCount = atomCount > 8 ? '8+' : atomCount > 4 ? '4-7' : '2-3';
        features.description = `VQE on ${molecule}`;
        features.reason = `Ansatz: ${config.ansatz}, Shots: ${config.shots}`;
      }
    }
    
    else if (job.problem_type === 'ANNEALING') {
      const matrix = config.qubo_matrix;
      const density = this.calculateMatrixDensity(matrix);
      
      if (density !== null) {
        features.conditions.qubodensity = density > 0.7 ? 'dense' : density > 0.3 ? 'mixed' : 'sparse';
        features.description = `QUBO optimization`;
        features.reason = `Chain strength: ${config.chain_strength}, Reads: ${config.num_reads}`;
      }
    }
    
    return features;
  }
  
  parseAtomCount(molecule) {
    const atomCounts = { 'H': 1, 'He': 3, 'Li': 7, 'H2': 2, 'HeH+': 8, 'LiH': 8 };
    const sorted = Object.entries(atomCounts).sort((a, b) => b[1] - a[1]);
    return sorted.find(([atom, count]) => molecule.includes(atom))?.[1] || 0;
  }
  
  calculateMatrixDensity(matrix) {
    if (!matrix || !Array.isArray(matrix) || matrix.length === 0) return null;
    
    const totalElements = matrix.reduce((sum, row) => sum + (Array.isArray(row) ? row.reduce((s, v) => s + (typeof v === 'number' && v !== 0 ? 1 : 0), 0), 0);
    const totalPossible = matrix.length * matrix[0]?.length || 0;
    
    return totalPossible > 0 ? totalElements / totalPossible : null;
  }
  
  calculateConfidence(result) {
    if (!result) return 50;
    
    const {
      optimal_value,
      iterations,
      convergence_history,
      execution_time
    } = result;
    
    let confidence = 50;
    
    // High confidence if converged quickly
    if (execution_time && execution_time < 10) confidence += 15;
    else if (execution_time < 30) confidence += 10;
    else if (execution_time < 60) confidence += 5;
    
    // High confidence if converged with few iterations
    if (iterations && iterations < 50) confidence += 10;
    else if (iterations && iterations < 100) confidence += 5;
    
    // High confidence if has good convergence history
    if (convergence_history?.length > 1) {
      const improvement = conververgence_history.length > 1
        ? Math.abs(convergence_history[-1] - convergence_history[0]) / convergence_history[0]
        : 0;
      if (improvement > 0.5) confidence += 15;
      else if (improvement > 0.2) confidence += 10;
    }
    
    return Math.min(98, confidence); // Cap at 98%
  }
}

// Global instance and initialization
let suggestionService = null;

function getSuggestionService() {
  if (!suggestionService) {
    suggestionService = new OptimizationSuggestionService();
  }
  return suggestionService;
}

// Make available globally
window.getSuggestionService = getSuggestionService;
window.OptimizationSuggestionCard = OptimizationSuggestionCard;

export default OptimizationSuggestionCard;
