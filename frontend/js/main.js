/**
 * QuantumSafe Optimize - Landing Page JavaScript
 * Handles navigation, animations, auth modal, and interactive elements
 */

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initAlgorithmTabs();
    initScrollAnimations();
    initEnhancedScrollReveal();
    initParticles();
    initCopyButtons();
    initMagneticButtons();
    initParallaxEffects();
    initCounters();
    initNewsletter();
    initFAQ();
});

/**
 * Navigation - Scroll effects and mobile menu
 */
function initNavigation() {
    const navbar = document.querySelector('.navbar');
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const navLinks = document.querySelector('.nav-links');
    const navActions = document.querySelector('.nav-actions');
    const announcementBar = document.querySelector('.announcement-bar');

    // Get announcement bar height
    const announcementHeight = announcementBar ? announcementBar.offsetHeight : 0;

    // Scroll effect
    let lastScroll = 0;

    window.addEventListener('scroll', () => {
        const currentScroll = window.pageYOffset;

        // Add scrolled class for background and hide announcement
        if (currentScroll > announcementHeight) {
            navbar.classList.add('scrolled');
            if (announcementBar) {
                announcementBar.style.transform = 'translateY(-100%)';
                announcementBar.style.opacity = '0';
            }
        } else {
            navbar.classList.remove('scrolled');
            if (announcementBar) {
                announcementBar.style.transform = 'translateY(0)';
                announcementBar.style.opacity = '1';
            }
        }

        lastScroll = currentScroll;
    });

    // Mobile menu toggle
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', () => {
            mobileMenuBtn.classList.toggle('active');

            // Create mobile menu if it doesn't exist
            let mobileMenu = document.querySelector('.mobile-menu');

            if (!mobileMenu) {
                mobileMenu = document.createElement('div');
                mobileMenu.className = 'mobile-menu';
                mobileMenu.innerHTML = `
                    <div class="mobile-menu-content">
                        ${navLinks ? navLinks.outerHTML : ''}
                        ${navActions ? navActions.outerHTML : ''}
                    </div>
                `;

                // Add styles
                mobileMenu.style.cssText = `
                    position: fixed;
                    top: 70px;
                    left: 0;
                    right: 0;
                    background: rgba(10, 10, 15, 0.98);
                    backdrop-filter: blur(20px);
                    border-bottom: 1px solid var(--border-color);
                    padding: 24px;
                    transform: translateY(-100%);
                    opacity: 0;
                    visibility: hidden;
                    transition: all 0.3s ease;
                    z-index: 999;
                `;

                const content = mobileMenu.querySelector('.mobile-menu-content');
                content.style.cssText = `
                    display: flex;
                    flex-direction: column;
                    gap: 24px;
                `;

                const links = mobileMenu.querySelector('.nav-links');
                if (links) {
                    links.style.cssText = `
                        display: flex;
                        flex-direction: column;
                        gap: 16px;
                    `;
                }

                const actions = mobileMenu.querySelector('.nav-actions');
                if (actions) {
                    actions.style.cssText = `
                        display: flex;
                        flex-direction: column;
                        gap: 12px;
                    `;
                }

                navbar.after(mobileMenu);
            }

            // Toggle menu visibility
            if (mobileMenuBtn.classList.contains('active')) {
                mobileMenu.style.transform = 'translateY(0)';
                mobileMenu.style.opacity = '1';
                mobileMenu.style.visibility = 'visible';
            } else {
                mobileMenu.style.transform = 'translateY(-100%)';
                mobileMenu.style.opacity = '0';
                mobileMenu.style.visibility = 'hidden';
            }
        });
    }

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href === '#') return;

            e.preventDefault();
            const target = document.querySelector(href);

            if (target) {
                const navHeight = navbar.offsetHeight;
                const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - navHeight;

                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });

                // Close mobile menu if open
                const mobileMenu = document.querySelector('.mobile-menu');
                if (mobileMenu && mobileMenuBtn.classList.contains('active')) {
                    mobileMenuBtn.click();
                }
            }
        });
    });
}

/**
 * Algorithm Tabs - Switch between QAOA, VQE, and Annealing
 */
function initAlgorithmTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const panels = document.querySelectorAll('.algorithm-panel');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.dataset.tab;

            // Update button states
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            // Update panel visibility
            panels.forEach(panel => {
                panel.classList.remove('active');
                if (panel.id === targetTab) {
                    panel.classList.add('active');
                }
            });
        });
    });
}

/**
 * Scroll Animations - Fade in elements on scroll
 */
