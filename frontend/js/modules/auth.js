/**
 * Authentication Module
 * Handles user authentication, login, registration, and session management
 */

import { CONFIG, STATE } from './config.js';
import { getAuthHeaders } from './utils.js';
import { showToast } from './toast.js';
import {
    getAuthToken, setAuthToken, removeAuthToken,
    getStoredUser, setStoredUser, removeStoredUser,
    clearAuthStorage
} from './secure-storage.js';
import { apiGet, apiPost, apiRequest } from './api.js';

// Forward declarations for callbacks
let loadJobsCallback = null;
let loadWorkerStatusCallback = null;
let loadWebhookStatsCallback = null;

export function setAuthCallbacks(loadJobs, loadWorkerStatus, loadWebhookStats) {
    loadJobsCallback = loadJobs;
    loadWorkerStatusCallback = loadWorkerStatus;
    loadWebhookStatsCallback = loadWebhookStats;
}

/**
 * Initialize authentication handlers
 */
export function initAuth() {
    // Login form submission
    document.getElementById('login-form')?.addEventListener('submit', handleLogin);

    // Register form submission
    document.getElementById('register-form')?.addEventListener('submit', handleRegister);
}

/**
 * Initialize user menu dropdown
 */
export function initUserMenu() {
    const userMenu = document.getElementById('user-menu');
    const dropdown = document.getElementById('user-dropdown');

    if (userMenu && dropdown) {
        userMenu.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdown.classList.toggle('active');
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!userMenu.contains(e.target)) {
                dropdown.classList.remove('active');
            }
        });
    }
}

/**
 * Check authentication status
 */
export async function checkAuthStatus() {
    const token = getAuthToken();
    const storedUserData = getStoredUser();

    if (!token) {
        console.log('[Auth] No token found');
        updateAuthUI(false, null);
        return;
    }

    console.log('[Auth] Token found, validating...');

    // First check if we have stored user data (from landing page login)
    // storedUserData is already parsed from getStoredUser()

    // Try to decode as demo token (base64 JSON)
    try {
        const decodedToken = JSON.parse(atob(token));
        if (decodedToken && decodedToken.email && decodedToken.exp > Date.now()) {
            console.log('[Auth] Valid demo token detected');
            const user = storedUserData || { email: decodedToken.email };
            STATE.isAuthenticated = true;
            STATE.user = user;
            updateAuthUI(true, user);
            if (loadWorkerStatusCallback) loadWorkerStatusCallback();
            if (loadWebhookStatsCallback) loadWebhookStatsCallback();
            return;
        }
    } catch (e) {
        // Not a demo token - this is expected for real JWT tokens
        console.log('[Auth] Token is not a demo token, trying API validation...');
    }

    // Validate real JWT token via API
    try {
        const user = await apiGet('/auth/me');
        console.log('[Auth] API validation successful:', user.username || user.email);
        STATE.isAuthenticated = true;
        STATE.user = user;
        updateAuthUI(true, user);
        if (loadWorkerStatusCallback) loadWorkerStatusCallback();
        if (loadWebhookStatsCallback) loadWebhookStatsCallback();
    } catch (error) {
        if (error.message.includes('Session expired') || error.message.includes('401')) {
            console.log('[Auth] Token invalid or expired');
            clearAuthStorage();
            updateAuthUI(false, null);
        } else {
            console.error('[Auth] API check failed:', error.message);
            // If API is unreachable but we have stored user data, use it
            if (storedUserData) {
                console.log('[Auth] API unreachable, using stored user data');
                STATE.isAuthenticated = true;
                STATE.user = storedUserData;
                updateAuthUI(true, storedUserData);
                if (loadWorkerStatusCallback) loadWorkerStatusCallback();
                if (loadWebhookStatsCallback) loadWebhookStatsCallback();
            } else {
                updateAuthUI(false, null);
            }
        }
    }
}

/**
 * Update authentication UI
 */
export function updateAuthUI(isAuthenticated, user) {
    STATE.isAuthenticated = isAuthenticated;
    STATE.user = user;

    const loginBtn = document.getElementById('btn-login');
    const logoutBtn = document.getElementById('btn-logout');
    const userAvatar = document.getElementById('user-avatar');
    const userName = document.getElementById('user-name');
    const dropdownHeader = document.getElementById('user-dropdown-header');
    const dropdownEmail = document.getElementById('user-dropdown-email');

    if (isAuthenticated && user) {
        // Show authenticated state
        if (loginBtn) loginBtn.style.display = 'none';
        if (logoutBtn) logoutBtn.style.display = 'flex';
        if (userAvatar) userAvatar.textContent = (user.name || user.email || 'U').charAt(0).toUpperCase();
        if (userName) userName.textContent = user.name || user.email?.split('@')[0] || 'User';
        if (dropdownEmail) dropdownEmail.textContent = user.email || 'Signed in';
        if (dropdownHeader) dropdownHeader.style.display = 'block';
    } else {
        // Show guest state
        if (loginBtn) loginBtn.style.display = 'flex';
        if (logoutBtn) logoutBtn.style.display = 'none';
        if (userAvatar) userAvatar.textContent = 'G';
        if (userName) userName.textContent = 'Guest';
        if (dropdownEmail) dropdownEmail.textContent = 'Not signed in';
    }
}

/**
 * Open authentication modal
 */
export function openAuthModal(e) {
    e?.preventDefault();
    document.getElementById('auth-modal')?.classList.add('active');
    showLoginForm();

    // Close user dropdown
    document.getElementById('user-dropdown')?.classList.remove('active');
}

/**
 * Close authentication modal
 */
export function closeAuthModal() {
    document.getElementById('auth-modal')?.classList.remove('active');
    // Reset forms
    document.getElementById('login-form')?.reset();
    document.getElementById('register-form')?.reset();
    document.getElementById('login-error').style.display = 'none';
    document.getElementById('register-error').style.display = 'none';
}

