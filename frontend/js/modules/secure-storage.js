/**
 * Secure Token Storage Module
 * Provides secure storage abstraction for authentication tokens
 * with configurable persistence (session vs persistent storage)
 */

// Storage keys
const TOKEN_KEY = 'authToken';
const USER_KEY = 'quantumSafeUser';
const REMEMBER_ME_KEY = 'rememberMe';

/**
 * Determines which storage to use based on user preference
 * @returns {Storage} sessionStorage or localStorage
 */
function getStorage() {
    // Use sessionStorage by default for better security
    // Only use localStorage if user explicitly chose "remember me"
    const rememberMe = localStorage.getItem(REMEMBER_ME_KEY) === 'true';
    return rememberMe ? localStorage : sessionStorage;
}

/**
 * Store authentication token securely
 * @param {string} token - The auth token to store
 * @param {boolean} rememberMe - Whether to persist across sessions
 */
export function setAuthToken(token, rememberMe = false) {
    // Store remember me preference
    localStorage.setItem(REMEMBER_ME_KEY, rememberMe.toString());

    // Store token in appropriate storage
    const storage = getStorage();
    storage.setItem(TOKEN_KEY, token);

    // If switching from localStorage to sessionStorage, clean up old token
    if (!rememberMe) {
        localStorage.removeItem(TOKEN_KEY);
    } else {
        sessionStorage.removeItem(TOKEN_KEY);
    }
}

/**
 * Get authentication token
 * @returns {string|null} The stored auth token or null
 */
export function getAuthToken() {
    // Check both storages to handle migration
    const storage = getStorage();
    let token = storage.getItem(TOKEN_KEY);

    // Fallback to other storage for backwards compatibility
    if (!token) {
        const otherStorage = storage === localStorage ? sessionStorage : localStorage;
        token = otherStorage.getItem(TOKEN_KEY);

        // Migrate token to correct storage if found
        if (token) {
            storage.setItem(TOKEN_KEY, token);
            otherStorage.removeItem(TOKEN_KEY);
        }
    }

    return token;
}

/**
 * Remove authentication token from all storages
 */
export function removeAuthToken() {
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REMEMBER_ME_KEY);
}

/**
 * Store user data securely
 * @param {Object} user - User data object
 */
export function setStoredUser(user) {
    const storage = getStorage();
    storage.setItem(USER_KEY, JSON.stringify(user));

    // Clean up other storage
    const otherStorage = storage === localStorage ? sessionStorage : localStorage;
    otherStorage.removeItem(USER_KEY);
}

/**
 * Get stored user data
 * @returns {Object|null} The stored user data or null
 */
export function getStoredUser() {
    const storage = getStorage();
    let userData = storage.getItem(USER_KEY);

    // Fallback to other storage for backwards compatibility
    if (!userData) {
        const otherStorage = storage === localStorage ? sessionStorage : localStorage;
        userData = otherStorage.getItem(USER_KEY);
    }

    if (userData) {
        try {
            return JSON.parse(userData);
        } catch (e) {
            console.warn('[SecureStorage] Failed to parse user data');
            return null;
        }
    }

    return null;
}

/**
 * Remove stored user data from all storages
 */
export function removeStoredUser() {
    localStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(USER_KEY);
}

/**
 * Clear all auth-related storage
 */
export function clearAuthStorage() {
    removeAuthToken();
    removeStoredUser();
}

/**
 * Check if "remember me" is enabled
 * @returns {boolean}
 */
export function isRememberMeEnabled() {
    return localStorage.getItem(REMEMBER_ME_KEY) === 'true';
}
