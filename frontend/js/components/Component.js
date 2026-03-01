/**
 * QuantumSafe Component System
 * Base component class for all UI components
 *
 * Features:
 * - Lifecycle management (mount, update, unmount)
 * - Event handling with delegation
 * - State management with reactivity
 * - Component composition
 */

export class Component {
  constructor(props = {}) {
    this.props = props;
    this.state = {};
    this.element = null;
    this.children = [];
    this.subscribers = [];
    this.isMounted = false;
    this._eventCleanups = []; // Track event listeners for cleanup
    this._updateQueued = false; // Batch update flag
  }

  // Lifecycle hooks
  componentDidMount() {
    // Override in subclass
  }

  componentDidUpdate(prevProps, prevState) {
    // Override in subclass
  }

  componentWillUnmount() {
    // Override in subclass
  }

  // State management with reactivity and batched updates
  setState(newState) {
    const prevState = { ...this.state };
    this.state = typeof newState === 'function'
      ? newState(this.state)
      : { ...this.state, ...newState };

    // Notify subscribers
    this.subscribers.forEach(callback => callback(this.state, prevState));

    // Batch updates: only render once per microtask
    if (this.isMounted && !this._updateQueued) {
      this._updateQueued = true;
      queueMicrotask(() => {
        this._updateQueued = false;
        if (this.isMounted) {
          this.componentDidUpdate(this.props, prevState);
          this.render();
        }
      });
    }
  }

  subscribe(callback) {
    this.subscribers.push(callback);
    return () => {
      this.subscribers = this.subscribers.filter(cb => cb !== callback);
    };
  }

  // Render the component (must be implemented by subclass)
  render() {
    throw new Error('Component subclass must implement render()');
  }

  // Mount component to DOM
  mount(container) {
    if (!container) {
      throw new Error('Container element is required');
    }

    this.element = container;
    this.render();
    this.isMounted = true;
    this.componentDidMount();

    // Mount children
    this.children.forEach(child => {
      if (child instanceof Component && child.element) {
        child.mount(child.element);
      }
    });

    return this.element;
  }

  // Update component props
  updateProps(newProps) {
    const prevProps = { ...this.props };
    this.props = { ...this.props, ...newProps };

    if (this.isMounted) {
      this.componentDidUpdate(prevProps, this.state);
      this.render();
    }
  }

  // Unmount component with full cleanup
  unmount() {
    this.componentWillUnmount();
    this.isMounted = false;

    // Clean up all tracked event listeners
    this._eventCleanups.forEach(cleanup => cleanup());
    this._eventCleanups = [];

    // Clear subscribers
    this.subscribers = [];

    // Unmount children
    this.children.forEach(child => {
      if (child instanceof Component) {
        child.unmount();
      }
    });

    // Clear element
    if (this.element) {
      this.element.innerHTML = '';
    }
  }

  // Event handler factory with automatic cleanup tracking
  addEvent(element, event, handler, options = {}) {
    const wrappedHandler = (e) => {
      if (!options.allowDefault) e.preventDefault();
      try {
        handler(e);
      } catch (error) {
        console.error(`Component ${this.constructor.name} event error:`, error);
        this.handleError(error);
      }
    };

    element.addEventListener(event, wrappedHandler, options);
    const cleanup = () => element.removeEventListener(event, wrappedHandler, options);
    this._eventCleanups.push(cleanup);
    return cleanup;
  }

  // Error handling
  handleError(error) {
    // Emit global error event for logging
    window.dispatchEvent(new CustomEvent('component-error', {
      detail: {
        component: this.constructor.name,
        error: error.message,
        stack: error.stack
      }
    }));
  }

  // Create child component
  createChild(ComponentClass, props = {}, container = null) {
    const child = new ComponentClass(props);
    this.children.push(child);

    if (container) {
      child.element = container;
    }

    return child;
  }

  // Destroy child component
  destroyChild(child) {
    if (child instanceof Component) {
      child.unmount();
      this.children = this.children.filter(c => c !== child);
    }
  }

  // Utility: Safe access to nested properties
  get(path, defaultValue = undefined) {
    const keys = path.split('.');
    let result = this.state;

    for (const key of keys) {
      if (result == null || typeof result !== 'object') {
        return defaultValue;
      }
      result = result[key];
    }

    return result !== undefined ? result : defaultValue;
  }

  // Utility: Debounce function
  debounce(func, wait) {
    let timeout;
    return (...args) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  }

  // Utility: Throttle function
  throttle(func, limit) {
    let inThrottle;
    return (...args) => {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    };
  }
}

// Component lifecycle constants
Component.Lifecycle = {
  MOUNT: 'componentDidMount',
  UPDATE: 'componentDidUpdate',
  UNMOUNT: 'componentWillUnmount',
  RENDER: 'render'
};

export default Component;