function initScrollAnimations() {
    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe elements
    const animateElements = document.querySelectorAll(
        '.feature-card, .backend-card, .security-feature, .flow-step, .pricing-card, .testimonial-card, .faq-item, .proof-stat'
    );

    animateElements.forEach((el, index) => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = `opacity 0.5s ease ${index * 0.05}s, transform 0.5s ease ${index * 0.05}s`;
        observer.observe(el);
    });

    // Add CSS for animation
    const style = document.createElement('style');
    style.textContent = `
        .animate-in {
            opacity: 1 !important;
            transform: translateY(0) !important;
        }
    `;
    document.head.appendChild(style);
}

/**
 * Enhanced Scroll Reveal - Advanced reveal animations
 */
function initEnhancedScrollReveal() {
    const revealOptions = {
        root: null,
        rootMargin: '-50px',
        threshold: 0.15
    };

    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('revealed');
                revealObserver.unobserve(entry.target);
            }
        });
    }, revealOptions);

    // Add reveal classes to sections
    document.querySelectorAll('.section-header').forEach(el => {
        el.classList.add('reveal-element');
        revealObserver.observe(el);
    });

    document.querySelectorAll('.features-grid, .backends-grid, .pricing-grid').forEach(el => {
        el.classList.add('stagger-children');
        revealObserver.observe(el);
    });

    document.querySelectorAll('.security-content').forEach(el => {
        el.classList.add('reveal-left');
        revealObserver.observe(el);
    });

    document.querySelectorAll('.security-visual').forEach(el => {
        el.classList.add('reveal-right');
        revealObserver.observe(el);
    });
}

/**
 * Floating Particles - Background animation
 */
function initParticles() {
    const container = document.getElementById('particles');
    if (!container) return;

    const particleCount = 30;

    for (let i = 0; i < particleCount; i++) {
        createParticle(container);
    }
}

function createParticle(container) {
    const particle = document.createElement('div');

    const size = Math.random() * 4 + 2;
    const x = Math.random() * 100;
    const y = Math.random() * 100;
    const duration = Math.random() * 20 + 10;
    const delay = Math.random() * 5;

    particle.style.cssText = `
        position: absolute;
        width: ${size}px;
        height: ${size}px;
        background: rgba(99, 102, 241, ${Math.random() * 0.3 + 0.1});
        border-radius: 50%;
        left: ${x}%;
        top: ${y}%;
        animation: float ${duration}s ease-in-out ${delay}s infinite;
        pointer-events: none;
    `;

    container.appendChild(particle);
}

// Add float animation
const floatStyle = document.createElement('style');
floatStyle.textContent = `
    @keyframes float {
        0%, 100% {
            transform: translate(0, 0) scale(1);
            opacity: 0.5;
        }
        25% {
            transform: translate(20px, -30px) scale(1.1);
            opacity: 0.8;
        }
        50% {
            transform: translate(-10px, -50px) scale(0.9);
            opacity: 0.6;
        }
        75% {
            transform: translate(-30px, -20px) scale(1.05);
            opacity: 0.7;
        }
    }
`;
document.head.appendChild(floatStyle);

/**
 * Copy Buttons - Copy code to clipboard
 */
function initCopyButtons() {
    const copyButtons = document.querySelectorAll('.copy-btn');

    copyButtons.forEach(button => {
        button.addEventListener('click', async () => {
            const codeBlock = button.closest('.code-block');
            const code = codeBlock.querySelector('code');

            if (code) {
                try {
                    await navigator.clipboard.writeText(code.textContent);

                    // Update button text
                    const originalText = button.textContent;
                    button.textContent = 'Copied!';
                    button.style.color = 'var(--success)';

                    setTimeout(() => {
                        button.textContent = originalText;
                        button.style.color = '';
                    }, 2000);
                } catch (err) {
                    console.error('Failed to copy:', err);
                }
            }
        });
    });
}

/**
 * Counter Animation
 */
function initCounters() {
    const counters = document.querySelectorAll('.counter');

    const observerOptions = {
        threshold: 0.5
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounter(entry.target);
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    counters.forEach(counter => observer.observe(counter));
}

function animateCounter(element) {
    const target = parseInt(element.dataset.target) || 0;
    const duration = 2000;
    const start = 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeProgress = 1 - Math.pow(1 - progress, 3); // Ease out cubic
        const current = Math.floor(easeProgress * target);

        element.textContent = current + '+';

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

/**
 * Newsletter Form Handler
 */
function initNewsletter() {
    const form = document.querySelector('.newsletter-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const email = form.querySelector('input[type="email"]');
        const button = form.querySelector('button');

        if (!email.value) return;

        // Show loading state
        const originalText = button.textContent;
        button.textContent = 'Subscribing...';
        button.disabled = true;

        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 1000));

        // Show success
        button.textContent = '✓ Subscribed!';
        button.style.background = 'var(--success)';
        email.value = '';

        // Reset after delay
        setTimeout(() => {
            button.textContent = originalText;
            button.style.background = '';
            button.disabled = false;
        }, 3000);
    });
}

