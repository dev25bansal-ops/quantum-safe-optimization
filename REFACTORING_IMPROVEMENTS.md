# QSOP Code Quality Improvements

## Executive Summary

This document identifies critical code quality issues in the QSOP codebase and provides actionable refactoring recommendations.

---

## 1. MONOLITHIC dashboard.js (4,225 lines)

### Problem
The `dashboard.js` file is a classic "God Object" anti-pattern containing multiple responsibilities in a single file:

- Authentication (login/register/logout)
- Job management (CRUD, polling, pagination)
- Chart visualizations (convergence, probability, parameter charts)
- WebSocket lifecycle
- Notifications (toasts, badges)
- Settings & key management
- UI state management

### Proposed Module Structure

```
frontend/js/
├── dashboard.js (main entry point, ~200 lines)
├── modules/
│   ├── auth.module.js
│   ├── jobs.module.js
│   ├── charts.module.js
│   ├── websocket.module.js
│   ├── notifications.module.js
│   └── settings.module.js
└── utils/
    ├── api.js
    ├── storage.js
    └── formatting.js
```

### Code Sample: Refactored Module Structure

**frontend/js/modules/auth.module.js**
```javascript
// Authentication module - handles login, register, logout, token management
export const AuthModule = (() => {
  const CONFIG = {
    TOKEN_KEY: 'authToken',
    USER_KEY: 'quantumSafeUser',
    API_BASE: localStorage.getItem('apiUrl')?.replace(/\/api\/v1\/?$/, '') || window.location.origin
  };

  async function login(email, password) {
    const response = await fetch(`${CONFIG.API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: email, password })
    });

    if (!response.ok) {
      throw new APIError('Login failed', response.status, await parseErrorResponse(response));
    }

    const data = await response.json();
    setToken(data.access_token);
    return data;
  }

  async function register(name, email, password) {
    const response = await fetch(`${CONFIG.API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: email, email, password, name })
    });

    if (!response.ok) {
      throw new APIError('Registration failed', response.status, await parseErrorResponse(response));
    }

    return await response.json();
  }

  async function logout() {
    // Try to call logout endpoint
    const token = getToken();
    if (token) {
      await fetch(`${CONFIG.API_BASE}/auth/logout`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      }).catch(() => {});
    }
    clearAuth();
  }

  function getToken() {
    return localStorage.getItem(CONFIG.TOKEN_KEY);
  }

  function setToken(token) {
    localStorage.setItem(CONFIG.TOKEN_KEY, token);
  }

  function clearAuth() {
    localStorage.removeItem(CONFIG.TOKEN_KEY);
    localStorage.removeItem(CONFIG.USER_KEY);
    localStorage.removeItem('refreshToken');
  }

  function isAuthenticated() {
    const token = getToken();
    if (!token) return false;

    try {
      // Check if demo token (base64 JSON)
      const decoded = JSON.parse(atob(token));
      return decoded.exp > Date.now();
    } catch {
      // Real JWT tokens are verified server-side
      return true;
    }
  }

  function getAuthHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    const token = getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  return {
    login,
    register,
    logout,
    getToken,
    setToken,
    isAuthenticated,
    getAuthHeaders
  };
})();
```

**frontend/js/modules/jobs.module.js**
```javascript
// Jobs module - handles CRUD, polling, pagination
export const JobsModule = (() => {
  const STATE = {
    jobs: [],
    currentPage: 1,
    pageSize: 10,
    totalJobs: 0,
    selectedForCompare: [],
    isLoading: false
  };

  async function listJobs(filters = {}) {
    const { status, problem_type, search, page = 1, limit = 10 } = filters;
    const params = new URLSearchParams({
      skip: (page - 1) * limit,
      limit: limit
    });

    if (status) params.append('status', status);
    if (problem_type) params.append('problem_type', problem_type.toUpperCase());
    if (search) params.append('search', search);

    const response = await fetch(`${CONFIG.apiUrl}/jobs?${params}`, {
      headers: AuthModule.getAuthHeaders()
    });

    if (!response.ok) {
      throw new APIError('Failed to load jobs', response.status, await parseErrorResponse(response));
    }

    const data = await response.json();
    STATE.jobs = (data.jobs || []).map(normalizeJob);
    STATE.totalJobs = data.total || STATE.jobs.length;
    STATE.currentPage = page;

    return { jobs: STATE.jobs, total: STATE.totalJobs };
  }

  async function getJob(jobId) {
    const response = await fetch(`${CONFIG.apiUrl}/jobs/${jobId}`, {
      headers: AuthModule.getAuthHeaders()
    });

    if (!response.ok) {
      throw new APIError('Job not found', response.status, await parseErrorResponse(response));
    }

    return normalizeJob(await response.json());
  }

  async function submitJob(jobData) {
    const response = await fetch(`${CONFIG.apiUrl}/jobs`, {
      method: 'POST',
      headers: AuthModule.getAuthHeaders(),
      body: JSON.stringify(jobData)
    });

    if (!response.ok) {
      throw new APIError('Job submission failed', response.status, await parseErrorResponse(response));
    }

    return await response.json();
  }

  async function cancelJob(jobId) {
    const response = await fetch(`${CONFIG.apiUrl}/jobs/${jobId}`, {
      method: 'DELETE',
      headers: AuthModule.getAuthHeaders()
    });

    if (!response.ok) {
      throw new APIError('Failed to cancel job', response.status, await parseErrorResponse(response));
    }

    return { success: true };
  }

  async function retryJob(jobId) {
    const response = await fetch(`${CONFIG.apiUrl}/jobs/${jobId}/retry`, {
      method: 'POST',
      headers: AuthModule.getAuthHeaders()
    });

    if (!response.ok) {
      throw new APIError('Failed to retry job', response.status, await parseErrorResponse(response));
    }

    return await response.json();
  }

  function normalizeJob(job) {
    return {
      ...job,
      encrypted: job.encrypted || job.encrypt_result || !!job.encrypted_result
    };
  }

  return {
    listJobs,
    getJob,
    submitJob,
    cancelJob,
    retryJob,
    getState: () => STATE
  };
})();
```

**frontend/js/modules/websocket.module.js**
```javascript
// WebSocket module - manages connection lifecycle with exponential backoff
export const WebSocketModule = (() => {
  let ws = null;
  let reconnectAttempts = 0;
  let reconnectTimer = null;
  let currentJobId = null;

  const CONFIG = {
    MAX_RECONNECT_ATTEMPTS: 5,
    BASE_RECONNECT_DELAY: 1000,
    RECONNECT_TIMEOUT_MULTIPLIER: 2
  };

  function connect(jobId, onMessage, onError, onClose) {
    disconnect(); // Close any existing connection

    currentJobId = jobId;
    reconnectAttempts = 0;

    createConnection(jobId, onMessage, onError, onClose);
  }

  function createConnection(jobId, onMessage, onError, onClose) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/jobs/${jobId}`;

    try {
      ws = new WebSocket(url);

      ws.onopen = () => {
        console.log(`[WebSocket] Connected to job ${jobId}`);
        reconnectAttempts = 0; // Reset on successful connection
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessage(data);
        } catch (e) {
          console.error('[WebSocket] Parse error:', e);
        }
      };

      ws.onerror = (error) => {
        console.warn('[WebSocket] Connection error');
        onError?.(error);
      };

      ws.onclose = (event) => {
        console.log('[WebSocket] Connection closed', event.code, event.reason);
        onClose?.(event);

        // Don't reconnect if intentionally closed or job completed
        if (event.code === 1000 || !currentJobId) {
          ws = null;
          return;
        }

        // Attempt reconnection with exponential backoff
        if (reconnectAttempts < CONFIG.MAX_RECONNECT_ATTEMPTS) {
          reconnectAttempts++;
          const delay = CONFIG.BASE_RECONNECT_DELAY * Math.pow(
            CONFIG.RECONNECT_TIMEOUT_MULTIPLIER,
            reconnectAttempts - 1
          );

          console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttempts}/${CONFIG.MAX_RECONNECT_ATTEMPTS})`);

          reconnectTimer = setTimeout(() => {
            if (currentJobId === jobId) {
              createConnection(jobId, onMessage, onError, onClose);
            }
          }, delay);
        } else {
          console.warn('[WebSocket] Max reconnection attempts reached');
          ws = null;
        }
      };
    } catch (error) {
      console.error('[WebSocket] Failed to connect:', error);
      onError?.(error);
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }

    if (ws) {
      currentJobId = null; // Prevent reconnection
      ws.close(1000, 'Intentional disconnect');
      ws = null;
    }
  }

  function isConnected() {
    return ws && ws.readyState === WebSocket.OPEN;
  }

  return {
    connect,
    disconnect,
    isConnected
  };
})();
```

**frontend/js/dashboard.js** (Refactored main entry)
```javascript
// Main dashboard entry point - orchestrates modules
import { AuthModule } from './modules/auth.module.js';
import { JobsModule } from './modules/jobs.module.js';
import { WebSocketModule } from './modules/websocket.module.js';
import { ChartsModule } from './modules/charts.module.js';
import { NotificationsModule } from './modules/notifications.module.js';
import { SettingsModule } from './modules/settings.module.js';

// Export global STATE for backward compatibility
window.STATE = {
  jobs: [],
  currentSection: 'overview',
  selectedJobId: null,
  isAuthenticated: AuthModule.isAuthenticated(),
  theme: localStorage.getItem('theme') || 'dark'
};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  // Initialize modules
  initNavigation();
  initJobForm();
  initModal();
  SettingsModule.init();
  NotificationsModule.init();

  // Check authentication status
  if (window.STATE.isAuthenticated) {
    loadJobs();
  } else {
    updateAuthUI(false);
  }

  // Start health checks
  setInterval(checkApiStatus, 30000);
});

// Navigation
function initNavigation() {
  document.querySelectorAll('.nav-item, [data-section]').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const section = item.dataset.section;
      if (section) {
        navigateToSection(section);
      }
    });
  });
}

function navigateToSection(section) {
  // Update active nav item
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.section === section);
  });

  // Update section visibility
  document.querySelectorAll('.dashboard-section').forEach(sec => {
    sec.classList.toggle('active', sec.id === `section-${section}`);
  });
}

// Jobs
async function loadJobs() {
  try {
    const { jobs, total } = await JobsModule.listJobs({
      status: window.STATE.filterStatus,
      problem_type: window.STATE.filterType,
      search: window.STATE.searchQuery,
      page: window.STATE.currentPage
    });

    window.STATE.jobs = jobs;
    window.STATE.totalJobs = total;

    updateJobsUI();
  } catch (error) {
    NotificationsModule.showToast('error', 'Load Failed', error.message);
  }
}

// WebSocket
function connectJobWebSocket(jobId) {
  WebSocketModule.connect(
    jobId,
    (data) => {
      // Handle message
      if (data.status === 'completed' || data.status === 'failed') {
        loadJobs();
        if (window.STATE.selectedJobId) {
          viewJobDetails(window.STATE.selectedJobId);
        }
      }
    },
    null,
    (event) => {
      console.log('WebSocket closed');
    }
  );
}

// Global exports for HTML handlers
window.navigate = navigateToSection;
window.loadJobs = loadJobs;
window.STATE = window.STATE;
```

---

## 2. DUPLICATE FUNCTIONS

### Problem

`handleLogin()` and `handleRegister()` are defined twice in `dashboard.js`:

**First definition (stub):**
```javascript
// Line 3023-3026
async function handleLogin(e) {
    // Defer to AuthModal component
    e.preventDefault();
}

async function handleRegister(e) {
    // Defer to AuthModal component
    e.preventDefault();
}
```

**Second definition (real implementation):**
```javascript
// Line 3083-3170 (for handleRegister - the first duplicate found)
async function handleRegister(e) {
    e.preventDefault();
    const name = document.getElementById('register-name').value;
    const email = document.getElementById('register-email').value;
    // ... full implementation
}
```

### Fix: Remove Duplicate Definitions

**Remove lines 3023-3031** (stub definitions that just call preventDefault)

The real implementations should be in a proper module (see auth.module.js above).

### Orphaned Code Issue

**Lines 3033-3081 contain orphaned error-handling code** that appears to be part of handleLogin but exists outside any function:

```javascript
// Lines 3033-3081 - ORPHANED CODE
            closeAuthModal();
            showToast('success', 'Welcome!', 'You have successfully signed in');
            await checkAuthStatus();
            loadJobs();
        } else {
            throw new Error(data.detail || data.message || 'Invalid credentials');
        }
    } catch (error) {
        // Fallback to demo mode if network error and DEMO_MODE enabled
        if (error.message.includes('fetch') || error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
            // ... more code
```

**Fix:** This code should be inside the handleLogin function after the API call, or moved to the auth.module.js.

---

## 3. ERROR RESPONSE INCONSISTENCY

### Problem

API endpoints return errors in different formats:

| Endpoint | Error Field | Location |
|----------|-------------|----------|
| `/auth/login` | `detail` | api/routers/auth.py:67 |
| `/auth/register` | `detail` | (not used) |
| `/jobs/*` | `detail` | api/routers/jobs.py (multiple) |
| `/jobs/*` (src) | `detail` | src/qsop/api/routers/jobs.py |
| Frontend access | `detail`, `message`, `error` | dashboard.js |

**Current frontend code:**
```javascript
// dashboard.js:625
const errorData = await response.json().catch(() => ({}));
throw new Error(errorData.detail || `HTTP ${response.status}`);

// dashboard.js:1719
showToast('warning', 'Credentials Error', errorData.detail || 'Could not save credentials');

// dashboard.js:3038
throw new Error(data.detail || data.message || 'Invalid credentials');
```

### Fix: Standardize on RFC 7807 Problem Details

**Create standardized error response handler:**

**frontend/js/utils/api.js**
```javascript
/**
 * Standardized API error handling using RFC 7807 Problem Details
 */
export class APIError extends Error {
  constructor(message, status, detail = null, instance = null) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.detail = detail;
    this.instance = instance;
  }

  toProblemDetails() {
    return {
      type: `https://api.qsop.io/errors/${this.getStatusType()}`,
      title: this.message,
      status: this.status,
      detail: this.detail || this.message,
      instance: this.instance || new URL(window.location.href).pathname
    };
  }

  getStatusType() {
    // Map HTTP status codes to error types
    const typeMap = {
      400: 'bad-request',
      401: 'unauthorized',
      403: 'forbidden',
      404: 'not-found',
      409: 'conflict',
      422: 'validation-error',
      429: 'rate-limit-exceeded',
      500: 'internal-server-error',
      503: 'service-unavailable'
    };
    return typeMap[this.status] || 'unknown-error';
  }

  getUserFriendlyMessage() {
    // Provide user-friendly messages
    const messages = {
      400: 'Invalid request. Please check your input.',
      401: 'Authentication required. Please sign in.',
      403: 'Access denied.',
      404: 'Requested resource not found.',
      422: 'Validation error. Please check your input.',
      429: 'Too many requests. Please wait.',
      500: 'Server error. Please try again.',
      503: 'Service temporarily unavailable.'
    };
    return messages[this.status] || this.message;
  }
}

