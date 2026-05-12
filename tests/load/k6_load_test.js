/**
 * Load Testing Script for QuantumSafe Optimize API
 *
 * Run with k6:
 *   k6 run tests/load/k6_load_test.js
 *
 * With custom config:
 *   k6 run --vus 50 --duration 60s tests/load/k6_load_test.js
 *
 * With cloud reporting:
 *   K6_CLOUD_TOKEN=xxx k6 run --out cloud tests/load/k6_load_test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend, Rate } from 'k6/metrics';

// Custom metrics
const jobSubmissionTime = new Trend('job_submission_duration_ms');
const jobQueryTime = new Trend('job_query_duration_ms');
const healthCheckTime = new Trend('health_check_duration_ms');
const errorRate = new Rate('error_rate');
const jobsSubmitted = new Counter('jobs_submitted');

// Test configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_BASE = `${BASE_URL}/api/v1`;

// k6 options — can be overridden via CLI
export const options = {
  stages: [
    { duration: '30s', target: 10 },   // Ramp up to 10 users
    { duration: '1m', target: 50 },    // Ramp up to 50 users
    { duration: '2m', target: 50 },    // Stay at 50 users
    { duration: '30s', target: 100 },  // Spike to 100 users
    { duration: '1m', target: 100 },   // Stay at 100 users
    { duration: '30s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],       // 95% of requests under 500ms
    http_req_failed: ['rate<0.05'],         // Error rate under 5%
    job_submission_duration_ms: ['p(95)<2000'],
    error_rate: ['rate<0.1'],
  },
};

// Test data
const PROBLEM_TYPES = ['QAOA', 'VQE', 'ANNEALING'];
const BACKENDS = ['local_simulator', 'advanced_simulator'];
const PROBLEMS = {
  QAOA: {
    problem: 'maxcut',
    edges: [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2]],
  },
  VQE: {
    hamiltonian: 'h2',
    bond_length: 0.74,
  },
  ANNEALING: {
    num_variables: 4,
  },
};

/**
 * Scenario 1: Health check endpoint
 */
export function healthCheck() {
  const res = http.get(`${BASE_URL}/health`);
  healthCheckTime.add(res.timings.duration);

  const success = check(res, {
    'health status is 200': (r) => r.status === 200,
    'health response is valid': (r) => {
      const body = r.json();
      return body && body.status === 'healthy';
    },
  });

  errorRate.add(!success);
  sleep(1);
}

/**
 * Scenario 2: Submit optimization job
 */
export function submitJob() {
  const problemType = PROBLEM_TYPES[Math.floor(Math.random() * PROBLEM_TYPES.length)];
  const backend = BACKENDS[Math.floor(Math.random() * BACKENDS.length)];

  const payload = JSON.stringify({
    problem_type: problemType,
    problem_config: PROBLEMS[problemType],
    parameters: {
      layers: 2,
      shots: 1024,
      optimizer: 'COBYLA',
    },
    backend: backend,
    priority: Math.floor(Math.random() * 10) + 1,
  });

  const params = {
    headers: { 'Content-Type': 'application/json' },
  };

  const res = http.post(`${API_BASE}/jobs`, payload, params);
  jobSubmissionTime.add(res.timings.duration);
  jobsSubmitted.add(1);

  const success = check(res, {
    'job submission is 202': (r) => r.status === 202,
    'job_id returned': (r) => {
      const body = r.json();
      return body && body.job_id && body.job_id.startsWith('job_');
    },
    'status is queued': (r) => r.json().status === 'queued',
  });

  errorRate.add(!success);

  // Store job_id for later queries
  if (res.status === 202) {
    return res.json().job_id;
  }
  return null;
}

/**
 * Scenario 3: Query job status
 */
export function queryJob(jobId) {
  if (!jobId) return;

  const res = http.get(`${API_BASE}/jobs/${jobId}`);
  jobQueryTime.add(res.timings.duration);

  check(res, {
    'job query is 200': (r) => r.status === 200,
    'job status field present': (r) => r.json().status !== undefined,
  });

  sleep(0.5);
}

/**
 * Scenario 4: List jobs with pagination
 */
export function listJobs() {
  const res = http.get(`${API_BASE}/jobs?limit=10&offset=0`);

  check(res, {
    'job list is 200': (r) => r.status === 200,
    'pagination metadata present': (r) => {
      const body = r.json();
      return body && body.page !== undefined && body.total_pages !== undefined;
    },
  });

  sleep(1);
}

/**
 * Scenario 5: Priority queue status
 */
export function checkQueueStatus() {
  const res = http.get(`${API_BASE}/jobs/queue/status`);

  check(res, {
    'queue status is 200': (r) => r.status === 200,
    'queue_size present': (r) => r.json().queue_size !== undefined,
  });

  sleep(2);
}

/**
 * Default export — mix of all scenarios
 */
export default function () {
  // 20% health checks
  // 40% job submissions
  // 20% job queries
  // 10% job listing
  // 10% queue status

  const rand = Math.random();

  if (rand < 0.2) {
    healthCheck();
  } else if (rand < 0.6) {
    const jobId = submitJob();
    if (jobId) {
      queryJob(jobId);
    }
  } else if (rand < 0.8) {
    // Query a random job
    queryJob(`job_${Math.random().toString(36).substring(2, 14)}`);
  } else if (rand < 0.9) {
    listJobs();
  } else {
    checkQueueStatus();
  }
}
