/**
 * Performance Optimization Module
 * Implements lazy loading, caching, and virtual scrolling
 */

import { STATE, CONFIG } from './config.js';

// Cache configuration
const CACHE_CONFIG = {
    defaultTTL: 60000, // 1 minute
    maxEntries: 100,
    staleWhileRevalidate: true
};

// In-memory cache
const memoryCache = new Map();
const cacheTimestamps = new Map();

// Virtual scroll state
let virtualScrollState = {
    containerHeight: 0,
    itemHeight: 72,
    visibleCount: 0,
    startIndex: 0,
    endIndex: 0,
    scrollTop: 0
};

// Lazy loaded modules registry
const lazyModules = new Map();

/**
 * Initialize performance optimizations
 */
export function initPerformanceOptimizations() {
    // Set up request caching
    initRequestCache();

    // Initialize virtual scrolling for job list
    initVirtualScrolling();

    // Set up lazy loading observers
    initLazyLoading();

    // Preload critical assets
    preloadCriticalAssets();

    // Set up cache cleanup
    setInterval(cleanupCache, CACHE_CONFIG.defaultTTL);

    console.log('[Performance] Optimizations initialized');
}

/**
 * Request Cache Implementation
 */
function initRequestCache() {
    // Intercept fetch for caching
    const originalFetch = window.fetch;
    window.fetch = async function(url, options = {}) {
        // Only cache GET requests
        if (options.method && options.method !== 'GET') {
            return originalFetch(url, options);
        }

        // Skip caching for WebSocket connections
        if (url.includes('/ws/') || url.includes('websocket')) {
            return originalFetch(url, options);
        }

        // Check cache
        const cacheKey = getCacheKey(url, options);
        const cached = getCachedResponse(cacheKey);

        if (cached && !isCacheExpired(cacheKey)) {
            // Return cached response but revalidate in background
            if (CACHE_CONFIG.staleWhileRevalidate) {
                revalidateInBackground(url, options, cacheKey);
            }
            return Promise.resolve(cached.clone());
        }

        // Make request
        try {
            const response = await originalFetch(url, options);
            if (response.ok) {
                cacheResponse(cacheKey, response.clone());
            }
            return response;
        } catch (error) {
            // Return stale cache if available
            if (cached) {
                console.log('[Cache] Returning stale cache due to error');
                return cached.clone();
            }
            throw error;
        }
    };
}

function getCacheKey(url, options) {
    const body = options.body ? JSON.stringify(options.body) : '';
    return `${url}:${body}`;
}

function getCachedResponse(key) {
    return memoryCache.get(key) || null;
}

function cacheResponse(key, response) {
    // Enforce max entries
    if (memoryCache.size >= CACHE_CONFIG.maxEntries) {
        const oldestKey = cacheTimestamps.keys().next().value;
        memoryCache.delete(oldestKey);
        cacheTimestamps.delete(oldestKey);
    }

    memoryCache.set(key, response);
    cacheTimestamps.set(key, Date.now());
}

function isCacheExpired(key) {
    const timestamp = cacheTimestamps.get(key);
    if (!timestamp) return true;
    return Date.now() - timestamp > CACHE_CONFIG.defaultTTL;
}

function revalidateInBackground(url, options, key) {
    originalFetch(url, options).then(response => {
        if (response.ok) {
            cacheResponse(key, response);
        }
    }).catch(() => {});
}

let originalFetch = window.fetch;

function cleanupCache() {
    const now = Date.now();
    for (const [key, timestamp] of cacheTimestamps.entries()) {
        if (now - timestamp > CACHE_CONFIG.defaultTTL * 2) {
            memoryCache.delete(key);
            cacheTimestamps.delete(key);
        }
    }
}

/**
 * Clear cache for specific pattern
 */
export function clearCache(pattern = '') {
    for (const key of memoryCache.keys()) {
        if (!pattern || key.includes(pattern)) {
            memoryCache.delete(key);
            cacheTimestamps.delete(key);
        }
    }
}

/**
 * Virtual Scrolling Implementation
 */