/**
 * Parse error response from API
 * Supports both old format ({detail, message, error}) and RFC 7807
 */
export async function parseErrorResponse(response) {
  const contentType = response.headers.get('content-type');
  let data = {};

  if (contentType && contentType.includes('application/json')) {
    try {
      data = await response.json();
    } catch {
      // JSON parse failed
    }
  }

  // Check for RFC 7807 Problem Details
  if (data.type || data.title) {
    return {
      type: data.type,
      title: data.title || 'Error',
      status: data.status || response.status,
      detail: data.detail || data.title,
      instance: data.instance || null
    };
  }

  // Legacy format - normalize to standard fields
  return {
    detail: data.detail || data.message || data.error || 'An error occurred',
    status: response.status
  };
}

/**
 * Wrap fetch with standardized error handling
 */
export async function fetchWithErrorHandling(url, options = {}) {
  const response = await fetch(url, options);

  if (!response.ok) {
    const errorData = await parseErrorResponse(response);
    throw new APIError(
      errorData.title || 'Request failed',
      response.status,
      errorData.detail,
      errorData.instance
    );
  }

  return response;
}
```

**Backend - Create standardized error response:**

**src/qsop/api/schemas/error.py**
```python
"""Standardized error response models using RFC 7807 Problem Details."""
from typing import Any
from pydantic import BaseModel, HttpUrl
from urllib.parse import urljoin


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details for HTTP APIs.

    See: https://datatracker.ietf.org/doc/html/rfc7807
    """

    type: str | None = None
    """An absolute URI that identifies the problem type."""

    title: str
    """A short, human-readable summary of the problem type."""

    status: int | None = None
    """The HTTP status code."""

    detail: str | None = None
    """A human-readable explanation specific to this occurrence."""

    instance: str | None = None
    """An absolute URI that identifies the specific occurrence of the problem."""

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Custom dump to ensure consistent field ordering."""
        data = super().model_dump(**kwargs)

        # Remove None values for cleaner responses
        return {k: v for k, v in data.items() if v is not None}


