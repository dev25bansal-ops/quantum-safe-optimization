/**
 * Auth Modal Component
 * Reusable authentication modal using the new Modal component
 */

import { Modal } from './Modal.js';

class AuthModal {
    constructor() {
        this.modal = new Modal({
            size: 'medium',
            title: 'Authentication',
            closable: true
        });
        this.modal.mount(document.body);

        this.currentMode = 'login'; // 'login' or 'register'
        this.isLoggedInCallback = null;
        this.isRegisteredCallback = null;

        this.setupEventHandlers();
    }

    setupEventHandlers() {
        // Defer overlay click handler - overlay only exists after modal.open()/render()
        const originalOpen = this.modal.open.bind(this.modal);
        this.modal.open = (...args) => {
            originalOpen(...args);
            const overlay = this.modal.element?.querySelector('[data-modal-overlay]');
            if (overlay) {
                overlay.addEventListener('click', (e) => {
                    if (e.target === overlay) {
                        this.close();
                    }
                });
            }
        };
    }

    openLogin() {
        this.currentMode = 'login';
        this.modal.open();  // setState queues render via microtask
        this.modal.setTitle('Sign In');
        // Defer content setup until after batched render completes
        setTimeout(() => this.getLoginContent(), 0);
    }

    openRegister() {
        this.currentMode = 'register';
        this.modal.open();  // setState queues render via microtask
        this.modal.setTitle('Create Account');
        // Defer content setup until after batched render completes
        setTimeout(() => this.getRegisterContent(), 0);
    }

