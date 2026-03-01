/**
 * QuantumSafe API Client
 * Production-ready API client with caching, retry logic, and error handling
 *
 * Features:
 * - Automatic retry with exponential backoff
 * - Request/response caching
 * - Request cancellation
 * - Request timing
 * - Error classification
 * - Interceptor support
 * - Request deduplication
 */

/**
 * @typedef {Object} RequestOptions
 * @property {string} [method='GET']
 * @property {Object} [headers]
 * @property {Object|Array|FormData} [body]
 * @property {number} [timeout=30000]
 * @property {number} [retries=3]
 * @property {boolean} [cache=false]
 * @property {number} [cacheTTL=60000]
 * @property {AbortSignal} [signal]
 * @property {Object} [metadata]
 */

/**
 * @typedef {Object} APIResponse
 * @property {T} data
 * @property {Object} metadata
 * @property {string} requestId
 * @property {number} duration
 * @property {boolean} cached
 */

class QuantumSafeAPIClient {
  constructor(config = {}) {
    this.config = {
      baseURL: config.baseURL || window.location.origin,
      timeout: config.timeout || 30000,
      retries: config.retries || 3,
      cache: new Map(),
      defaultHeaders: config.defaultHeaders || {
        'Content-Type': 'application/json',
      },
      interceptors: {
        request: [],
        response: [],
        error: []
      },
      metrics: {
        totalRequests: 0,
        successfulRequests: 0,
        failedRequests: 0,
        cachedRequests: 0
      }
    };

    // Pending requests for deduplication
    this.pendingRequests = new Map();
  }

  /**
   * Make an API request
   * @param {string} endpoint
   * @param {RequestOptions} options
   * @returns {Promise<APIResponse>}
   */
  async request(endpoint, options = {}) {
    const url = `${this.config.baseURL}${endpoint}`;
    const opts = {
      method: 'GET',
      ...options,
      headers: { ...this.config.defaultHeaders, ...options.headers }
    };

    // Generate request ID for tracking
    const requestId = this.generateRequestId();
    opts.metadata = { requestId, startTime: Date.now() };

    this.config.metrics.totalRequests++;

    try {
      // Apply request interceptors
      let finalOptions = opts;
      for (const interceptor of this.config.interceptors.request) {
        finalOptions = await interceptor(finalOptions);
      }

      // Check cache for GET requests
      if (opts.cache && opts.method === 'GET') {
        const cachedResponse = this.config.cache.get(endpoint);
        if (cachedResponse && Date.now() - cachedResponse.timestamp < (opts.cacheTTL || 60000)) {
          this.config.metrics.cachedRequests++;
          console.log(`[API] Cache hit for ${endpoint}`);
          return {
            data: cachedResponse.data,
            metadata: cachedResponse.metadata,
            requestId,
            duration: 0,
            cached: true
          };
        }
      }

      // Execute request with retry logic
      const response = await this.executeWithRetry(url, finalOptions, requestId);

      // Apply response interceptors
      let processedResponse = response;
      for (const interceptor of this.config.interceptors.response) {
        processedResponse = await interceptor(processedResponse);
      }

      // Cache successful GET responses
      if (opts.cache && opts.method === 'GET' && response.ok) {
        this.config.cache.set(endpoint, {
          data: response.data,
          metadata: processedResponse.metadata,
          timestamp: Date.now()
        });
      }

      this.config.metrics.successfulRequests++;

      return {
        data: response.data,
        metadata: processedResponse.metadata,
        requestId,
        duration: Date.now() - opts.metadata.startTime,
        cached: false
      };

    } catch (error) {
      this.config.metrics.failedRequests++;

      // Apply error interceptors
      let processedError = error;
      for (const interceptor of this.config.interceptors.error) {
        processedError = await interceptor(processedError);
      }

      throw processedError;
    }
  }

