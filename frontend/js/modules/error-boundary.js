/**
 * Error Boundary Module
 * Global error handling, logging, and user-friendly error display
 */

import { showToast } from './toast.js';
import { addNotification } from './notifications.js';
import { STATE } from './config.js';

// Error log storage (in-memory, limited size)
const errorLog = [];
const MAX_ERROR_LOG_SIZE = 50;

// Error types for categorization
const ErrorTypes = {
    NETWORK: 'network',
    VALIDATION: 'validation',
    API: 'api',
    RUNTIME: 'runtime',
    SECURITY: 'security',
    UNKNOWN: 'unknown'
};

/**
 * Initialize global error handlers
 */
export function initErrorBoundary() {
    // Global error handler
    window.onerror = function (message, source, lineno, colno, error) {
        handleError({
            type: ErrorTypes.RUNTIME,
            message: message,
            source: source,
            line: lineno,
            column: colno,
            stack: error?.stack,
            timestamp: new Date().toISOString()
        });

        // Return true to prevent default browser error handling
        return true;
    };

    // Unhandled promise rejection handler
    window.addEventListener('unhandledrejection', function (event) {
        const error = event.reason;
        handleError({
            type: ErrorTypes.RUNTIME,
            message: error?.message || 'Unhandled Promise Rejection',
            stack: error?.stack,
            timestamp: new Date().toISOString()
        });

        // Prevent default handling
        event.preventDefault();
    });

    console.log('[ErrorBoundary] Global error handlers initialized');
}

/**
 * Central error handler
 */
export function handleError(errorInfo) {
    // Categorize error
    const categorizedError = categorizeError(errorInfo);

    // Log error
    logError(categorizedError);

    // Display user-friendly message
    displayErrorToUser(categorizedError);

    // Optional: Send to error reporting service
    // reportError(categorizedError);

    return categorizedError;
}

/**
 * Categorize error by type
 */
function categorizeError(errorInfo) {
    const message = (errorInfo.message || '').toLowerCase();

    let type = ErrorTypes.UNKNOWN;

    if (message.includes('fetch') || message.includes('network') ||
        message.includes('failed to fetch') || message.includes('cors')) {
        type = ErrorTypes.NETWORK;
    } else if (message.includes('invalid') || message.includes('validation') ||
        message.includes('required') || message.includes('format')) {
        type = ErrorTypes.VALIDATION;
    } else if (message.includes('401') || message.includes('403') ||
        message.includes('500') || message.includes('api')) {
        type = ErrorTypes.API;
    } else if (message.includes('security') || message.includes('permission') ||
        message.includes('unauthorized')) {
        type = ErrorTypes.SECURITY;
    } else if (errorInfo.type) {
        type = errorInfo.type;
    }

    return {
        ...errorInfo,
        type,
        id: generateErrorId()
    };
}

/**
 * Log error to in-memory storage
 */
function logError(error) {
    // Add to log
    errorLog.unshift(error);

    // Trim to max size
    if (errorLog.length > MAX_ERROR_LOG_SIZE) {
        errorLog.pop();
    }

    // Console log for debugging
    console.error(`[ErrorBoundary][${error.type}]`, error.message, error);
}

/**
 * Display user-friendly error message
 */
function displayErrorToUser(error) {
    const friendlyMessages = {
        [ErrorTypes.NETWORK]: {
            title: 'Connection Issue',
            message: 'Unable to connect to the server. Please check your internet connection.'
        },
        [ErrorTypes.VALIDATION]: {
            title: 'Validation Error',
            message: error.message || 'Please check your input and try again.'
        },
        [ErrorTypes.API]: {
            title: 'Server Error',
            message: 'The server encountered an error. Please try again later.'
        },
        [ErrorTypes.SECURITY]: {
            title: 'Security Error',
            message: 'A security issue was detected. Please sign in again.'
        },
        [ErrorTypes.RUNTIME]: {
            title: 'Application Error',
            message: 'Something went wrong. The error has been logged.'
        },
        [ErrorTypes.UNKNOWN]: {
            title: 'Error',
            message: 'An unexpected error occurred.'
        }
    };

    const display = friendlyMessages[error.type] || friendlyMessages[ErrorTypes.UNKNOWN];

    // Don't show toast for every error - only if it's significant
    if (shouldShowToast(error)) {
        showToast('error', display.title, display.message);
    }

    // Add to notification center for tracking
    addNotification('error', display.title, `${display.message} (ID: ${error.id})`);
}

/**
 * Determine if error should show a toast
 */
function shouldShowToast(error) {
    // Don't spam toasts for repeated errors
    const recentError = errorLog.find((e, i) =>
        i > 0 && e.message === error.message &&
        (new Date(error.timestamp) - new Date(e.timestamp)) < 5000
    );

    if (recentError) return false;

    // Always show security errors
    if (error.type === ErrorTypes.SECURITY) return true;

    // Don't show network errors in demo mode
    if (error.type === ErrorTypes.NETWORK && !STATE.isAuthenticated) return false;

    return true;
}

/**
 * Generate unique error ID for tracking
 */
function generateErrorId() {
    return 'ERR-' + Date.now().toString(36).toUpperCase();
}

/**
 * Get recent errors for debugging
 */
export function getErrorLog() {
    return [...errorLog];
}

/**
 * Clear error log
 */
export function clearErrorLog() {
    errorLog.length = 0;
}

/**
 * Try-catch wrapper for async functions
 */
export async function safeAsync(fn, fallback = null, context = '') {
    try {
        return await fn();
    } catch (error) {
        handleError({
            message: error.message,
            stack: error.stack,
            context,
            timestamp: new Date().toISOString()
        });
        return fallback;
    }
}

/**
 * Try-catch wrapper for sync functions
 */
export function safeSync(fn, fallback = null, context = '') {
    try {
        return fn();
    } catch (error) {
        handleError({
            message: error.message,
            stack: error.stack,
            context,
            timestamp: new Date().toISOString()
        });
        return fallback;
    }
}

/**
 * Create an error boundary wrapper for DOM operations
 */
export function withErrorBoundary(elementId, operation) {
    return function (...args) {
        try {
            return operation(...args);
        } catch (error) {
            handleError({
                message: error.message,
                stack: error.stack,
                context: `DOM operation on #${elementId}`,
                timestamp: new Date().toISOString()
            });

            // Try to show error state in the element
            const element = document.getElementById(elementId);
            if (element) {
                element.innerHTML = `
                    <div class="error-boundary-fallback">
                        <i class="fas fa-exclamation-circle"></i>
                        <p>Something went wrong loading this section.</p>
                        <button class="btn btn-sm" onclick="location.reload()">Reload</button>
                    </div>
                `;
            }
        }
    };
}

// Export error types for external use
export { ErrorTypes };

// Make functions globally accessible for console debugging
window.getErrorLog = getErrorLog;
window.clearErrorLog = clearErrorLog;
