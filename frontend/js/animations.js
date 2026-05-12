/**
 * QuantumSafe Optimize - Scroll Animations
 * IntersectionObserver-based scroll-triggered animations
 */

(function () {
  'use strict';

  // Respect reduced motion preference
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReducedMotion) return;

  /**
   * Initialize scroll-triggered animations using IntersectionObserver
   */
  function initScrollAnimations() {
    const animatedElements = document.querySelectorAll(
      '.animate-on-scroll, .animate-slide-left, .animate-slide-right, .animate-scale, .animate-fade, .animate-zoom-fade'
    );

    if (!animatedElements.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('animate-visible');
            observer.unobserve(entry.target);
          }
        });
      },
      {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px',
      }
    );

    animatedElements.forEach((el) => observer.observe(el));
  }

  /**
   * Auto-apply animation classes to common elements if not already present
   * This ensures existing pages get animations without manual class additions
   */
  function autoApplyAnimations() {
    // Apply to feature cards
    document.querySelectorAll('.feature-card:not(.animate-on-scroll)').forEach((el) => {
      el.classList.add('animate-on-scroll');
    });

    // Apply to backend cards
    document.querySelectorAll('.backend-card:not(.animate-on-scroll)').forEach((el) => {
      el.classList.add('animate-on-scroll');
    });

    // Apply to pricing cards
    document.querySelectorAll('.pricing-card:not(.animate-on-scroll)').forEach((el) => {
      el.classList.add('animate-on-scroll');
    });

    // Apply to testimonial cards
    document.querySelectorAll('.testimonial-card:not(.animate-on-scroll)').forEach((el) => {
      el.classList.add('animate-on-scroll');
    });

    // Apply to FAQ items
    document.querySelectorAll('.faq-item:not(.animate-on-scroll)').forEach((el) => {
      el.classList.add('animate-on-scroll');
    });

    // Apply to section headers
    document.querySelectorAll('.section-header:not(.animate-zoom-fade)').forEach((el) => {
      el.classList.add('animate-zoom-fade');
    });

    // Apply to proof stats
    document.querySelectorAll('.proof-stat:not(.animate-scale)').forEach((el) => {
      el.classList.add('animate-scale');
    });
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      autoApplyAnimations();
      initScrollAnimations();
    });
  } else {
    autoApplyAnimations();
    initScrollAnimations();
  }
})();