    getLoginContent() {
        this.modal.setContent(`
            <form id="login-form" class="auth-form">
                <div class="form-group">
                    <label for="login-email"><i class="fas fa-envelope"></i> Email</label>
                    <input type="email" id="login-email" placeholder="your@email.com" required>
                </div>
                <div class="form-group">
                    <label for="login-password"><i class="fas fa-lock"></i> Password</label>
                    <input type="password" id="login-password" placeholder="••••••••" required>
                </div>
                <div class="form-error" id="login-error" style="display: none;"></div>
                <div class="form-actions">
                    <button type="submit" class="btn btn-primary btn-block" id="login-submit">
                        <i class="fas fa-sign-in-alt"></i> Sign In
                    </button>
                </div>
                <div class="auth-switch">
                    <span>Don't have an account?</span>
                    <a href="#" id="switch-to-register" class="link">Create one</a>
                </div>
            </form>
        `);

        // Setup event listeners
        const loginForm = this.modal.element.querySelector('#login-form');
        const switchToRegisterBtn = this.modal.element.querySelector('#switch-to-register');

        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleLogin();
        });

        switchToRegisterBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.openRegister();
        });
    }

    getRegisterContent() {
        this.modal.setContent(`
            <form id="register-form" class="auth-form">
                <div class="form-group">
                    <label for="register-name"><i class="fas fa-user"></i> Full Name</label>
                    <input type="text" id="register-name" placeholder="John Doe" required>
                </div>
                <div class="form-group">
                    <label for="register-email"><i class="fas fa-envelope"></i> Email</label>
                    <input type="email" id="register-email" placeholder="your@email.com" required>
                </div>
                <div class="form-group">
                    <label for="register-password"><i class="fas fa-lock"></i> Password</label>
                    <input type="password" id="register-password" placeholder="••••••••" required minlength="8">
                </div>
                <div class="form-group">
                    <label for="register-confirm"><i class="fas fa-lock"></i> Confirm Password</label>
                    <input type="password" id="register-confirm" placeholder="••••••••" required minlength="8">
                </div>
                <div class="form-error" id="register-error" style="display: none;"></div>
                <div class="form-actions">
                    <button type="submit" class="btn btn-primary btn-block" id="register-submit">
                        <i class="fas fa-user-plus"></i> Create Account
                    </button>
                </div>
                <div class="auth-switch">
                    <span>Already have an account?</span>
                    <a href="#" id="switch-to-login" class="link">Sign in</a>
                </div>
            </form>
        `);

        // Setup event listeners
        const registerForm = this.modal.element.querySelector('#register-form');
        const switchToLoginBtn = this.modal.element.querySelector('#switch-to-login');

        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleRegister();
        });

        switchToLoginBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.openLogin();
        });
    }

    async handleLogin() {
        const email = this.modal.element.querySelector('#login-email').value;
        const password = this.modal.element.querySelector('#login-password').value;
        const errorDiv = this.modal.element.querySelector('#login-error');
        const submitBtn = this.modal.element.querySelector('#login-submit');

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing in...';
        errorDiv.style.display = 'none';

        try {
            // Transform email to username
            const username = email.includes('@')
                ? email.split('@')[0].toLowerCase().replace(/[^a-z0-9_]/g, '_')
                : email.toLowerCase();

            const apiUrl = localStorage.getItem('apiUrl') || (window.location.origin + '/api/v1');

            const response = await fetch(`${apiUrl}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            const data = await response.json();

            if (response.ok && data.access_token) {
                localStorage.setItem('authToken', data.access_token);
                localStorage.setItem('quantumSafeUser', JSON.stringify({
                    email: email,
                    username: username,
                    signedInAt: new Date().toISOString()
                }));

                if (data.refresh_token) {
                    localStorage.setItem('refreshToken', data.refresh_token);
                }

                this.close();
                if (this.isLoggedInCallback) {
                    await this.isLoggedInCallback();
                }

                // Trigger global toast
                if (window.showToast) {
                    window.showToast('success', 'Welcome!', 'You have successfully signed in');
                }
            } else {
                throw new Error(data.detail || data.message || 'Invalid credentials');
            }
        } catch (error) {
            // SECURITY: Demo tokens must be issued by server, not client-side
            // Client-side token generation via btoa() is a CRITICAL vulnerability
            if (error.message.includes('fetch') || error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
                if (window.showToast) window.showToast('error', 'API Unavailable', 'Server authentication is required. Please check your connection.');
                errorDiv.textContent = 'Authentication server available. Please check your connection.';
                errorDiv.style.display = 'block';
            } else {
                errorDiv.textContent = error.message;
                errorDiv.style.display = 'block';
            }
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Sign In';
        }
    }

    async handleRegister() {
        const name = this.modal.element.querySelector('#register-name').value;
        const email = this.modal.element.querySelector('#register-email').value;
        const password = this.modal.element.querySelector('#register-password').value;
        const confirmPassword = this.modal.element.querySelector('#register-confirm').value;
        const errorDiv = this.modal.element.querySelector('#register-error');
        const submitBtn = this.modal.element.querySelector('#register-submit');

        // Validate passwords match
        if (password !== confirmPassword) {
            errorDiv.textContent = 'Passwords do not match';
            errorDiv.style.display = 'block';
            return;
        }

        // Validate password complexity
        const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d@$!%*?&]{8,}$/;
        if (!passwordRegex.test(password)) {
            errorDiv.textContent = 'Password must be at least 8 characters, include uppercase, lowercase, and numbers';
            errorDiv.style.display = 'block';
            return;
        }

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating account...';
        errorDiv.style.display = 'none';

        try {
            // Transform email to username
            const username = email.includes('@')
                ? email.split('@')[0].toLowerCase().replace(/[^a-z0-9_]/g, '_')
                : email.toLowerCase();

            const apiUrl = localStorage.getItem('apiUrl') || (window.location.origin + '/api/v1');

            // Step 1: Register the user
            const regResponse = await fetch(`${apiUrl}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username,
                    email,
                    password,
                    full_name: name
                })
            });

            const regData = await regResponse.json();

            if (!regResponse.ok) {
                throw new Error(regData.detail || regData.message || 'Registration failed');
            }

            // Step 2: Auto-login after successful registration
            const loginResponse = await fetch(`${apiUrl}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            const loginData = await loginResponse.json();

            if (loginResponse.ok && loginData.access_token) {
                localStorage.setItem('authToken', loginData.access_token);
                localStorage.setItem('quantumSafeUser', JSON.stringify({
                    email: email,
                    username: username,
                    full_name: name,
                    signedInAt: new Date().toISOString()
                }));

                if (loginData.refresh_token) {
                    localStorage.setItem('refreshToken', loginData.refresh_token);
                }

                this.close();
                if (this.isRegisteredCallback) {
                    await this.isRegisteredCallback();
                }

                if (window.showToast) {
                    window.showToast('success', 'Account Created!', 'Your account has been created and you are now signed in');
                }
            } else {
                // Registration succeeded but auto-login failed - prompt to sign in
                this.close();
                if (window.showToast) {
                    window.showToast('success', 'Account Created!', regData.message || 'You can now sign in with your credentials');
                }
            }
        } catch (error) {
            if (error.message.includes('fetch') || error.message.includes('NetworkError') || error.message.includes('Failed to fetch')) {
                if (window.showToast) window.showToast('error', 'API Unavailable', 'Server authentication is required. Please check your connection.');
                errorDiv.textContent = 'Authentication server unavailable. Please check your connection.';
                errorDiv.style.display = 'block';
            } else {
                errorDiv.textContent = error.message;
                errorDiv.style.display = 'block';
            }
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-user-plus"></i> Create Account';
        }
    }

    close() {
        this.modal.close();
    }

    onLogin(callback) {
        this.isLoggedInCallback = callback;
    }

    onRegister(callback) {
        this.isRegisteredCallback = callback;
    }
}

export default AuthModal;