function initVirtualScrolling() {
    const container = document.querySelector('.jobs-table-container') || 
                      document.getElementById('jobs-table-container');

    if (!container) return;

    // Calculate item height based on rendered item
    const firstRow = container.querySelector('.job-row');
    if (firstRow) {
        virtualScrollState.itemHeight = firstRow.offsetHeight || 72;
    }

    // Set up scroll handler
    container.addEventListener('scroll', debounce(handleVirtualScroll, 16));

    // Calculate visible count
    virtualScrollState.containerHeight = container.clientHeight;
    virtualScrollState.visibleCount = Math.ceil(virtualScrollState.containerHeight / virtualScrollState.itemHeight) + 2;

    // Initial render
    handleVirtualScroll();
}

function handleVirtualScroll() {
    const container = document.querySelector('.jobs-table-container');
    if (!container) return;

    virtualScrollState.scrollTop = container.scrollTop;
    virtualScrollState.startIndex = Math.floor(virtualScrollState.scrollTop / virtualScrollState.itemHeight);
    virtualScrollState.endIndex = Math.min(
        virtualScrollState.startIndex + virtualScrollState.visibleCount,
        STATE.jobs.length
    );

    // Render visible items only
    renderVirtualItems();
}

function renderVirtualItems() {
    const tbody = document.getElementById('jobs-table-body');
    if (!tbody || STATE.jobs.length === 0) return;

    // Create fragment for batch DOM update
    const fragment = document.createDocumentFragment();

    // Add spacer for items before visible range
    const topSpacer = document.createElement('tr');
    topSpacer.className = 'virtual-scroll-spacer';
    topSpacer.style.height = `${virtualScrollState.startIndex * virtualScrollState.itemHeight}px`;
    fragment.appendChild(topSpacer);

    // Render visible items
    const visibleJobs = STATE.jobs.slice(
        virtualScrollState.startIndex,
        virtualScrollState.endIndex
    );

    visibleJobs.forEach((job, index) => {
        const actualIndex = virtualScrollState.startIndex + index;
        const row = createJobRow(job, actualIndex);
        fragment.appendChild(row);
    });

    // Add spacer for items after visible range
    const bottomSpacer = document.createElement('tr');
    bottomSpacer.className = 'virtual-scroll-spacer';
    const remainingItems = STATE.jobs.length - virtualScrollState.endIndex;
    bottomSpacer.style.height = `${remainingItems * virtualScrollState.itemHeight}px`;
    fragment.appendChild(bottomSpacer);

    // Batch DOM update
    tbody.innerHTML = '';
    tbody.appendChild(fragment);
}

function createJobRow(job, index) {
    const row = document.createElement('tr');
    row.className = `job-row ${job.status}`;
    row.dataset.jobId = job.job_id;
    row.innerHTML = `
        <td class="job-id-cell">${escapeHtml(job.job_id.substring(0, 12))}...</td>
        <td><span class="type-badge">${escapeHtml(job.problem_type)}</span></td>
        <td><span class="backend-badge">${escapeHtml(job.backend)}</span></td>
        <td><span class="status-badge ${escapeHtml(job.status)}">${escapeHtml(job.status)}</span></td>
        <td>${job.encrypted ? '<span class="encrypted-badge">🔐</span>' : '—'}</td>
        <td>${formatDate(job.created_at)}</td>
        <td class="actions-cell">
            <button class="btn btn-outline btn-sm" onclick="viewJobDetails('${escapeHtml(job.job_id)}')">
                <i class="fas fa-eye"></i>
            </button>
        </td>
    `;
    return row;
}

/**
 * Lazy Loading for Modules and Assets
 */
function initLazyLoading() {
    // Intersection Observer for lazy loading images
    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                if (img.dataset.src) {
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                    imageObserver.unobserve(img);
                }
            }
        });
    }, { rootMargin: '100px' });

    // Observe all lazy images
    document.querySelectorAll('img[data-src]').forEach(img => {
        imageObserver.observe(img);
    });

    // Intersection Observer for lazy loading sections
    const sectionObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const section = entry.target;
                if (section.dataset.lazyModule) {
                    loadModule(section.dataset.lazyModule);
                    section.removeAttribute('data-lazy-module');
                    sectionObserver.unobserve(section);
                }
            }
        });
    }, { rootMargin: '200px' });

    // Observe lazy sections
    document.querySelectorAll('[data-lazy-module]').forEach(section => {
        sectionObserver.observe(section);
    });
}

