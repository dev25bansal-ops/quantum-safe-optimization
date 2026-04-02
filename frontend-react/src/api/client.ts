import axios, { AxiosError, AxiosInstance } from "axios";
import type {
  Job,
  JobCreateRequest,
  User,
  KeyPair,
  AuthTokens,
  HealthStatus,
  CryptoStatus,
  PaginatedResponse,
  ApiError,
} from "@/types";

const API_BASE = "/api/v1";

export class QSOPApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    public details?: ApiError,
  ) {
    super(message);
    this.name = "QSOPApiError";
  }
}

function handleError(error: AxiosError<ApiError>): never {
  if (error.response?.data) {
    throw new QSOPApiError(
      error.response.data.detail || error.message,
      error.response.status,
      error.response.data,
    );
  }
  throw new QSOPApiError(error.message);
}

export class QSOPApiClient {
  private client: AxiosInstance;
  private token: string | null = null;
  private refreshToken: string | null = null;

  constructor(baseURL: string = API_BASE) {
    this.client = axios.create({
      baseURL,
      timeout: 30000,
      headers: {
        "Content-Type": "application/json",
      },
    });

    this.client.interceptors.request.use((config) => {
      if (this.token) {
        config.headers.Authorization = `Bearer ${this.token}`;
      }
      return config;
    });
  }

  setTokens(tokens: AuthTokens) {
    this.token = tokens.access_token;
    this.refreshToken = tokens.refresh_token ?? null;
  }

  clearTokens() {
    this.token = null;
    this.refreshToken = null;
  }

  async login(username: string, password: string): Promise<AuthTokens> {
    try {
      const { data } = await this.client.post<AuthTokens>("/auth/login", {
        username,
        password,
      });
      this.setTokens(data);
      return data;
    } catch (e) {
      handleError(e as AxiosError<ApiError>);
    }
  }

  async logout(): Promise<void> {
    try {
      await this.client.post("/auth/logout");
      this.clearTokens();
    } catch (e) {
      handleError(e as AxiosError<ApiError>);
    }
  }

  async getCurrentUser(): Promise<User> {
    try {
      const { data } = await this.client.get<User>("/auth/me");
      return data;
    } catch (e) {
      handleError(e as AxiosError<ApiError>);
    }
  }

  async getJobs(params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<PaginatedResponse<Job>> {
    try {
      const { data } = await this.client.get<PaginatedResponse<Job>>("/jobs", {
        params,
      });
      return data;
    } catch (e) {
      handleError(e as AxiosError<ApiError>);
    }
  }

  async getJob(jobId: string): Promise<Job> {
    try {
      const { data } = await this.client.get<Job>(`/jobs/${jobId}`);
      return data;
    } catch (e) {
      handleError(e as AxiosError<ApiError>);
    }
  }

  async submitJob(request: JobCreateRequest): Promise<Job> {
    try {
      const { data } = await this.client.post<Job>("/jobs", request);
      return data;
    } catch (e) {
      handleError(e as AxiosError<ApiError>);
    }
  }

  async cancelJob(jobId: string): Promise<Job> {
    try {
      const { data } = await this.client.post<Job>(`/jobs/${jobId}/cancel`);
      return data;
    } catch (e) {
      handleError(e as AxiosError<ApiError>);
    }
  }

  async getJobResult(jobId: string): Promise<Record<string, unknown>> {
    try {
      const { data } = await this.client.get(`/jobs/${jobId}/result`);
      return data;
    } catch (e) {
      handleError(e as AxiosError<ApiError>);
    }
  }

  async generateKey(
    keyType: "kem" | "signing",
    securityLevel: number = 3,
  ): Promise<KeyPair> {
    try {
      const { data } = await this.client.post<KeyPair>("/auth/keys/generate", {
        key_type: keyType,
        security_level: securityLevel,
      });
      return data;
    } catch (e) {
      handleError(e as AxiosError<ApiError>);
    }
  }

  async getKeys(): Promise<KeyPair[]> {
    try {
      const { data } = await this.client.get<KeyPair[]>("/auth/keys");
      return data;
    } catch (e) {
      handleError(e as AxiosError<ApiError>);
    }
  }

  async getHealth(): Promise<HealthStatus> {
    try {
      const { data } = await this.client.get<HealthStatus>("/health");
      return data;
    } catch (e) {
      handleError(e as AxiosError<ApiError>);
    }
  }

  async getCryptoStatus(): Promise<CryptoStatus> {
    try {
      const { data } = await this.client.get<CryptoStatus>("/health/crypto");
      return data;
    } catch (e) {
      handleError(e as AxiosError<ApiError>);
    }
  }
}

export const apiClient = new QSOPApiClient();
