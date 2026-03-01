/**
 * Search & Filter Module
 * Handles job search and filtering functionality
 */

import { STATE } from './config.js';
import { debounce } from './utils.js';

// Forward declaration - will be set by jobs module
let loadJobsCallback = null;

export function setLoadJobsCallback(callback) {
    loadJobsCallback = callback;
}

/**
 * Initialize search input handlers
 */
export function initSearch() {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', debounce((e) => {
            STATE.searchQuery = e.target.value.toLowerCase();
            // Reload with server-side filtering
            STATE.currentPage = 1;
            if (loadJobsCallback) loadJobsCallback(true);
        }, 500));

        // Enter key triggers immediate search
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                STATE.searchQuery = e.target.value.toLowerCase();
                STATE.currentPage = 1;
                if (loadJobsCallback) loadJobsCallback(true);
            }
        });
    }

    // Status filter - server-side
    const statusFilter = document.getElementById('filter-status');
    if (statusFilter) {
        statusFilter.addEventListener('change', (e) => {
            STATE.filterStatus = e.target.value;
            STATE.currentPage = 1;
            if (loadJobsCallback) loadJobsCallback(true);
        });
    }

    // Type filter - server-side
    const typeFilter = document.getElementById('filter-type');
    if (typeFilter) {
        typeFilter.addEventListener('change', (e) => {
            STATE.filterType = e.target.value;
            STATE.currentPage = 1;
            if (loadJobsCallback) loadJobsCallback(true);
        });
    }
}

/**
 * Initialize mobile search toggle
 */
export function initMobileSearch() {
    const mobileSearchToggle = document.getElementById('mobile-search-toggle');
    const searchBox = document.getElementById('search-box');
    const searchInput = document.getElementById('search-input');

    if (mobileSearchToggle && searchBox) {
        mobileSearchToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            searchBox.classList.toggle('mobile-active');
            if (searchBox.classList.contains('mobile-active')) {
                searchInput?.focus();
            }
        });

        // Close mobile search when clicking outside
        document.addEventListener('click', (e) => {
            if (!searchBox.contains(e.target) && !mobileSearchToggle.contains(e.target)) {
                searchBox.classList.remove('mobile-active');
            }
        });

        // Close on escape
        searchInput?.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                searchBox.classList.remove('mobile-active');
            }
        });
    }
}

/**
 * Filter jobs client-side
 */
export function filterJobs(jobs) {
    return jobs.filter(job => {
        // Search filter
        const matchesSearch = STATE.searchQuery === '' ||
            job.id?.toLowerCase().includes(STATE.searchQuery) ||
            job.job_id?.toLowerCase().includes(STATE.searchQuery) ||
            job.problem_type?.toLowerCase().includes(STATE.searchQuery) ||
            job.status?.toLowerCase().includes(STATE.searchQuery);

        // Status filter
        const matchesStatus = STATE.filterStatus === 'all' ||
            job.status?.toLowerCase() === STATE.filterStatus.toLowerCase();

        // Type filter
        const matchesType = STATE.filterType === 'all' ||
            job.problem_type?.toLowerCase() === STATE.filterType.toLowerCase();

        return matchesSearch && matchesStatus && matchesType;
    });
}

/**
 * Clear all filters
 */
export function clearFilters() {
    STATE.searchQuery = '';
    STATE.filterStatus = 'all';
    STATE.filterType = 'all';

    const searchInput = document.querySelector('.search-box input');
    const statusFilter = document.getElementById('filter-status');
    const typeFilter = document.getElementById('filter-type');

    if (searchInput) searchInput.value = '';
    if (statusFilter) statusFilter.value = 'all';
    if (typeFilter) typeFilter.value = 'all';

    if (loadJobsCallback) loadJobsCallback(true);
}

// Make globally accessible
window.clearFilters = clearFilters;
