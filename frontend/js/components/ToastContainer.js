/**
 * Toast Notification Component
 * Displays temporary notifications to users
 *
 * Features:
 * - Auto-dismiss after timeout
 * - Multiple toast types (success, error, warning, info)
 * - Action buttons support
 * - Queue management for multiple toasts
 * - Smooth animations
 */

import Component from './Component.js';

export class ToastContainer extends Component {
  constructor(props = {}) {
    super(props);
    this.toasts = [];
    this.maxToasts = props.maxToasts || 5;
    this.defaultDuration = props.defaultDuration || 5000;
    this.position = props.position || 'top-right';
  }

  render() {
    const containerClasses = ['toast-container', `toast-container-${this.position}`];

    this.element.innerHTML = `
      <div class="${containerClasses.join(' ')}">
        <div class="toast-list"></div>
      </div>
    `;
  }

  // Show a new toast
  show(options) {
    const {
      type = 'info',
      title = '',
      message = '',
      duration = this.defaultDuration,
      actions = [],
      persistent = false
    } = options;

    const toast = {
      id: `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      type,
      title,
      message,
      duration,
      actions,
      persistent,
      createdAt: Date.now()
    };

    // Remove oldest toast if at max capacity
    if (this.toasts.length >= this.maxToasts) {
      this.dismiss(this.toasts[0].id);
    }

    this.toasts.push(toast);
    this.renderToastItem(toast);

    // Auto-dismiss if not persistent
    if (!persistent && duration > 0) {
      setTimeout(() => {
        this.dismiss(toast.id);
      }, duration);
    }

    return toast.id;
  }

  // Render a single toast item
  renderToastItem(toast) {
    const toastList = this.element.querySelector('.toast-list');
    if (!toastList) return;

    const typeIcons = {
      success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
      error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
      warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
      info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
    };

    const toastElement = document.createElement('div');
    toastElement.className = `toast toast-${toast.type}`;
    toastElement.dataset.toastId = toast.id;
    toastElement.style.opacity = '0';
    toastElement.style.transform = 'translateX(100%)';

    const actionsHtml = toast.actions.length > 0
      ? `<div class="toast-actions">
          ${toast.actions.map(action => `
            <button class="toast-action-btn" data-action="${action.id}">
              ${action.label}
            </button>
          `).join('')}
        </div>`
      : '';

    toastElement.innerHTML = `
      <div class="toast-icon">${typeIcons[toast.type]}</div>
      <div class="toast-content">
        ${toast.title ? `<div class="toast-title">${this.escapeHtml(toast.title)}</div>` : ''}
        <div class="toast-message">${this.escapeHtml(toast.message)}</div>
        ${actionsHtml}
      </div>
      <button class="toast-close" aria-label="Close">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
      <div class="toast-progress" style="animation-duration: ${toast.duration}ms"></div>
    `;

    // Add close button handler
    const closeBtn = toastElement.querySelector('.toast-close');
    this.addEvent(closeBtn, 'click', () => this.dismiss(toast.id));

    // Add action button handlers
    toast.actions.forEach(action => {
      const actionBtn = toastElement.querySelector(`[data-action="${action.id}"]`);
      if (actionBtn && action.handler) {
        this.addEvent(actionBtn, 'click', (e) => {
          e.stopPropagation();
          action.handler(toast.id);
          if (!action.persistent) {
            this.dismiss(toast.id);
          }
        });
      }
    });

    toastList.appendChild(toastElement);

    // Trigger animation
    requestAnimationFrame(() => {
      toastElement.style.opacity = '1';
      toastElement.style.transform = 'translateX(0)';
    });

    // Emit toast show event
    window.dispatchEvent(new CustomEvent('toast-show', {
      detail: { toast }
    }));
  }

  // Dismiss a toast
  dismiss(toastId) {
    const toastIndex = this.toasts.findIndex(t => t.id === toastId);
    if (toastIndex === -1) return;

    const toast = this.toasts[toastIndex];
    this.toasts.splice(toastIndex, 1);

    const toastElement = this.element.querySelector(`[data-toast-id="${toastId}"]`);
    if (toastElement) {
      toastElement.style.opacity = '0';
      toastElement.style.transform = 'translateX(100%)';

      setTimeout(() => {
        toastElement.remove();
      }, 300);
    }

    // Emit toast dismiss event
    window.dispatchEvent(new CustomEvent('toast-dismiss', {
      detail: { toast }
    }));
  }

  // Dismiss all toasts
  dismissAll() {
    const toastIds = this.toasts.map(t => t.id);
    toastIds.forEach(id => this.dismiss(id));
  }

  // Update an existing toast
  update(toastId, updates) {
    const toast = this.toasts.find(t => t.id === toastId);
    if (!toast) return;

    Object.assign(toast, updates);

    // Re-render the toast element
    this.dismiss(toastId);
    this.renderToastItem(toast);
  }

  // Convenience methods
  success(title, message, duration) {
    return this.show({ type: 'success', title, message, duration });
  }

  error(title, message, duration) {
    return this.show({ type: 'error', title, message, duration });
  }

  warning(title, message, duration) {
    return this.show({ type: 'warning', title, message, duration });
  }

  info(title, message, duration) {
    return this.show({ type: 'info', title, message, duration });
  }

  // Escape HTML to prevent XSS
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Global toast container instance
let globalToastContainer = null;

export function initToasts(container = document.body, options = {}) {
  globalToastContainer = new ToastContainer(options);
  globalToastContainer.mount(container);
  return globalToastContainer;
}

export function showToast(type, title, message, duration) {
  if (!globalToastContainer) {
    initToasts();
  }
  return globalToastContainer.show({ type, title, message, duration });
}

export default ToastContainer;