/**
 * Smooth Scroll Enhancement
 */
function initSmoothScroll() {
    // Handle announcement bar offset
    const announcementBar = document.querySelector('.announcement-bar');
    const navbar = document.querySelector('.navbar');

    if (announcementBar && navbar) {
        const updateNavPosition = () => {
            const barHeight = announcementBar.offsetHeight;
            navbar.style.top = `${barHeight}px`;
        };

        updateNavPosition();
        window.addEventListener('resize', updateNavPosition);
    }
}

/**
 * FAQ Accordion Enhancement
 */
function initFAQ() {
    const faqItems = document.querySelectorAll('.faq-item');

    faqItems.forEach(item => {
        const summary = item.querySelector('summary');

        // Add click animation
        summary.addEventListener('click', (e) => {
            // Add visual feedback
            item.style.transition = 'all 0.3s ease';
        });

        // Track open/close state for animation
        item.addEventListener('toggle', () => {
            if (item.open) {
                item.style.borderColor = 'var(--primary)';
                item.style.background = 'rgba(99, 102, 241, 0.05)';
            } else {
                item.style.borderColor = '';
                item.style.background = '';
            }
        });
    });
}

/**
 * API Integration Helpers (for dashboard integration)
 */
const API = {
    baseUrl: window.location.origin,

    async submitJob(jobData) {
        try {
            const response = await fetch(`${this.baseUrl}/jobs`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(jobData)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Job submission failed:', error);
            throw error;
        }
    },

    async getJobStatus(jobId) {
        try {
            const response = await fetch(`${this.baseUrl}/jobs/${jobId}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Failed to get job status:', error);
            throw error;
        }
    },

    async getHealth() {
        try {
            const response = await fetch(`${this.baseUrl}/health`);
            return await response.json();
        } catch (error) {
            console.error('Health check failed:', error);
            return { status: 'error', message: error.message };
        }
    }
};

// Expose API for dashboard use
window.QuantumSafeAPI = API;

/**
 * Auth Modal Functions
 */
function openAuthModal(tab = 'signup') {
    const modal = document.getElementById('authModal');
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
        switchAuthTab(tab);
    }
}

function closeAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';

        // Reset forms
        const signupForm = document.getElementById('signupForm');
        const signinForm = document.getElementById('signinForm');
        const successMessage = document.getElementById('authSuccess');
        const modalBody = document.querySelector('.auth-modal-body');

        if (signupForm) signupForm.reset();
        if (signinForm) signinForm.reset();
        if (successMessage) successMessage.classList.remove('show');
        if (modalBody) modalBody.style.display = 'block';

        // Reset button states
        document.querySelectorAll('.auth-submit-btn').forEach(btn => {
            btn.classList.remove('loading');
            btn.disabled = false;
        });
    }
}

function switchAuthTab(tab) {
    const tabs = document.querySelectorAll('.auth-tab');
    const signupForm = document.getElementById('signupForm');
    const signinForm = document.getElementById('signinForm');
    const authFooter = document.getElementById('authFooter');

    tabs.forEach(t => t.classList.remove('active'));

    if (tab === 'signup') {
        tabs[0].classList.add('active');
        if (signupForm) signupForm.style.display = 'flex';
        if (signinForm) signinForm.style.display = 'none';
        if (authFooter) authFooter.innerHTML = '<p>Already have an account? <a onclick="switchAuthTab(\'signin\')">Sign in</a></p>';
    } else {
        tabs[1].classList.add('active');
        if (signupForm) signupForm.style.display = 'none';
        if (signinForm) signinForm.style.display = 'flex';
        if (authFooter) authFooter.innerHTML = '<p>Don\'t have an account? <a onclick="switchAuthTab(\'signup\')">Sign up</a></p>';
    }
}

async function handleSignup(event) {
    event.preventDefault();

    const form = event.target;
    const submitBtn = form.querySelector('.auth-submit-btn');
    const modalBody = document.querySelector('.auth-modal-body');
    const successMessage = document.getElementById('authSuccess');
    const errorDiv = form.querySelector('.auth-error') || createErrorDiv(form);

    // Get form data
    const name = document.getElementById('signup-name').value;
    const email = document.getElementById('signup-email').value;
    const password = document.getElementById('signup-password').value;

    // Hide previous errors
    errorDiv.style.display = 'none';

    // Show loading state
    submitBtn.classList.add('loading');
    submitBtn.disabled = true;

    try {
        // Create username from email prefix (same as signin logic)
        const username = email.includes('@') ? email.split('@')[0].toLowerCase().replace(/[^a-z0-9_]/g, '_') : email.toLowerCase();

        // Call real backend API
        const response = await fetch('/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: username,
                email: email,
                password: password
            })
        });

        // Check if response is JSON (not HTML error page)
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('API unavailable');
        }

        const data = await response.json();

        if (response.ok) {
            // Store user data
            localStorage.setItem('quantumSafeUser', JSON.stringify({
                user_id: data.user_id,
                username: data.username,
                name: name,
                email: email,
                createdAt: data.created_at
            }));

            // Auto-login with the same credentials
            try {
                const loginResponse = await fetch('/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: data.username,
                        password: password
                    })
                });

                // Check content type for login response too
                const loginContentType = loginResponse.headers.get('content-type');
                if (!loginContentType || !loginContentType.includes('application/json')) {
                    throw new Error('Login API unavailable');
                }

                const loginData = await loginResponse.json();

                if (loginResponse.ok && loginData.access_token) {
                    localStorage.setItem('authToken', loginData.access_token);
                    // Show success and redirect to dashboard
                    if (modalBody) modalBody.style.display = 'none';
                    if (successMessage) successMessage.classList.add('show');
                    // Wait a moment then redirect
                    setTimeout(() => {
                        window.location.href = 'dashboard.html';
                    }, 1500);
                } else {
                    // Login failed but signup succeeded - show success and ask to login manually
                    if (modalBody) modalBody.style.display = 'none';
                    if (successMessage) successMessage.classList.add('show');
                }
            } catch (loginError) {
                console.warn('Auto-login failed:', loginError);
                // Show success message anyway
                if (modalBody) modalBody.style.display = 'none';
                if (successMessage) successMessage.classList.add('show');
            }
        } else {
            throw new Error(data.detail || 'Registration failed');
        }
    } catch (error) {
        // Fallback to demo mode if API unavailable (network errors, JSON parse errors, etc.)
        const isApiUnavailable =
            error.message.includes('fetch') ||
            error.message.includes('NetworkError') ||
            error.message.includes('Failed to fetch') ||
            error.message.includes('API unavailable') ||
            error.message.includes('Unexpected token') ||
            error.message.includes('JSON');

        if (isApiUnavailable) {
            const demoToken = btoa(JSON.stringify({ email, name, exp: Date.now() + 86400000 }));
            localStorage.setItem('authToken', demoToken);
            localStorage.setItem('quantumSafeUser', JSON.stringify({
                name: name,
                email: email,
                createdAt: new Date().toISOString()
            }));
            if (modalBody) modalBody.style.display = 'none';
            if (successMessage) successMessage.classList.add('show');
        } else {
            // Provide helpful error message with suggestion to sign in
            if (error.message.toLowerCase().includes('already exists') || error.message.toLowerCase().includes('username') && error.message.toLowerCase().includes('exists')) {
                errorDiv.innerHTML = `Account already exists! <a href="#" onclick="switchAuthTab('signin'); return false;" style="color: #8b5cf6; text-decoration: underline;">Sign in instead</a>`;
            } else {
                errorDiv.textContent = error.message;
            }
            errorDiv.style.display = 'block';
        }
    } finally {
        submitBtn.classList.remove('loading');
        submitBtn.disabled = false;
    }
}

function createErrorDiv(form) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'auth-error';
    errorDiv.style.cssText = 'color: #ef4444; font-size: 0.875rem; margin-top: 0.5rem; display: none;';
    form.insertBefore(errorDiv, form.querySelector('.auth-submit-btn'));
    return errorDiv;
}

async function handleSignin(event) {
    event.preventDefault();

    const form = event.target;
    const submitBtn = form.querySelector('.auth-submit-btn');
    const errorDiv = form.querySelector('.auth-error') || createErrorDiv(form);

    // Get form data - treat email as username for login
    const email = document.getElementById('signin-email').value;
    const password = document.getElementById('signin-password').value;

    // Hide previous errors
    errorDiv.style.display = 'none';

    // Show loading state
    submitBtn.classList.add('loading');
    submitBtn.disabled = true;

    try {
        // Transform email to username (same logic as signup - dots become underscores)
        const username = email.includes('@')
            ? email.split('@')[0].toLowerCase().replace(/[^a-z0-9_]/g, '_')
            : email.toLowerCase();

        // Call real backend API
        const response = await fetch('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: username,
                password: password
            })
        });

        // Check if response is JSON (not HTML error page)
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('API unavailable');
        }

        const data = await response.json();

        if (response.ok && data.access_token) {
            // Store auth token
            localStorage.setItem('authToken', data.access_token);
            localStorage.setItem('quantumSafeUser', JSON.stringify({
                email: email,
                signedInAt: new Date().toISOString()
            }));

            // Redirect to dashboard
            window.location.href = 'dashboard.html';
        } else {
            throw new Error(data.detail || 'Invalid credentials');
        }
    } catch (error) {
        // Fallback to demo mode if API unavailable (network errors, JSON parse errors, etc.)
        const isApiUnavailable =
            error.message.includes('fetch') ||
            error.message.includes('NetworkError') ||
            error.message.includes('Failed to fetch') ||
            error.message.includes('API unavailable') ||
            error.message.includes('Unexpected token') ||
            error.message.includes('JSON');

        if (isApiUnavailable) {
            const demoToken = btoa(JSON.stringify({ email, exp: Date.now() + 86400000 }));
            localStorage.setItem('authToken', demoToken);
            localStorage.setItem('quantumSafeUser', JSON.stringify({
                email: email,
                signedInAt: new Date().toISOString()
            }));
            window.location.href = 'dashboard.html';
        } else {
            // Provide helpful error message with suggestion to sign up
            if (error.message.toLowerCase().includes('invalid credentials')) {
                errorDiv.innerHTML = `Invalid credentials. Don't have an account? <a href="#" onclick="switchAuthTab('signup'); return false;" style="color: #8b5cf6; text-decoration: underline;">Sign up</a>`;
            } else {
                errorDiv.textContent = error.message;
            }
            errorDiv.style.display = 'block';
        }
    } finally {
        submitBtn.classList.remove('loading');
        submitBtn.disabled = false;
    }
}

function goToDashboard() {
    window.location.href = 'dashboard.html';
}

// Close modal on backdrop click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('auth-modal-overlay')) {
        closeAuthModal();
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeAuthModal();
    }
});

