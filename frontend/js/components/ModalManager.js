/**
 * Modal Manager
 * Centralized modal management for QuantumSafe platform
 */

import { Modal, ConfirmModal } from './Modal.js';

class ModalManager {
    constructor() {
        this.modals = new Map();
        this.activeModals = [];
        this.container = null;
    }

    /**
     * Initialize modal manager with a container
     */
    init(container = document.body) {
        this.container = container;
        console.log('[ModalManager] Initialized');
    }

    /**
     * Register a modal instance
     */
    register(id, modal) {
        if (this.modals.has(id)) {
            console.warn(`[ModalManager] Modal "${id}" is already registered`);
            return false;
        }
        this.modals.set(id, modal);
        console.log(`[ModalManager] Registered modal "${id}"`);
        return true;
    }

    /**
     * Unregister and destroy a modal
     */
    unregister(id) {
        const modal = this.modals.get(id);
        if (modal) {
            modal.close();
            modal.unmount();
            this.modals.delete(id);
            this.activeModals = this.activeModals.filter(m => m !== id);
            console.log(`[ModalManager] Unregistered modal "${id}"`);
            return true;
        }
        return false;
    }

    /**
     * Open a modal by ID
     */
    open(id, props = {}) {
        const modal = this.modals.get(id);
        if (!modal) {
            console.error(`[ModalManager] Modal "${id}" not found`);
            return false;
        }

        // If modal is already open, return
        if (modal.state.isOpen) {
            return true;
        }

        // Update modal props and open
        modal.updateProps(props);
        modal.open();

        // Track active modal
        if (!this.activeModals.includes(id)) {
            this.activeModals.push(id);
        }

        console.log(`[ModalManager] Opened modal "${id}"`);
        return true;
    }

    /**
     * Close a modal by ID
     */
    close(id) {
        const modal = this.modals.get(id);
        if (!modal) {
            console.warn(`[ModalManager] Modal "${id}" not found`);
            return false;
        }

        modal.close();
        this.activeModals = this.activeModals.filter(m => m !== id);
        console.log(`[ModalManager] Closed modal "${id}"`);
        return true;
    }

    /**
     * Close all active modals
     */
    closeAll() {
        this.activeModals.forEach(id => {
            const modal = this.modals.get(id);
            if (modal) {
                modal.close();
            }
        });
        this.activeModals = [];
        console.log('[ModalManager] Closed all modals');
    }

    /**
     * Get a modal instance by ID
     */
    getModal(id) {
        return this.modals.get(id);
    }

    /**
     * Check if a modal is open
     */
    isOpen(id) {
        const modal = this.modals.get(id);
        return modal ? modal.state.isOpen : false;
    }

    /**
     * Create and register a new modal
     */
    create(id, config = {}) {
        let modal;

        if (config.type === 'confirm') {
            modal = new ConfirmModal({
                title: config.title || 'Confirm',
                message: config.message || '',
                confirmText: config.confirmText || 'Confirm',
                cancelText: config.cancelText || 'Cancel',
                onConfirm: config.onConfirm,
                onCancel: config.onCancel,
                ...config.props
            });
        } else {
            modal = new Modal({
                title: config.title || 'Modal',
                size: config.size || 'medium',
                body: config.body || '',
                footer: config.footer || '',
                ...config.props
            });
        }

        // Create wrapper element for modal
        const wrapper = document.createElement('div');
        wrapper.id = `modal-${id}`;
        wrapper.style.display = 'none';
        this.container.appendChild(wrapper);

        // Mount modal
        modal.mount(wrapper);

        // Register modal
        this.register(id, modal);

        return modal;
    }

    /**
     * Show an alert modal
     */
    alert(title, message, options = {}) {
        const id = 'alert-' + Date.now();
        return new Promise((resolve) => {
            const modal = this.create(id, {
                type: 'confirm',
                title: title,
                message: message,
                confirmText: options.confirmText || 'OK',
                cancelText: '',
                onConfirm: () => {
                    this.close(id);
                    this.unregister(id);
                    const wrapper = modal.element;
                    setTimeout(() => wrapper.remove(), 100);
                    if (options.onConfirm) options.onConfirm();
                    resolve(true);
                },
                size: options.size || 'small'
            });

            // Hide cancel button for simple alerts
            const cancelButton = modal.element.querySelector('[data-modal-cancel]');
            if (cancelButton) {
                cancelButton.style.display = 'none';
            }

            this.open(id);
        });
    }

    /**
     * Show a confirm modal (returns a promise)
     */
    confirm(title, message, options = {}) {
        return new Promise((resolve) => {
            const id = 'confirm-' + Date.now();
            const modal = this.create(id, {
                type: 'confirm',
                title: title,
                message: message,
                confirmText: options.confirmText || 'Confirm',
                cancelText: options.cancelText || 'Cancel',
                size: options.size || 'small',
                props: {
                    onConfirm: () => {
                        this.close(id);
                        this.unregister(id);
                        setTimeout(() => {
                            const wrapper = document.getElementById(`modal-${id}`);
                            if (wrapper) wrapper.remove();
                        }, 100);
                        resolve(true);
                        options.onConfirm && options.onConfirm();
                    },
                    onCancel: () => {
                        this.close(id);
                        this.unregister(id);
                        setTimeout(() => {
                            const wrapper = document.getElementById(`modal-${id}`);
                            if (wrapper) wrapper.remove();
                        }, 100);
                        resolve(false);
                        options.onCancel && options.onCancel();
                    }
                }
            });

            const wrapper = modal.element;
            this.open(id);
        });
    }
}

// Export singleton instance
const modalManager = new ModalManager();

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => modalManager.init());
} else {
    modalManager.init();
}

// Make globally accessible
window.modalManager = modalManager;

export { ModalManager };
export default modalManager;