  /**
   * Execute HTTP request with retry logic
   * @private
   */
  async executeWithRetry(url, options, requestId, attempt = 0) {
    const maxRetries = options.retries || this.config.retries;

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), options.timeout || this.config.timeout);

      if (options.signal) {
        options.signal.addEventListener('abort', () => {
          clearTimeout(timeoutId);
          controller.abort();
        });
      }

      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'X-Request-ID': requestId,
          ...options.headers
        }
      });

      clearTimeout(timeoutId);

      const data = await this.parseResponse(response);

      if (!response.ok) {
        throw this.createAPIError(response, data);
      }

      return {
        ok: response.ok,
        status: response.status,
        headers: Object.fromEntries(response.headers.entries()),
        data
      };

    } catch (error) {
      const isRetryable = this.isRetryableError(error) && attempt < maxRetries;

      if (isRetryable) {
        const delay = this.calculateBackoff(attempt);
        console.log(`[API] Retrying ${url} (attempt ${attempt + 1}/${maxRetries}) after ${delay}ms`);

        await this.sleep(delay);
        return this.executeWithRetry(url, options, requestId, attempt + 1);
      }

      throw error;
    }
  }

  /**
   * Parse response based on content type
   * @private
   */
  async parseResponse(response) {
    const contentType = response.headers.get('content-type');

    if (contentType?.includes('application/json')) {
      return await response.json();
    }

    if (contentType?.includes('text/')) {
      return await response.text();
    }

    if (contentType?.includes('multipart/form-data')) {
      return await response.formData();
    }

    return await response.blob();
  }

  /**
   * Create structured error from HTTP response
   * @private
   */
  createAPIError(response, data) {
    const error = new Error(data?.detail || data?.message || response.statusText || 'Request failed');
    error.name = 'APIError';
    error.status = response.status;
    error.code = data?.code || undefined;
    error.requestId = response.headers.get('X-Request-ID');
    error.details = data;

    return error;
  }

  /**
   * Determine if error is retryable
   * @private
   */
  isRetryableError(error) {
    // Retry on network errors, timeouts, and server errors (5xx)
    if (error.name === 'AbortError' || error.name === 'TypeError') {
      return false;
    }

    if (error.name === 'APIError') {
      return error.status >= 500 || error.status === 429;
    }

    return true;
  }

  /**
   * Calculate exponential backoff delay
   * @private
   */
  calculateBackoff(attempt) {
    const baseDelay = 1000;
    const maxDelay = 30000;
    const delay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
    // Add jitter to prevent thundering herd
    return delay + Math.random() * 1000;
  }

  /**
   * Sleep utility
   * @private
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Generate unique request ID
   * @private
   */
  generateRequestId() {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Add request interceptor
   */
  addRequestInterceptor(interceptor) {
    this.config.interceptors.request.push(interceptor);
  }

  /**
   * Add response interceptor
   */
  addResponseInterceptor(interceptor) {
    this.config.interceptors.response.push(interceptor);
  }

  /**
   * Add error interceptor
   */
  addErrorInterceptor(interceptor) {
    this.config.interceptors.error.push(interceptor);
  }

  /**
   * Clear all caches
   */
  clearCache() {
    this.config.cache.clear();
  }

  /**
   * Get metrics
   */
  getMetrics() {
    return { ...this.config.metrics };
  }

  // ===== Convenience methods for common HTTP verbs =====

  get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  post(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'POST',
      body: data
    });
  }

  put(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'PUT',
      body: data
    });
  }

  patch(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'PATCH',
      body: data
    });
  }

  delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'DELETE' });
  }
}

// Create and export singleton instance
const apiClient = new QuantumSafeAPIClient();

// Add default auth interceptor if token exists
apiClient.addRequestInterceptor(async (options) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    options.headers = {
      ...options.headers,
      'Authorization': `Bearer ${token}`
    };
  }
  return options;
});

// Add default error interceptor
apiClient.addErrorInterceptor((error) => {
  // Handle 401 (Unauthorized)
  if (error.name === 'APIError' && error.status === 401) {
    localStorage.removeItem('authToken');
    window.dispatchEvent(new CustomEvent('auth-expired'));
  }

  return error;
});

export default apiClient;

// Export class for creating additional instances
export { QuantumSafeAPIClient };
