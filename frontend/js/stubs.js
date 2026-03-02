/**
 * Stubs for missing functions to prevent console errors
 * These will be loaded by the main component system
 */

// Auth Modal stubs
window.openAuthModal = function() {
    console.warn('openAuthModal: AuthModal component not loaded');
    alert('Authentication functionality requires full component system');
    return false;
};

window.switchAuthTab = function(tab) {
    console.warn('switchAuthTab: AuthModal component not loaded');
    const signinTab = document.querySelector('.auth-tab[data-tab="signin"]');
    const signupTab = document.querySelector('.auth-tab[data-tab="signup"]');
    
    if (signinTab && signupTab) {
        if (tab === 'signin') {
            signinTab.classList.add('active');
            signupTab.classList.remove('active');
        } else {
            signupTab.classList.add('active');
            signinTab.classList.remove('active');
        }
    }
    return false;
};

window.closeAuthModal = function() {
    console.warn('closeAuthModal: AuthModal component not loaded');
    const modal = document.querySelector('.auth-modal');
    if (modal) {
        modal.classList.remove('active');
    }
    return false;
};

window.goToDashboard = function() {
    console.log('Redirecting to dashboard...');
    window.location.href = 'dashboard.html';
};

// Demo optimization stub
window.runDemoOptimization = function() {
    console.warn('runDemoOptimization: Demo functionality not available in stub mode');
    alert('Demo optimization requires full backend integration');
    return false;
};

// Toast stubs
window.showToast = function(type, title, message, duration) {
    const colors = {
        error: '#ef4444',
        success: '#4b5563',
        warning: '#f59e0b',
        info: '#3b82f6'
    };

    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${colors[type] || '#6b7280'};
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
        animation: slideIn 0.3s ease-out;
        max-width: 400px;
    `;
    toast.innerHTML = `<strong>${title}</strong><br/>${message}`;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, duration || 5000);
};

// Add animation styles
if (!document.querySelector('#toast-styles')) {
    const style = document.createElement('style');
    style.id = 'toast-styles';
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
    `;
    document.head.appendChild(style);
}

console.log('✓ Stubs loaded successfully');