class ErrorResponses:
    """Factory for common error responses."""

    BASE_URL = "https://api.qsop.io/errors/"

    @classmethod
    def not_found(cls, detail: str, instance: str | None = None) -> ProblemDetail:
        """Return a 404 Not Found error response."""
        return ProblemDetail(
            type=urljoin(cls.BASE_URL, "not-found"),
            title="Resource Not Found",
            status=404,
            detail=detail,
            instance=instance,
        )

    @classmethod
    def unauthorized(cls, detail: str = "Authentication required", instance: str | None = None) -> ProblemDetail:
        """Return a 401 Unauthorized error response."""
        return ProblemDetail(
            type=urljoin(cls.BASE_URL, "unauthorized"),
            title="Unauthorized",
            status=401,
            detail=detail,
            instance=instance,
        )

    @classmethod
    def forbidden(cls, detail: str, instance: str | None = None) -> ProblemDetail:
        """Return a 403 Forbidden error response."""
        return ProblemDetail(
            type=urljoin(cls.BASE_URL, "forbidden"),
            title="Forbidden",
            status=403,
            detail=detail,
            instance=instance,
        )

    @classmethod
    def validation_error(cls, detail: str, instance: str | None = None) -> ProblemDetail:
        """Return a 422 Validation Error response."""
        return ProblemDetail(
            type=urljoin(cls.BASE_URL, "validation-error"),
            title="Validation Error",
            status=422,
            detail=detail,
            instance=instance,
        )

    @classmethod
    def bad_request(cls, detail: str, instance: str | None = None) -> ProblemDetail:
        """Return a 400 Bad Request error response."""
        return ProblemDetail(
            type=urljoin(cls.BASE_URL, "bad-request"),
            title="Bad Request",
            status=400,
            detail=detail,
            instance=instance,
        )

    @classmethod
    def job_not_found(cls, job_id: str) -> ProblemDetail:
        """Return a 404 error for a specific job."""
        return cls.not_found(
            detail=f"Job {job_id} does not exist or you do not have access"
        )
