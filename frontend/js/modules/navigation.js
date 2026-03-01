/**
 * Navigation Module
 * Handles sidebar navigation and section management
 */

import { STATE } from './config.js';

/**
 * Initialize navigation handlers
 */
export function initNavigation() {
    // Sidebar navigation
    document.querySelectorAll('.nav-item, [data-section]').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const section = item.dataset.section;
            if (section) {
                navigateToSection(section);

                // Handle algorithm type selection for new job
                if (section === 'new-job' && item.dataset.type) {
                    setTimeout(() => {
                        const typeSelect = document.getElementById('problem-type');
                        if (typeSelect) {
                            typeSelect.value = item.dataset.type;
                            typeSelect.dispatchEvent(new Event('change'));
                        }
                    }, 100);
                }
            }
        });
    });

    // Sidebar toggle for mobile with backdrop
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    const sidebarBackdrop = document.getElementById('sidebar-backdrop');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            sidebarBackdrop?.classList.toggle('active', sidebar.classList.contains('open'));
            document.body.classList.toggle('sidebar-open', sidebar.classList.contains('open'));
        });
    }

    // Close sidebar when clicking backdrop
    if (sidebarBackdrop) {
        sidebarBackdrop.addEventListener('click', () => {
            sidebar?.classList.remove('open');
            sidebarBackdrop.classList.remove('active');
            document.body.classList.remove('sidebar-open');
        });
    }

    // Close sidebar when clicking nav item on mobile
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 1024) {
                sidebar?.classList.remove('open');
                sidebarBackdrop?.classList.remove('active');
                document.body.classList.remove('sidebar-open');
            }
        });
    });
}

/**
 * Navigate to a specific section
 */
export function navigateToSection(section) {
    // Update active nav item
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.section === section);
    });

    // Update section visibility
    document.querySelectorAll('.dashboard-section').forEach(sec => {
        sec.classList.toggle('active', sec.id === `section-${section}`);
    });

    // Update page title
    const titles = {
        'overview': 'Overview',
        'new-job': 'New Job',
        'jobs': 'My Jobs',
        'job-details': 'Job Details',
        'qaoa': 'QAOA',
        'vqe': 'VQE',
        'annealing': 'Quantum Annealing',
        'security': 'Security',
        'settings': 'Settings'
    };

    document.getElementById('page-title').textContent = titles[section] || section;
    STATE.currentSection = section;

    // Close mobile sidebar
    document.querySelector('.sidebar')?.classList.remove('open');
}

// Make globally accessible
window.navigateToSection = navigateToSection;
