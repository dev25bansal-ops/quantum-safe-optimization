/**
 * TypeScript definitions for Quantum-Safe Optimization Platform Frontend
 */

declare module "@modules/api" {
  export interface ApiResponse<T> {
    data: T;
    status: number;
    message?: string;
  }

  export interface ApiError {
    error: string;
    message: string;
    request_id?: string;
  }

  export function apiGet<T>(
    endpoint: string,
    options?: RequestInit,
  ): Promise<T>;
  export function apiPost<T>(
    endpoint: string,
    data: unknown,
    options?: RequestInit,
  ): Promise<T>;
  export function apiPut<T>(
    endpoint: string,
    data: unknown,
    options?: RequestInit,
  ): Promise<T>;
  export function apiDelete<T>(
    endpoint: string,
    options?: RequestInit,
  ): Promise<T>;
}

declare module "@modules/config" {
  export interface AppConfig {
    API_BASE_URL: string;
    WS_URL: string;
    AUTH_TOKEN_KEY: string;
    REFRESH_TOKEN_KEY: string;
    DEMO_MODE: boolean;
  }

  export const CONFIG: AppConfig;
  export const STATE: AppState;

  export interface AppState {
    isAuthenticated: boolean;
    user: User | null;
    theme: "light" | "dark";
    loading: boolean;
  }
}

declare module "@modules/auth" {
  export interface User {
    id: string;
    username: string;
    email?: string;
    roles: string[];
    kem_public_key?: string;
    signing_public_key?: string;
  }

  export interface LoginRequest {
    username: string;
    password: string;
  }

  export interface LoginResponse {
    access_token: string;
    refresh_token: string;
    token_type: string;
    expires_in: number;
    user: User;
  }

  export interface RegisterRequest {
    username: string;
    password: string;
    email?: string;
  }

  export function login(credentials: LoginRequest): Promise<LoginResponse>;
  export function logout(): Promise<void>;
  export function register(data: RegisterRequest): Promise<LoginResponse>;
  export function refreshToken(): Promise<LoginResponse>;
  export function getCurrentUser(): User | null;
  export function isAuthenticated(): boolean;
}

declare module "@modules/jobs" {
  export interface Job {
    job_id: string;
    status:
      | "pending"
      | "queued"
      | "running"
      | "completed"
      | "failed"
      | "cancelled";
    problem_type: string;
    backend: string;
    created_at: string;
    started_at?: string;
    completed_at?: string;
    parameters?: Record<string, unknown>;
    result?: Record<string, unknown>;
    error?: string;
  }

  export interface JobSubmitRequest {
    problem_type: string;
    problem_config: Record<string, unknown>;
    parameters?: Record<string, unknown>;
    backend?: string;
    callback_url?: string;
    encrypt_result?: boolean;
  }

  export interface JobListResponse {
    jobs: Job[];
    total: number;
    limit: number;
    offset: number;
  }

  export function submitJob(data: JobSubmitRequest): Promise<Job>;
  export function getJob(jobId: string): Promise<Job>;
  export function listJobs(params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<JobListResponse>;
  export function cancelJob(jobId: string): Promise<Job>;
  export function getJobResult(jobId: string): Promise<Record<string, unknown>>;
}

declare module "@modules/websocket" {
  export interface WebSocketMessage {
    type: string;
    data: unknown;
    timestamp?: string;
  }

  export interface WebSocketOptions {
    onMessage?: (message: WebSocketMessage) => void;
    onOpen?: () => void;
    onClose?: () => void;
    onError?: (error: Event) => void;
    reconnect?: boolean;
    maxReconnectAttempts?: number;
  }

  export class WebSocketManager {
    connect(url: string, options?: WebSocketOptions): void;
    disconnect(): void;
    send(message: WebSocketMessage): void;
    subscribe(handler: (message: WebSocketMessage) => void): () => void;
  }

  export const wsManager: WebSocketManager;
}

declare module "@modules/toast" {
  export type ToastType = "success" | "error" | "warning" | "info";

  export interface ToastOptions {
    duration?: number;
    position?: "top-right" | "top-left" | "bottom-right" | "bottom-left";
    closable?: boolean;
  }

  export function showToast(
    type: ToastType,
    title: string,
    message?: string,
    options?: ToastOptions,
  ): void;
}

declare module "@modules/notifications" {
  export interface Notification {
    notification_id: string;
    notification_type: string;
    title: string;
    message: string;
    user_id: string;
    read: boolean;
    created_at: string;
    data?: Record<string, unknown>;
  }

  export function getNotifications(
    unreadOnly?: boolean,
  ): Promise<Notification[]>;
  export function markNotificationRead(
    notificationId: string,
  ): Promise<boolean>;
  export function getUnreadCount(): Promise<number>;
}

declare module "@modules/charts" {
  export interface ChartConfig {
    type: "line" | "bar" | "pie" | "doughnut" | "radar";
    data: unknown;
    options?: Record<string, unknown>;
  }

  export function createChart(
    containerId: string,
    config: ChartConfig,
  ): unknown;
  export function updateChart(chart: unknown, newData: unknown): void;
  export function destroyChart(chart: unknown): void;
}

declare module "@modules/theme" {
  export type Theme = "light" | "dark" | "system";

  export function getTheme(): Theme;
  export function setTheme(theme: Theme): void;
  export function toggleTheme(): void;
  export function watchThemeChange(
    callback: (theme: Theme) => void,
  ): () => void;
}

declare module "@modules/utils" {
  export function escapeHtml(str: string): string;
  export function formatDate(date: string | Date): string;
  export function formatTimeShort(date: string | Date): string;
  export function formatBytes(bytes: number): string;
  export function formatDuration(ms: number): string;
  export function debounce<T extends (...args: unknown[]) => unknown>(
    fn: T,
    delay: number,
  ): T;
  export function throttle<T extends (...args: unknown[]) => unknown>(
    fn: T,
    limit: number,
  ): T;
  export function getAuthHeaders(): Record<string, string>;
}