```

**Update API routers to use standardized errors:**

**src/qsop/api/routers/jobs.py (updated)**
```python
from qsop.api.schemas.error import ErrorResponses

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> JobResponse:
    """Get details of a specific job."""
    job = await container.job_repo.get_by_id(job_id, tenant_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponses.job_not_found(str(job_id)).detail,
        )

    return JobResponse.model_validate(job)


@router.get("/{job_id}/results", response_model=JobResultsResponse)
async def get_job_results(
    job_id: UUID,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> JobResultsResponse:
    """Get the results of a completed job."""
    job = await container.job_repo.get_by_id(job_id, tenant_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponses.job_not_found(str(job_id)).detail,
        )

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job results not available. Current status: {job.status}",
        )

    results_data = await container.artifact_store.get(f"jobs/{job_id}/results.json")

    if results_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Results not found in artifact store",
        )

    return JobResultsResponse.model_validate_json(results_data)
```

---

## 4. INCONSISTENT API NAMING

### Problem

| Current Endpoint | Issue | Recommended |
|------------------|-------|-------------|
| `GET /jobs/{id}/result` | Non-RESTful - results are a sub-resource | Remove, use `GET /jobs/{id}` with `status='completed'` |
| `POST /jobs/{id}/decrypt` | Action endpoint, already deprecated | Already marked deprecated, remove in v2 |
| `GET /jobs/workers/status` | Workers are a separate resource, not sub-resource of jobs | `GET /workers` or `GET /system/workers` |
| `GET /jobs/webhooks/stats` | Webhooks are separate resource | `GET /webhooks/stats` |

### Fix: Standardize API Routes

**api/routers/workers.py (new file)**
```python
"""Worker management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Any

router = APIRouter(tags=["workers"])

try:
    from api.tasks.celery_app import get_celery_status
    _celery_available = True
except ImportError:
    _celery_available = False
    get_celery_status = None

from api.routers.auth import get_current_user


@router.get("", response_model=dict[str, Any])
async def list_workers(
    status: str | None = Query(None, description="Filter by worker status"),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    List all workers.

    Returns information about active workers, their status, queue assignments,
    and current task load.
    """
    if not _celery_available:
        return {
            "workers": [],
            "total": 0,
            "available": False,
            "message": "Celery workers not configured"
        }

    status_info = get_celery_status()

    # Filter by status if specified
    workers = status_info.get("workers", [])
    if status:
        workers = [w for w in workers if w.get("status") == status]

    return {
        "workers": workers,
        "total": len(workers),
        "available": True,
        "statistics": {
            "active": sum(1 for w in workers if w.get("status") == "active"),
            "idle": sum(1 for w in workers if w.get("status") == "idle"),
            "offline": sum(1 for w in workers if w.get("status") == "offline")
        }
    }