/**
 * Lazy load a module
 */
export async function loadModule(moduleName) {
    if (lazyModules.has(moduleName)) {
        return lazyModules.get(moduleName);
    }

    const modulePromise = import(`./${moduleName}.js`)
        .then(module => {
            lazyModules.set(moduleName, module);
            return module;
        })
        .catch(error => {
            console.error(`[Lazy] Failed to load module: ${moduleName}`, error);
            throw error;
        });

    lazyModules.set(moduleName, modulePromise);
    return modulePromise;
}

/**
 * Preload Critical Assets
 */
function preloadCriticalAssets() {
    // Preload fonts
    const fonts = [
        'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap',
        'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap'
    ];

    fonts.forEach(font => {
        const link = document.createElement('link');
        link.rel = 'preload';
        link.as = 'style';
        link.href = font;
        document.head.appendChild(link);
    });

    // Preload Chart.js if not already loaded
    if (!window.Chart) {
        const script = document.createElement('link');
        script.rel = 'preload';
        script.as = 'script';
        script.href = `https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js`;
        document.head.appendChild(script);
    }
}

/**
 * Debounce helper
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Escape HTML helper
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format date helper
 */
function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/**
 * Batch DOM updates using requestAnimationFrame
 */
export function batchUpdate(callback) {
    requestAnimationFrame(() => {
        // Double RAF for layout stability
        requestAnimationFrame(callback);
    });
}

/**
 * Throttle function for scroll/resize handlers
 */
export function throttle(func, limit) {
    let inThrottle;
    return function executedFunction(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Request idle callback with fallback
 */
export function requestIdleCallback(callback, options = {}) {
    if ('requestIdleCallback' in window) {
        return window.requestIdleCallback(callback, options);
    }
    return setTimeout(callback, 1);
}

/**
 * Cancel idle callback with fallback
 */
export function cancelIdleCallback(id) {
    if ('cancelIdleCallback' in window) {
        window.cancelIdleCallback(id);
    } else {
        clearTimeout(id);
    }
}

/**
 * Memory-efficient deep clone
 */
export function efficientClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;

    // Use structured clone if available
    if (typeof structuredClone === 'function') {
        return structuredClone(obj);
    }

    // Fallback to JSON
    return JSON.parse(JSON.stringify(obj));
}

/**
 * Performance metrics collector
 */
export function collectPerformanceMetrics() {
    const metrics = {};

    // Navigation timing
    if (performance.timing) {
        const timing = performance.timing;
        metrics.domContentLoaded = timing.domContentLoadedEventEnd - timing.navigationStart;
        metrics.loadComplete = timing.loadEventEnd - timing.navigationStart;
    }

    // Paint timing
    if (performance.getEntriesByType) {
        const paintEntries = performance.getEntriesByType('paint');
        paintEntries.forEach(entry => {
            metrics[entry.name] = entry.startTime;
        });
    }

    // Memory usage (if available)
    if (performance.memory) {
        metrics.memoryUsed = performance.memory.usedJSHeapSize;
        metrics.memoryTotal = performance.memory.totalJSHeapSize;
    }

    // Cache stats
    metrics.cacheSize = memoryCache.size;
    metrics.cacheHits = Array.from(cacheTimestamps.values()).filter(
        (ts, i) => ts > Date.now() - CACHE_CONFIG.defaultTTL
    ).length;

    return metrics;
}

// Log performance metrics in development
if (CONFIG.debug || localStorage.getItem('debug') === 'true') {
    setInterval(() => {
        const metrics = collectPerformanceMetrics();
        console.log('[Performance]', metrics);
    }, 60000);
}

export default {
    initPerformanceOptimizations,
    loadModule,
    clearCache,
    batchUpdate,
    throttle,
    requestIdleCallback,
    cancelIdleCallback,
    efficientClone,
    collectPerformanceMetrics
};
