/**
 * Modal Component
 * Lightweight modal dialog component
 *
 * Features:
 * - Accessible (focus management, keyboard support)
 * - Customizable size and position
 * - Animation support
 * - Backdrop click to close
 * - Multiple modal stacking
 */

import Component from './Component.js';

export class Modal extends Component {
  constructor(props = {}) {
    super(props);

    this.state = {
      isOpen: false,
      title: props.title || '',
      size: props.size || 'medium', // small, medium, large, fullscreen
      closable: props.closable !== false,
      showBackdrop: props.showBackdrop !== false,
      closeOnBackdropClick: props.closeOnBackdropClick !== false,
      closeOnEscape: props.closeOnEscape !== false
    };

    this.backdropElement = null;
    this.previousActiveElement = null;
    this.focusableElements = [];
    this.firstFocusable = null;
    this.lastFocusable = null;
  }

  render() {
    if (!this.state.isOpen) {
      this.element.innerHTML = '';
      return;
    }

    const sizeClasses = {
      small: 'modal-sm',
      medium: 'modal-md',
      large: 'modal-lg',
      fullscreen: 'modal-fullscreen'
    };

    this.element.innerHTML = `
      <div class="modal-overlay${this.state.showBackdrop ? ' modal-backdrop' : ''}" data-modal-overlay>
        <div class="modal ${sizeClasses[this.state.size]}" role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div class="modal-header">
            <h2 id="modal-title" class="modal-title">${this.escapeHtml(this.state.title)}</h2>
            ${this.state.closable ? `
              <button class="modal-close" aria-label="Close modal" data-modal-close>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"/>
                  <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            ` : ''}
          </div>
          <div class="modal-body" data-modal-body></div>
          <div class="modal-footer" data-modal-footer></div>
        </div>
      </div>
    `;

    // Set up event handlers
    this.setupEventHandlers();
  }

  setupEventHandlers() {
    const overlay = this.element.querySelector('[data-modal-overlay]');
    const closeBtn = this.element.querySelector('[data-modal-close]');

    // Close button
    if (closeBtn && this.state.closable) {
      this.addEvent(closeBtn, 'click', () => this.close());
    }

    // Backdrop click
    if (overlay && this.state.closeOnBackdropClick) {
      this.addEvent(overlay, 'click', (e) => {
        if (e.target === overlay) {
          this.close();
        }
      });
    }

    // Escape key
    if (this.state.closeOnEscape) {
      this.addEvent(document, 'keydown', (e) => {
        if (e.key === 'Escape' && this.state.isOpen) {
          this.close();
        }
      });
    }

    // Focus trap
    this.setupFocusTrap();
  }

  setupFocusTrap() {
    const modal = this.element.querySelector('.modal');
    if (!modal) return;

    // Get all focusable elements
    this.focusableElements = modal.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );

    this.firstFocusable = this.focusableElements[0];
    this.lastFocusable = this.focusableElements[this.focusableElements.length - 1];

    // Handle tab key to trap focus
    this.addEvent(modal, 'keydown', (e) => {
      if (e.key !== 'Tab') return;

      if (e.shiftKey) {
        // Shift+Tab: move to previous element
        if (document.activeElement === this.firstFocusable) {
          e.preventDefault();
          this.lastFocusable.focus();
        }
      } else {
        // Tab: move to next element
        if (document.activeElement === this.lastFocusable) {
          e.preventDefault();
          this.firstFocusable.focus();
        }
      }
    });
  }

  // Open the modal
  open(options = {}) {
    if (options.title !== undefined) {
      this.updateProps({ title: options.title });
    }

    this.setState({ isOpen: true });

    // Store previous focused element
    this.previousActiveElement = document.activeElement;

    // Prevent body scroll
    document.body.style.overflow = 'hidden';

    // Focus management
    requestAnimationFrame(() => {
      const modal = this.element.querySelector('.modal');
      if (modal) {
        // Focus first focusable element or modal itself
        if (this.firstFocusable) {
          this.firstFocusable.focus();
        } else {
          modal.setAttribute('tabindex', '-1');
          modal.focus();
        }
      }

      // Emit open event
      window.dispatchEvent(new CustomEvent('modal-open', {
        detail: { modal: this }
      }));
    });
  }

  // Close the modal
  close() {
    if (!this.state.isOpen) return;

    this.setState({ isOpen: false });

    // Restore body scroll
    document.body.style.overflow = '';

    // Restore focus
    if (this.previousActiveElement) {
      requestAnimationFrame(() => {
        this.previousActiveElement.focus();
      });
    }

    // Emit close event
    window.dispatchEvent(new CustomEvent('modal-close', {
      detail: { modal: this }
    }));
  }

  // Set modal content
  setContent(content) {
    const modalBody = this.element.querySelector('[data-modal-body]');
    if (modalBody) {
      modalBody.innerHTML = content;
    }

    // Re-setup focus trap after content changes
    setTimeout(() => this.setupFocusTrap(), 0);
  }

  // Set modal footer button(s)
  setFooter(buttons = []) {
    const modalFooter = this.element.querySelector('[data-modal-footer]');
    if (!modalFooter) return;

    modalFooter.innerHTML = buttons.map(btn => `
      <button class="btn btn-${btn.variant || 'primary'}" data-modal-action="${btn.id || ''}">
        ${btn.icon ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${btn.icon}</svg>` : ''}
        ${btn.label}
      </button>
    `).join('');

    // Add button handlers
    buttons.forEach(btn => {
      const button = modalFooter.querySelector(`[data-modal-action="${btn.id}"]`);
      if (button && btn.handler) {
        this.addEvent(button, 'click', (e) => {
          const shouldClose = btn.handler(e);
          if (shouldClose !== false) {
            this.close();
          }
        });
      }
    });
  }

  // Update modal title
  setTitle(title) {
    this.setState({ title });
  }

  // Escape HTML to prevent XSS
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Dialog type modals
export class ConfirmModal extends Modal {
  constructor(props = {}) {
    super({
      size: 'small',
      ...props
    });
  }

  render() {
    super.render();

    if (!this.state.isOpen) return;

    const modalBody = this.element.querySelector('[data-modal-body]');
    if (modalBody) {
      modalBody.innerHTML = `
        <div class="confirm-modal-content">
          <div class="confirm-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
          </div>
          <p class="confirm-message">${this.escapeHtml(this.props.message || 'Are you sure?')}</p>
        </div>
      `;
    }

    this.setFooter([
      {
        id: 'cancel',
        label: 'Cancel',
        variant: 'outline',
        handler: () => this.props.onCancel?.() || false
      },
      {
        id: 'confirm',
        label: this.props.confirmText || 'Confirm',
        variant: 'primary',
        handler: () => this.props.onConfirm?.() || true
      }
    ]);
  }

  // Open and return a promise that resolves on confirm or rejects on cancel
  confirm(message, options = {}) {
    return new Promise((resolve, reject) => {
      this.updateProps({
        message,
        onConfirm: () => {
          resolve(true);
          this.close();
        },
        onCancel: () => {
          resolve(false);
          this.close();
        },
        ...options
      });

      this.open();
    });
  }
}

export default Modal;
