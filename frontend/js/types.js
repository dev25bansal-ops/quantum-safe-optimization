/**
 * Type definitions for QSOP Frontend.
 * Provides TypeScript-like type checking with JSDoc.
 */

/**
 * @typedef {'pending' | 'running' | 'completed' | 'failed' | 'cancelled'} JobStatus
 */

/**
 * @typedef {'QAOA' | 'VQE' | 'ANNEALING'} ProblemType
 */

/**
 * @typedef {object} Job
 * @property {string} id - Unique job identifier
 * @property {ProblemType} problem_type - Type of optimization problem
 * @property {object} problem_config - Problem configuration
 * @property {JobStatus} status - Current job status
 * @property {number} [progress] - Progress percentage (0-100)
 * @property {object} [result] - Job result when completed
 * @property {string} [error] - Error message if failed
 * @property {string} created_at - ISO timestamp
 * @property {string} [started_at] - ISO timestamp
 * @property {string} [completed_at] - ISO timestamp
 */

/**
 * @typedef {object} User
 * @property {string} user_id - User identifier
 * @property {string} username - Username
 * @property {string} [email] - User email
 * @property {string[]} roles - User roles
 * @property {string} created_at - ISO timestamp
 */

/**
 * @typedef {object} TokenResponse
 * @property {string} access_token - JWT access token
 * @property {string} token_type - Token type (usually 'bearer')
 * @property {number} expires_in - Token expiration in seconds
 * @property {string} [refresh_token] - Refresh token
 * @property {string} pqc_signature - ML-DSA signature of token
 */

/**
 * @typedef {object} KeyPair
 * @property {string} public_key - Base64 encoded public key
 * @property {string} key_id - Key identifier
 * @property {string} algorithm - Algorithm name
 * @property {string} expires_at - ISO timestamp
 */

/**
 * @typedef {object} ApiError
 * @property {string} error - Error code
 * @property {string} message - Human-readable message
 * @property {object} [details] - Additional details
 * @property {string} [request_id] - Request tracking ID
 */

/**
 * @typedef {object} HealthStatus
 * @property {string} status - 'healthy' or 'unhealthy'
 * @property {string} version - API version
 * @property {string} env - Environment name
 */

/**
 * @typedef {object} CryptoStatus
 * @property {string} status - 'healthy' or 'unhealthy'
 * @property {boolean} liboqs_available - Whether liboqs is available
 * @property {string} implementation - 'liboqs' or 'STUB'
 * @property {string} [security_warning] - Warning if using stub
 */

/**
 * @typedef {object} WebSocketMessage
 * @property {'connected' | 'state' | 'progress' | 'completed' | 'error' | 'ping'} type - Message type
 * @property {string} [job_id] - Job identifier
 * @property {object} [data] - Message data
 * @property {string} [message] - Error message
 * @property {string} [timestamp] - ISO timestamp
 */

/**
 * @typedef {object} ApiClientConfig
 * @property {string} baseUrl - API base URL
 * @property {number} [timeout] - Request timeout in ms
 * @property {string} [token] - Auth token
 * @property {(error: ApiError) => void} [onError] - Error handler
 */

/**
 * @callback JobSubmitCallback
 * @param {Job} job - Submitted job
 * @returns {void}
 */

/**
 * @callback JobProgressCallback
 * @param {string} jobId - Job ID
 * @param {number} progress - Progress percentage
 * @param {object} [data] - Progress data
 * @returns {void}
 */

/**
 * @callback JobCompleteCallback
 * @param {string} jobId - Job ID
 * @param {object} result - Job result
 * @returns {void}
 */

/**
 * @callback JobErrorCallback
 * @param {string} jobId - Job ID
 * @param {string} error - Error message
 * @returns {void}
 */

export {};
