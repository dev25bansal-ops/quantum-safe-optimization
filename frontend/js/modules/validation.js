/**
 * Validation Module
 * Form validation, input sanitization, and validation feedback
 */

import { showToast } from './toast.js';

// Validation rules configuration
const ValidationRules = {
    required: {
        validate: (value) => value !== null && value !== undefined && value.toString().trim() !== '',
        message: 'This field is required'
    },
    email: {
        validate: (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
        message: 'Please enter a valid email address'
    },
    minLength: (min) => ({
        validate: (value) => value.length >= min,
        message: `Must be at least ${min} characters`
    }),
    maxLength: (max) => ({
        validate: (value) => value.length <= max,
        message: `Must be no more than ${max} characters`
    }),
    pattern: (regex, msg) => ({
        validate: (value) => regex.test(value),
        message: msg || 'Invalid format'
    }),
    numeric: {
        validate: (value) => !isNaN(parseFloat(value)) && isFinite(value),
        message: 'Must be a valid number'
    },
    integer: {
        validate: (value) => Number.isInteger(Number(value)),
        message: 'Must be a whole number'
    },
    positiveNumber: {
        validate: (value) => !isNaN(parseFloat(value)) && parseFloat(value) > 0,
        message: 'Must be a positive number'
    },
    range: (min, max) => ({
        validate: (value) => {
            const num = parseFloat(value);
            return !isNaN(num) && num >= min && num <= max;
        },
        message: `Must be between ${min} and ${max}`
    }),
    json: {
        validate: (value) => {
            try {
                JSON.parse(value);
                return true;
            } catch {
                return false;
            }
        },
        message: 'Must be valid JSON'
    },
    alphanumeric: {
        validate: (value) => /^[a-zA-Z0-9]+$/.test(value),
        message: 'Only letters and numbers allowed'
    },
    noSpecialChars: {
        validate: (value) => /^[a-zA-Z0-9\s\-_]+$/.test(value),
        message: 'Special characters are not allowed'
    }
};

// Field validation state
const validationState = new Map();

/**
 * Validate a single field
 * @param {HTMLElement} field - Input element to validate
 * @param {Array} rules - Array of validation rules
 * @returns {Object} - { valid: boolean, errors: string[] }
 */
export function validateField(field, rules) {
    const value = field.value;
    const errors = [];

    for (const rule of rules) {
        let ruleConfig;

        if (typeof rule === 'string') {
            ruleConfig = ValidationRules[rule];
        } else if (typeof rule === 'object' && rule.name) {
            ruleConfig = typeof ValidationRules[rule.name] === 'function'
                ? ValidationRules[rule.name](...(rule.params || []))
                : ValidationRules[rule.name];
        } else if (typeof rule === 'object') {
            ruleConfig = rule;
        }

        if (ruleConfig && !ruleConfig.validate(value)) {
            errors.push(ruleConfig.message);
        }
    }

    const result = { valid: errors.length === 0, errors };

    // Store validation state
    validationState.set(field.id || field.name, result);

    // Update visual feedback
    updateFieldFeedback(field, result);

    return result;
}

/**
 * Validate an entire form
 * @param {HTMLFormElement} form - Form element
 * @param {Object} fieldRules - Object mapping field names to rule arrays
 * @returns {Object} - { valid: boolean, errors: Object }
 */
export function validateForm(form, fieldRules) {
    const allErrors = {};
    let isValid = true;

    for (const [fieldName, rules] of Object.entries(fieldRules)) {
        const field = form.querySelector(`[name="${fieldName}"], #${fieldName}`);
        if (!field) continue;

        const result = validateField(field, rules);
        if (!result.valid) {
            isValid = false;
            allErrors[fieldName] = result.errors;
        }
    }

    return { valid: isValid, errors: allErrors };
}

/**
 * Update visual feedback on field
 */
function updateFieldFeedback(field, result) {
    // Remove existing feedback
    field.classList.remove('is-valid', 'is-invalid');

    // Find or create feedback element
    let feedback = field.parentElement.querySelector('.validation-feedback');
    if (!feedback) {
        feedback = document.createElement('div');
        feedback.className = 'validation-feedback';
        field.parentElement.appendChild(feedback);
    }

    if (result.valid) {
        field.classList.add('is-valid');
        feedback.textContent = '';
        feedback.className = 'validation-feedback valid';
    } else {
        field.classList.add('is-invalid');
        feedback.textContent = result.errors[0]; // Show first error
        feedback.className = 'validation-feedback invalid';
    }
}

/**
 * Clear validation state and UI for a form
 */
export function clearValidation(form) {
    const fields = form.querySelectorAll('input, select, textarea');
    fields.forEach(field => {
        field.classList.remove('is-valid', 'is-invalid');
        const feedback = field.parentElement.querySelector('.validation-feedback');
        if (feedback) feedback.remove();
        validationState.delete(field.id || field.name);
    });
}

/**
 * Sanitize input - remove potentially dangerous content
 */
export function sanitize(input) {
    if (typeof input !== 'string') return input;

    // Remove HTML tags
    let sanitized = input.replace(/<[^>]*>/g, '');

    // Escape special characters
    const escapeChars = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    sanitized = sanitized.replace(/[&<>"']/g, char => escapeChars[char]);

    return sanitized;
}

/**
 * Sanitize object recursively
 */
export function sanitizeObject(obj) {
    if (typeof obj === 'string') return sanitize(obj);
    if (Array.isArray(obj)) return obj.map(item => sanitizeObject(item));
    if (typeof obj === 'object' && obj !== null) {
        const result = {};
        for (const [key, value] of Object.entries(obj)) {
            result[sanitize(key)] = sanitizeObject(value);
        }
        return result;
    }
    return obj;
}

/**
 * Validate JSON string
 */
export function validateJSON(jsonString) {
    try {
        const parsed = JSON.parse(jsonString);
        return { valid: true, data: parsed, error: null };
    } catch (error) {
        return { valid: false, data: null, error: error.message };
    }
}

/**
 * Validate job configuration
 */
export function validateJobConfig(config) {
    const errors = [];

    // Problem type validation
    if (!config.problem_type) {
        errors.push('Problem type is required');
    }

    // Backend validation
    if (!config.backend) {
        errors.push('Backend is required');
    }

    // Type-specific validation
    switch (config.problem_type) {
        case 'QAOA':
            if (!config.problem_config?.graph || config.problem_config.graph.length === 0) {
                errors.push('QAOA requires a graph configuration');
            }
            if (config.problem_config?.p_layers !== undefined) {
                if (config.problem_config.p_layers < 1 || config.problem_config.p_layers > 20) {
                    errors.push('P-layers must be between 1 and 20');
                }
            }
            break;

        case 'VQE':
            if (!config.problem_config?.molecule) {
                errors.push('VQE requires a molecule configuration');
            }
            break;
    }

    // Shots validation
    if (config.problem_config?.shots !== undefined) {
        if (config.problem_config.shots < 100 || config.problem_config.shots > 100000) {
            errors.push('Shots must be between 100 and 100,000');
        }
    }

    return { valid: errors.length === 0, errors };
}

/**
 * Create realtime validation on a field
 */
export function enableRealtimeValidation(field, rules, debounceMs = 300) {
    let timeout;

    const validate = () => {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            validateField(field, rules);
        }, debounceMs);
    };

    field.addEventListener('input', validate);
    field.addEventListener('blur', () => {
        clearTimeout(timeout);
        validateField(field, rules);
    });

    // Return cleanup function
    return () => {
        field.removeEventListener('input', validate);
        field.removeEventListener('blur', validate);
    };
}

/**
 * Initialize validation for auth forms
 */
export function initAuthValidation() {
    // Sign in form
    const signinEmail = document.getElementById('signin-email');
    const signinPassword = document.getElementById('signin-password');

    if (signinEmail) {
        enableRealtimeValidation(signinEmail, ['required', 'email']);
    }
    if (signinPassword) {
        enableRealtimeValidation(signinPassword, ['required', { name: 'minLength', params: [6] }]);
    }

    // Sign up form
    const signupEmail = document.getElementById('signup-email');
    const signupUsername = document.getElementById('signup-username');
    const signupPassword = document.getElementById('signup-password');

    if (signupEmail) {
        enableRealtimeValidation(signupEmail, ['required', 'email']);
    }
    if (signupUsername) {
        enableRealtimeValidation(signupUsername, ['required', { name: 'minLength', params: [3] }, 'noSpecialChars']);
    }
    if (signupPassword) {
        enableRealtimeValidation(signupPassword, ['required', { name: 'minLength', params: [8] }]);
    }
}

/**
 * Validate before form submit
 */
export function validateOnSubmit(form, fieldRules, onValid) {
    form.addEventListener('submit', (e) => {
        e.preventDefault();

        const result = validateForm(form, fieldRules);

        if (result.valid) {
            onValid(form);
        } else {
            const firstError = Object.values(result.errors)[0]?.[0];
            showToast('warning', 'Validation Error', firstError || 'Please check your input');

            // Focus first invalid field
            const firstInvalid = form.querySelector('.is-invalid');
            if (firstInvalid) firstInvalid.focus();
        }
    });
}

// Export validation rules for external use
export { ValidationRules };
