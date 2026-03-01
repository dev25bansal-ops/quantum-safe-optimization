/**
 * Modal Utilities
 * Helper functions for common modal interactions
 */

import modalManager from './ModalManager.js';

/**
 * Show a simple alert modal
 */
export function alertDialog(title, message, options = {}) {
    return modalManager.alert(title, message, options);
}

/**
 * Show a confirmation modal
 * @returns {Promise<boolean>} Resolves to true if confirmed, false otherwise
 */
export function confirmDialog(title, message, options = {}) {
    return modalManager.confirm(title, message, options);
}

/**
 * Show a custom modal with body content
 */
export function showModal(title, body, options = {}) {
    const id = options.id || 'modal-' + Date.now();
    const modal = modalManager.create(id, {
        title,
        body,
        footer: options.footer || '',
        size: options.size || 'medium',
        props: options.props || {}
    });
    
    modalManager.open(id);
    
    return {
        close: () => modalManager.close(id),
        updateBody: (newBody) => {
            const bodyEl = modal.element.querySelector('[data-modal-body]');
            if (bodyEl) bodyEl.innerHTML = newBody;
        }
    };
}

/**
 * Show a form in a modal
 */
export function showFormModal(title, formHTML, onSubmit, options = {}) {
    const modalInstance = showModal(title, formHTML, {
        size: options.size || 'medium',
        footer: `
            <button class="btn btn-outline" data-modal-cancel>${options.cancelText || 'Cancel'}</button>
            <button class="btn btn-primary" data-modal-confirm>${options.confirmText || 'Submit'}</button>
        `
    });
    
    // Set up form submission
    setTimeout(() => {
        const form = document.querySelector('[data-modal-body] form');
        if (form) {
            const handler = (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData.entries());
                
                if (onSubmit(data, modalInstance) !== false) {
                    modalInstance.close();
                }
            };
            
            form.addEventListener('submit', handler);
            
            // Store handler for cleanup
            form._modalHandler = handler;
        }
    }, 0);
    
    return modalInstance;
}

/**
 * Show a loading modal
 */
export function showLoadingModal(title, message = 'Please wait...') {
    const id = 'loading-' + Date.now();
    const body = `
        <div class="modal-loading-content">
            <div class="spinner"></div>
            <p>${message}</p>
        </div>
    `;
    
    const modal = modalManager.create(id, {
        title,
        body,
        footer: '',
        closable: false,
        size: 'small'
    });
    
    modalManager.open(id);
    
    return {
        close: () => modalManager.close(id),
        updateMessage: (newMessage) => {
            const p = modal.element.querySelector('[data-modal-body] p');
            if (p) p.textContent = newMessage;
        },
        setProgress: (progress) => {
            const spinner = modal.element.querySelector('.spinner');
            if (spinner) {
                spinner.setAttribute('data-progress', progress);
                spinner.setAttribute('data-has-progress', 'true');
            }
        }
    };
}

/**
 * Show a success message
 */
export function showSuccess(title, message, options = {}) {
    const body = `
        <div class="modal-success-content">
            <div class="success-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20 6L9 17l-5-5"/>
                </svg>
            </div>
            <p>${message}</p>
        </div>
    `;
    
    return modalManager.alert(title, body, {
        confirmText: options.confirmText || 'OK',
        size: options.size || 'small'
    });
}

/**
 * Show an error message
 */
export function showError(title, message, options = {}) {
    const body = `
        <div class="modal-error-content">
            <div class="error-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
            </div>
            <p>${message}</p>
        </div>
    `;
    
    return modalManager.alert(title, body, {
        confirmText: options.confirmText || 'OK',
        size: options.size || 'small'
    });
}

/**
 * Show a warning message
 */
export function showWarning(title, message, options = {}) {
    const body = `
        <div class="modal-warning-content">
            <div class="warning-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                    <line x1="12" y1="9" x2="12" y2="13"/>
                    <line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
            </div>
            <p>${message}</p>
        </div>
    `;
    
    return modalManager.alert(title, body, {
        confirmText: options.confirmText || 'OK',
        size: options.size || 'small'
    });
}

// Export modal manager instance
export default modalManager;