// Expose auth functions globally
window.openAuthModal = openAuthModal;
window.closeAuthModal = closeAuthModal;
window.switchAuthTab = switchAuthTab;
window.handleSignup = handleSignup;
window.handleSignin = handleSignin;
window.goToDashboard = goToDashboard;

/**
 * Magnetic Button Effect
 */
function initMagneticButtons() {
    const magneticBtns = document.querySelectorAll('.btn-primary, .btn-secondary');

    magneticBtns.forEach(btn => {
        btn.addEventListener('mousemove', (e) => {
            const rect = btn.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;

            btn.style.transform = `translate(${x * 0.1}px, ${y * 0.1}px)`;
        });

        btn.addEventListener('mouseleave', () => {
            btn.style.transform = '';
        });
    });
}

/**
 * Parallax Effects
 */
function initParallaxEffects() {
    const parallaxElements = document.querySelectorAll('.gradient-orb, .quantum-visual');

    window.addEventListener('scroll', () => {
        const scrollY = window.pageYOffset;

        parallaxElements.forEach((el, index) => {
            const speed = 0.05 * (index + 1);
            el.style.transform = `translateY(${scrollY * speed}px)`;
        });
    });
}

/**
 * Typing Animation for Hero
 */
function initTypingAnimation() {
    const typingElements = document.querySelectorAll('.typing-text');

    typingElements.forEach(el => {
        const text = el.textContent;
        el.textContent = '';
        el.style.visibility = 'visible';

        let i = 0;
        const typeWriter = () => {
            if (i < text.length) {
                el.textContent += text.charAt(i);
                i++;
                setTimeout(typeWriter, 50);
            }
        };

        typeWriter();
    });
}