/**
 * Show login form
 */
export function showLoginForm(e) {
    e?.preventDefault();
    document.getElementById('login-form').style.display = 'block';
    document.getElementById('register-form').style.display = 'none';
    document.getElementById('auth-modal-title').innerHTML = '<i class="fas fa-user-lock"></i> Sign In';
}

/**
 * Show register form
 */
export function showRegisterForm(e) {
    e?.preventDefault();
    document.getElementById('login-form').style.display = 'none';
    document.getElementById('register-form').style.display = 'block';
    document.getElementById('auth-modal-title').innerHTML = '<i class="fas fa-user-plus"></i> Create Account';
}

/**
 * Handle login form submission
 */
async function handleLogin(e) {
    e.preventDefault();

    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const errorDiv = document.getElementById('login-error');
    const submitBtn = document.getElementById('login-submit');

    // Disable button and show loading
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing in...';
    errorDiv.style.display = 'none';

    try {
        // Transform email to username (same logic as signup - dots become underscores)
        const username = email.includes('@')
            ? email.split('@')[0].toLowerCase().replace(/[^a-z0-9_]/g, '_')
            : email.toLowerCase();

        const data = await apiPost('/auth/login', { username, password });

        // Check if "remember me" checkbox is checked
        const rememberMe = document.getElementById('remember-me')?.checked || false;
        setAuthToken(data.access_token, rememberMe);
        setStoredUser({
            email: email,
            username: username,
            signedInAt: new Date().toISOString()
        });
        if (data.refresh_token) {
            localStorage.setItem('refreshToken', data.refresh_token);
        }

        closeAuthModal();
        showToast('success', 'Welcome!', 'You have successfully signed in');
        await checkAuthStatus();
        if (loadJobsCallback) loadJobsCallback();
    } catch (error) {
        // Fallback to demo mode if network error
        if (error.message.includes('Failed to fetch') || error.name === 'TypeError') {
            const demoToken = btoa(JSON.stringify({ email, exp: Date.now() + 86400000 }));
            const rememberMe = document.getElementById('remember-me')?.checked || false;
            setAuthToken(demoToken, rememberMe);
            setStoredUser({
                email: email,
                signedInAt: new Date().toISOString()
            });
            closeAuthModal();
            showToast('success', 'Welcome!', 'Signed in (demo mode)');
            await checkAuthStatus();
            if (loadJobsCallback) loadJobsCallback();
        } else {
            errorDiv.textContent = error.message;
            errorDiv.style.display = 'block';
        }
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Sign In';
    }
}

/**
 * Handle register form submission
 */
async function handleRegister(e) {
    e.preventDefault();

    const name = document.getElementById('register-name').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    const confirm = document.getElementById('register-confirm').value;
    const errorDiv = document.getElementById('register-error');
    const submitBtn = document.getElementById('register-submit');

    // Validate passwords match
    if (password !== confirm) {
        errorDiv.textContent = 'Passwords do not match';
        errorDiv.style.display = 'block';
        return;
    }

    // Disable button and show loading
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating account...';
    errorDiv.style.display = 'none';

    try {
        // Create username from email prefix (same as signin logic for consistency)
        const username = email.includes('@') ? email.split('@')[0].toLowerCase().replace(/[^a-z0-9_]/g, '_') : email.toLowerCase();

        const data = await apiPost('/auth/register', { username, email, password });

        // Auto-login after successful registration
        try {
            const loginData = await apiPost('/auth/login', { username, password });

            const rememberMe = true; // Auto-login uses session storage
            setAuthToken(loginData.access_token, rememberMe);
            setStoredUser({
                email: email,
                username: username,
                name: name,
                signedInAt: new Date().toISOString()
            });

            closeAuthModal();
            showToast('success', 'Account Created', 'Welcome! You are now signed in.');
            await checkAuthStatus();
            if (loadJobsCallback) loadJobsCallback();
        } catch (loginError) {
            console.warn('Auto-login failed:', loginError);
            showToast('success', 'Account Created', 'Please sign in with your credentials');
            showLoginForm();
            document.getElementById('login-email').value = username;
        }
    } catch (error) {
        // Fallback to demo mode if network error
        if (error.message.includes('Failed to fetch') || error.name === 'TypeError') {
            showToast('info', 'Demo Mode', 'Account created in demo mode');
            showLoginForm();
            document.getElementById('login-email').value = email;
        } else {
            errorDiv.textContent = error.message;
            errorDiv.style.display = 'block';
        }
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-user-plus"></i> Create Account';
    }
}

/**
 * Handle logout
 */
export async function handleLogout(e) {
    e?.preventDefault();

    try {
        const token = getAuthToken();
        if (token) {
            // Try to call logout endpoint (optional, may fail if token expired)
            try {
                await apiRequest('/auth/logout', { method: 'POST' });
            } catch {
                // Logout endpoint failure is ok - continue with cleanup
            }
        }
    } finally {
        // Clear all auth tokens and user data
        clearAuthStorage();
        localStorage.removeItem('refreshToken');

        // Update UI
        STATE.isAuthenticated = false;
        STATE.user = null;
        updateAuthUI(false, null);

        // Close dropdown
        document.getElementById('user-dropdown')?.classList.remove('active');

        showToast('info', 'Signed Out', 'You have been signed out');
        if (loadJobsCallback) loadJobsCallback();
    }
}

// Make auth functions globally accessible
window.openAuthModal = openAuthModal;
window.closeAuthModal = closeAuthModal;
window.showLoginForm = showLoginForm;
window.showRegisterForm = showRegisterForm;
window.handleLogout = handleLogout;
