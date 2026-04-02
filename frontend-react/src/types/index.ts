export type JobStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type AlgorithmType = "QAOA" | "VQE" | "ANNEALING" | "GROVER";

export type ProblemType =
  | "maxcut"
  | "portfolio"
  | "tsp"
  | "graph_coloring"
  | "molecular_hamiltonian"
  | "qubo"
  | "ising";

export type BackendType =
  | "qiskit_aer"
  | "ibm_quantum"
  | "aws_braket"
  | "azure_quantum"
  | "dwave_leap";

export interface Job {
  id: string;
  problem_type: AlgorithmType;
  status: JobStatus;
  created_at: string;
  updated_at?: string;
  user_id?: string;
  progress: number;
  result?: JobResult;
  error?: string;
  parameters: JobParameters;
}

export interface JobResult {
  optimal_value: number;
  optimal_parameters: Record<string, number>;
  iterations: number;
  objective_history: number[];
  execution_time_ms: number;
  shots_used: number;
}

export interface JobParameters {
  layers?: number;
  optimizer?: string;
  max_iterations?: number;
  shots?: number;
  backend: BackendType;
  random_seed?: number;
}

export interface JobCreateRequest {
  problem_type: AlgorithmType;
  problem_config: ProblemConfig;
  parameters?: Partial<JobParameters>;
  webhook_url?: string;
}

export type ProblemConfig =
  | MaxCutConfig
  | PortfolioConfig
  | QUBOConfig
  | MolecularConfig;

export interface MaxCutConfig {
  type: "maxcut";
  graph: {
    edges: [number, number][];
    weights?: number[];
  };
}

export interface PortfolioConfig {
  type: "portfolio";
  assets: number;
  expected_returns: number[];
  covariance_matrix: number[][];
  budget?: number;
}

export interface QUBOConfig {
  type: "qubo";
  qubo_matrix: number[][];
}

export interface MolecularConfig {
  type: "molecular_hamiltonian";
  molecule: string;
  basis_set?: string;
}

export interface User {
  user_id: string;
  username: string;
  email: string | null;
  roles: string[];
  created_at: string;
}

export interface KeyPair {
  key_id: string;
  public_key: string;
  key_type: "kem" | "signing";
  algorithm: string;
  created_at: string;
  expires_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token?: string;
  expires_in: number;
  token_type: string;
}

export interface ApiError {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance?: string;
  timestamp?: string;
}

export interface HealthStatus {
  status: "healthy" | "degraded" | "unhealthy";
  version: string;
  uptime_seconds: number;
  components: Record<string, ComponentHealth>;
}

export interface ComponentHealth {
  status: "up" | "down" | "degraded";
  latency_ms?: number;
  message?: string;
}

export interface CryptoStatus {
  liboqs_available: boolean;
  implementation: "liboqs" | "STUB";
  security_warning: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