/**
 * Number Counter Animation
 */
function animateValue(element, start, end, duration) {
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeProgress = 1 - Math.pow(1 - progress, 3);
        const current = Math.floor(start + (end - start) * easeProgress);

        element.textContent = current.toLocaleString();

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

/**
 * Interactive Demo Section
 */
function initInteractiveDemo() {
    // Demo tabs
    const demoTabs = document.querySelectorAll('.demo-tab');
    demoTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.tab;

            // Update tabs
            demoTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Update panels
            document.querySelectorAll('.demo-panel').forEach(panel => {
                panel.classList.remove('active');
            });
            document.getElementById(`demo-${target}`).classList.add('active');

            // If visualization tab is selected, redraw the canvas
            if (target === 'visualization') {
                setTimeout(() => {
                    const size = parseInt(document.getElementById('demo-size')?.value) || 5;
                    const solution = Array.from({ length: size }, () => Math.round(Math.random()));
                    drawOptimizationResult(solution);
                }, 50);
            }
        });
    });

    // Slider value update
    const sizeSlider = document.getElementById('demo-size');
    const sliderValue = document.querySelector('.slider-value');
    if (sizeSlider && sliderValue) {
        sizeSlider.addEventListener('input', () => {
            sliderValue.textContent = `${sizeSlider.value} nodes`;
            updateDemoRequest();
        });
    }

    // Update request on field changes
    ['demo-algorithm', 'demo-problem', 'demo-backend', 'demo-encrypt'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', updateDemoRequest);
        }
    });

    // Initialize live metrics
    initLiveMetrics();
}