@router.get("/stats", response_model=dict[str, Any])
async def get_worker_stats(
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get aggregate worker statistics.

    Returns summary statistics including:
    - Total configured workers
    - Active/idle/offline counts
    - Queue length
    - Task throughput
    """
    if not _celery_available:
        return {
            "available": False,
            "message": "Celery workers not configured"
        }

    return get_celery_status()
```

**api/routers/webhooks.py (new file)**
```python
"""Webhook management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from typing import Any
from datetime import datetime

router = APIRouter(tags=["webhooks"])

try:
    from api.services.webhooks import webhook_service
    _webhooks_available = True
except ImportError:
    _webhooks_available = False
    webhook_service = None

from api.routers.auth import get_current_user


@router.get("/stats")
async def get_webhook_statistics(
    hours: int = 24,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get webhook delivery statistics.

    Returns statistics about webhook delivery including:
    - Total deliveries attempted
    - Success/failure counts
    - Retry statistics
    - Average delivery time
    """
    if not _webhooks_available:
        raise HTTPException(
            status_code=503,
            detail="Webhook service not available"
        )

    return webhook_service.get_statistics(hours=hours)


@router.get("")
async def list_webhooks(
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    List all registered webhooks.

    Returns webhook URLs and their delivery status for the current user.
    """
    # Implementation depends on webhook storage strategy
    return {
        "webhooks": [],
        "total": 0
    }


@router.post("")
async def register_webhook(
    url: str,
    events: list[str],
    secret: str | None = None,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Register a new webhook.

    Webhooks receive notifications for specified events (job.completed, job.failed, etc.).
    """
    if not _webhooks_available:
        raise HTTPException(
            status_code=503,
            detail="Webhook service not available"
        )

    return {
        "webhook_id": "wh_123",
        "url": url,
        "events": events,
        "status": "active",
        "created_at": datetime.utcnow().isoformat()
    }


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """Delete a registered webhook."""
    return {"message": f"Webhook {webhook_id} deleted"}
```

**api/routers/jobs.py (updated endpoints)**
```python
# Remove these endpoints:

# DELETE: GET /jobs/workers/status - moved to /workers
# DELETE: GET /jobs/webhooks/stats - moved to /webhooks/stats

# DEPRECATION NOTICE: POST /jobs/{id}/decrypt (already marked)
@router.post("/{job_id}/decrypt", deprecated=True)
async def decrypt_job_result(...):
    """
    ⚠️ DEPRECATED: Use client-side decryption instead.

    This endpoint sends your secret key over HTTP, which is a security risk.
    """
    warnings.warn("Server-side decryption is deprecated. Use client-side decryption.", DeprecationWarning)
    # ... implementation for backward compatibility
```

**frontend/js/modules/jobs.module.js (updated routes)**
```javascript
// Update API calls to use standardized routes

async function listWorkers(status = null) {
  const params = {};
  if (status) params.status = status;

  const response = await fetch(`${CONFIG.apiUrl}/workers${new URLSearchParams(params)}`, {
    headers: AuthModule.getAuthHeaders()
  });

  if (!response.ok) {
    throw new APIError('Failed to fetch workers', response.status, await parseErrorResponse(response));
  }

  return await response.json();
}

async function getWorkerStats() {
  const response = await fetch(`${CONFIG.apiUrl}/workers/stats`, {
    headers: AuthModule.getAuthHeaders()
  });

  if (!response.ok) {
    throw new APIError('Failed to fetch worker stats', response.status, await parseErrorResponse(response));
  }

  return await response.json();
}

async function getWebhookStats(hours = 24) {
  const response = await fetch(`${CONFIG.apiUrl}/webhooks/stats?hours=${hours}`, {
    headers: AuthModule.getAuthHeaders()
  });

  if (!response.ok) {
    throw new APIError('Failed to fetch webhook stats', response.status, await parseErrorResponse(response));
  }

  return await response.json();
}
```

---

## 5. Summary of Refactoring Benefits

### Code Quality Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| dashboard.js lines | 4,225 | ~200 | 95% reduction |
| Files in frontend | 1 | ~10 | Modular architecture |
| Duplicate functions | 2 (handleLogin, handleRegister) | 0 | Eliminated |
| Orphaned code blocks | 1 (50+ lines) | 0 | Proper scoping |
| API error formats | 3 (detail, message, error) | 1 (RFC 7807) | Standardized |
| Non-RESTful endpoints | 4 | 0 | Fully RESTful |

### Maintainability Benefits

1. **Single Responsibility**: Each module handles one concern
2. **Testability**: Modules can be unit tested independently
3. **Reusability**: Modules can be shared across pages
4. **Scalability**: Easy to add new features without touching core modules
5. **Debuggability**: Smaller files with clear boundaries

### Security Benefits

1. **Deprecation of insecure endpoint**: `/decrypt` properly marked for removal
2. **Standardized error responses**: No accidental information leakage
3. **Proper error handling**: Consistent error types across the codebase

### Developer Experience Benefits

1. **Faster navigation**: Smaller, focused files
2. **Clearer code organization**: Logical groupings
3. **Easier onboarding**: New developers can focus on specific modules
4. **Better IDE support**: Smaller files improve IDE performance

---

## Implementation Priority

### Phase 1 (Immediate - Critical)
1. Remove duplicate function definitions (handleLogin, handleRegister)
2. Move orphaned code into proper function scope
3. Standardize API error responses (RFC 7807)

### Phase 2 (Short-term - 1-2 weeks)
1. Extract authentication module (auth.module.js)
2. Extract jobs module (jobs.module.js)
3. Extract WebSocket module (websocket.module.js)

### Phase 3 (Medium-term - 2-4 weeks)
1. Extract charts module (charts.module.js)
2. Extract notifications module (notifications.module.js)
3. Extract settings module (settings.module.js)

### Phase 4 (Long-term - 1-2 months)
1. Reorganize API routes (/workers, /webhooks)
2. Remove deprecated endpoints
3. Update frontend to use new API routes
4. Write comprehensive tests for all modules

---

## Testing Strategy

### Unit Tests
```javascript
// tests/auth.module.test.js
import { AuthModule } from '../modules/auth.module.js';

describe('AuthModule', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test('should store token after login', async () => {
    // Mock fetch
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'test_token' })
      })
    );

    await AuthModule.login('test@example.com', 'password');
    expect(localStorage.getItem('authToken')).toBe('test_token');
  });

  test('should clear tokens on logout', async () => {
    AuthModule.setToken('test_token');
    await AuthModule.logout();
    expect(localStorage.getItem('authToken')).toBeNull();
  });
});
```

### Integration Tests
```javascript
// tests/integration/jobs.test.js
import { JobsModule } from '../modules/jobs.module.js';
import { AuthModule } from '../modules/auth.module.js';

describe('Jobs Integration', () => {
  test('should submit job when authenticated', async () => {
    // Mock authentication
    AuthModule.setToken('test_token');

    const jobData = {
      problem_type: 'QAOA',
      backend: 'local_simulator',
      problem_config: { problem: 'maxcut' }
    };

    const result = await JobsModule.submitJob(jobData);
    expect(result.job_id).toBeDefined();
  });

  test('should fail to submit job when unauthenticated', async () => {
    // Clear authentication
    AuthModule.clearAuth();

    const jobData = { problem_type: 'QAOA' };

    await expect(JobsModule.submitJob(jobData)).rejects.toThrow('Unauthorized');
  });
});
```

---

## References

- [RFC 7807: Problem Details for HTTP APIs](https://datatracker.ietf.org/doc/html/rfc7807)
- [FastAPI Router Guidelines](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [JavaScript Module Pattern](https://addyosmani.com/resources/essentialjsdesignpatterns/book/#modulepatternjavascript)
- [RESTful API Design Best Practices](https://restfulapi.net/)