function updateDemoRequest() {
    const algorithm = document.getElementById('demo-algorithm')?.value || 'qaoa';
    const problem = document.getElementById('demo-problem')?.value || 'maxcut';
    const size = document.getElementById('demo-size')?.value || 5;
    const backend = document.getElementById('demo-backend')?.value || 'simulator';
    const encrypt = document.getElementById('demo-encrypt')?.checked || true;

    const problemTypes = {
        maxcut: 'max_cut',
        tsp: 'traveling_salesman',
        portfolio: 'portfolio_optimization',
        scheduling: 'job_scheduling'
    };

    // Generate random edges based on size
    const edges = [];
    const numNodes = parseInt(size);
    for (let i = 0; i < numNodes; i++) {
        edges.push([i, (i + 1) % numNodes]);
        if (Math.random() > 0.5 && i + 2 < numNodes) {
            edges.push([i, i + 2]);
        }
    }

    const request = {
        algorithm: algorithm,
        problem: {
            type: problemTypes[problem] || 'max_cut',
            graph: {
                nodes: numNodes,
                edges: edges
            }
        },
        config: {
            p_layers: algorithm === 'qaoa' ? 2 : undefined,
            optimizer: 'COBYLA',
            shots: 1024
        },
        backend: backend,
        encryption: {
            enabled: encrypt,
            algorithm: 'ML-KEM-768'
        }
    };

    // Clean up undefined values
    if (!request.config.p_layers) delete request.config.p_layers;

    const codeEl = document.getElementById('demo-request-code');
    if (codeEl) {
        codeEl.textContent = JSON.stringify(request, null, 2);
    }
}

async function runDemoOptimization() {
    const statusEl = document.getElementById('demo-status');
    const responseEl = document.getElementById('demo-response-code');
    const runBtn = document.querySelector('.demo-run-btn');

    // Update status
    statusEl.className = 'demo-status running';
    statusEl.innerHTML = '<span class="status-icon">⏳</span><span class="status-text">Running optimization...</span>';
    runBtn.disabled = true;

    // Simulate optimization (in real app, this would call the API)
    await simulateProgress(statusEl);

    // Generate mock response
    const algorithm = document.getElementById('demo-algorithm')?.value || 'qaoa';
    const size = parseInt(document.getElementById('demo-size')?.value) || 5;

    const response = {
        job_id: `job_${Date.now().toString(36)}`,
        status: 'completed',
        algorithm: algorithm.toUpperCase(),
        result: {
            optimal_value: -(Math.random() * size + size).toFixed(4),
            optimal_solution: Array.from({ length: size }, () => Math.round(Math.random())),
            iterations: Math.floor(Math.random() * 50) + 20,
            optimization_time_ms: (Math.random() * 500 + 100).toFixed(2)
        },
        encryption: {
            algorithm: 'ML-KEM-768',
            key_exchange_time_ms: (Math.random() * 5 + 1).toFixed(2),
            signature_verified: true
        },
        backend: {
            name: 'local_simulator',
            shots_executed: 1024,
            fidelity: 0.98
        }
    };

    responseEl.textContent = JSON.stringify(response, null, 2);

    // Switch to response tab
    document.querySelectorAll('.demo-tab').forEach(t => t.classList.remove('active'));
    document.querySelector('.demo-tab[data-tab="response"]').classList.add('active');
    document.querySelectorAll('.demo-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('demo-response').classList.add('active');

    // Update status
    statusEl.className = 'demo-status success';
    statusEl.innerHTML = `<span class="status-icon">✓</span><span class="status-text">Optimization completed in ${response.result.optimization_time_ms}ms</span>`;
    runBtn.disabled = false;

    // Update visualization
    drawOptimizationResult(response.result.optimal_solution);
}

async function simulateProgress(statusEl) {
    const stages = [
        'Encrypting problem data with ML-KEM-768...',
        'Submitting to quantum backend...',
        'Initializing quantum circuit...',
        'Running QAOA optimization...',
        'Processing results...',
        'Verifying ML-DSA signature...'
    ];

    for (const stage of stages) {
        statusEl.innerHTML = `<span class="status-icon">⏳</span><span class="status-text">${stage}</span>`;
        await sleep(300 + Math.random() * 400);
    }
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function initDemoCanvas() {
    const canvas = document.getElementById('demo-canvas');
    if (!canvas) return;

    // Set canvas size properly
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;

    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    // Draw initial graph
    drawGraph(ctx, rect.width, rect.height, 5, [0, 1, 0, 1, 0]);
}

function drawOptimizationResult(solution) {
    const canvas = document.getElementById('demo-canvas');
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;

    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    // Switch to visualization tab
    document.querySelectorAll('.demo-tab').forEach(t => t.classList.remove('active'));
    document.querySelector('.demo-tab[data-tab="visualization"]')?.classList.add('active');
    document.querySelectorAll('.demo-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('demo-visualization')?.classList.add('active');

    // Small delay to ensure panel is visible before drawing
    setTimeout(() => {
        const newRect = canvas.getBoundingClientRect();
        canvas.width = newRect.width * dpr;
        canvas.height = newRect.height * dpr;
        ctx.scale(dpr, dpr);
        drawGraph(ctx, newRect.width, newRect.height, solution.length, solution);
    }, 50);
}

function drawGraph(ctx, width, height, numNodes, solution) {
    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.35;

    // Calculate node positions
    const nodes = [];
    for (let i = 0; i < numNodes; i++) {
        const angle = (2 * Math.PI * i / numNodes) - Math.PI / 2;
        nodes.push({
            x: centerX + radius * Math.cos(angle),
            y: centerY + radius * Math.sin(angle),
            partition: solution[i]
        });
    }

    // Draw edges with glow effect
    ctx.shadowBlur = 10;
    ctx.shadowColor = 'rgba(6, 182, 212, 0.5)';

    for (let i = 0; i < numNodes; i++) {
        const j = (i + 1) % numNodes;
        const isCut = nodes[i].partition !== nodes[j].partition;

        ctx.beginPath();
        ctx.moveTo(nodes[i].x, nodes[i].y);
        ctx.lineTo(nodes[j].x, nodes[j].y);

        if (isCut) {
            ctx.strokeStyle = '#06b6d4';
            ctx.lineWidth = 3;
            ctx.shadowBlur = 15;
            ctx.shadowColor = 'rgba(6, 182, 212, 0.6)';
        } else {
            ctx.strokeStyle = 'rgba(99, 102, 241, 0.4)';
            ctx.lineWidth = 2;
            ctx.shadowBlur = 0;
        }
        ctx.stroke();
    }

    // Draw some cross-edges
    ctx.shadowBlur = 0;
    for (let i = 0; i < numNodes - 2; i++) {
        const j = i + 2;
        const isCut = nodes[i].partition !== nodes[j].partition;

        ctx.beginPath();
        ctx.moveTo(nodes[i].x, nodes[i].y);
        ctx.lineTo(nodes[j].x, nodes[j].y);

        if (isCut) {
            ctx.strokeStyle = 'rgba(6, 182, 212, 0.7)';
            ctx.lineWidth = 2;
        } else {
            ctx.strokeStyle = 'rgba(99, 102, 241, 0.25)';
            ctx.lineWidth = 1;
        }
        ctx.stroke();
    }

    // Draw nodes with gradient and glow
    nodes.forEach((node, i) => {
        // Glow effect
        ctx.shadowBlur = 20;
        ctx.shadowColor = node.partition === 0 ? 'rgba(99, 102, 241, 0.6)' : 'rgba(139, 92, 246, 0.6)';

        ctx.beginPath();
        ctx.arc(node.x, node.y, 20, 0, 2 * Math.PI);

        const gradient = ctx.createRadialGradient(
            node.x - 5, node.y - 5, 0,
            node.x, node.y, 20
        );

        if (node.partition === 0) {
            gradient.addColorStop(0, '#a5b4fc');
            gradient.addColorStop(0.7, '#6366f1');
            gradient.addColorStop(1, '#4f46e5');
        } else {
            gradient.addColorStop(0, '#c4b5fd');
            gradient.addColorStop(0.7, '#8b5cf6');
            gradient.addColorStop(1, '#7c3aed');
        }

        ctx.fillStyle = gradient;
        ctx.fill();

        // Border
        ctx.shadowBlur = 0;
        ctx.strokeStyle = node.partition === 0 ? '#818cf8' : '#a78bfa';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Node label
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 14px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(i.toString(), node.x, node.y);
    });
}

function copyDemoCode(type) {
    const codeEl = document.getElementById(`demo-${type}-code`);
    if (codeEl) {
        navigator.clipboard.writeText(codeEl.textContent);

        // Show feedback
        const btn = codeEl.parentElement.querySelector('.copy-btn');
        const originalText = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => btn.textContent = originalText, 1500);
    }
}

/**
 * Live Metrics Animation
 */
function initLiveMetrics() {
    const metricsElements = {
        jobs: document.getElementById('live-jobs'),
        today: document.getElementById('live-today'),
        latency: document.getElementById('live-latency'),
        success: document.getElementById('live-success')
    };

    if (!metricsElements.jobs) return;

    // Simulate live updates
    setInterval(() => {
        // Random fluctuations
        const jobsDelta = Math.floor(Math.random() * 10) - 3;
        const currentJobs = parseInt(metricsElements.jobs.textContent) || 247;
        metricsElements.jobs.textContent = Math.max(200, Math.min(350, currentJobs + jobsDelta));

        const todayDelta = Math.floor(Math.random() * 5);
        const currentToday = parseInt(metricsElements.today.textContent.replace(/,/g, '')) || 12847;
        metricsElements.today.textContent = (currentToday + todayDelta).toLocaleString();

        const latency = Math.floor(Math.random() * 15) + 18;
        metricsElements.latency.textContent = `${latency}ms`;

        const success = (99.5 + Math.random() * 0.4).toFixed(1);
        metricsElements.success.textContent = `${success}%`;
    }, 3000);

    // Draw mini chart
    drawMetricsChart();
}

function drawMetricsChart() {
    const canvas = document.getElementById('metrics-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.offsetWidth;
    const height = canvas.offsetHeight;

    canvas.width = width * 2;
    canvas.height = height * 2;
    ctx.scale(2, 2);

    // Generate random data points
    const points = [];
    for (let i = 0; i < 20; i++) {
        points.push(30 + Math.random() * 60);
    }

    // Draw gradient background
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, 'rgba(99, 102, 241, 0.3)');
    gradient.addColorStop(1, 'rgba(99, 102, 241, 0)');

    ctx.beginPath();
    ctx.moveTo(0, height);

    points.forEach((point, i) => {
        const x = (i / (points.length - 1)) * width;
        const y = height - (point / 100) * height;

        if (i === 0) {
            ctx.lineTo(x, y);
        } else {
            const prevX = ((i - 1) / (points.length - 1)) * width;
            const prevY = height - (points[i - 1] / 100) * height;
            const cpX = (prevX + x) / 2;
            ctx.bezierCurveTo(cpX, prevY, cpX, y, x, y);
        }
    });

    ctx.lineTo(width, height);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw line
    ctx.beginPath();
    points.forEach((point, i) => {
        const x = (i / (points.length - 1)) * width;
        const y = height - (point / 100) * height;

        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            const prevX = ((i - 1) / (points.length - 1)) * width;
            const prevY = height - (points[i - 1] / 100) * height;
            const cpX = (prevX + x) / 2;
            ctx.bezierCurveTo(cpX, prevY, cpX, y, x, y);
        }
    });

    ctx.strokeStyle = '#6366f1';
    ctx.lineWidth = 2;
    ctx.stroke();
}

// Initialize demo on load
document.addEventListener('DOMContentLoaded', () => {
    initInteractiveDemo();
});

/**
 * Console Easter Egg
 */
console.log(`
%c QuantumSafe Optimize 
%c Quantum-Safe Secure Optimization Platform

%c🔐 Post-Quantum Cryptography: ML-KEM-768, ML-DSA-65
%c📡 API: http://localhost:8000
%c📖 Docs: http://localhost:8000/docs
%c⚛️ Backends: IBM Quantum, AWS Braket, Azure Quantum, D-Wave

%c Built with ❤️ for the post-quantum era
`,
    'font-size: 24px; font-weight: bold; background: linear-gradient(90deg, #6366f1, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent;',
    'font-size: 12px; color: #888;',
    'font-size: 11px; color: #10b981;',
    'font-size: 11px; color: #06b6d4;',
    'font-size: 11px; color: #6366f1;',
    'font-size: 11px; color: #8b5cf6;',
    'font-size: 10px; color: #666; font-style: italic;'
);

