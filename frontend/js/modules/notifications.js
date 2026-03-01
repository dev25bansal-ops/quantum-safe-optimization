/**
 * Notifications Module
 * Handles notification system and UI updates
 */

import { STATE } from './config.js';
import { formatDate } from './utils.js';
import { showToast } from './toast.js';

// Forward declaration for viewJobDetails
let viewJobDetailsCallback = null;

export function setViewJobDetailsCallback(callback) {
    viewJobDetailsCallback = callback;
}

/**
 * Initialize notification system
 */
export function initNotifications() {
    // Load notifications from localStorage
    const savedNotifications = localStorage.getItem('notifications');
    if (savedNotifications) {
        try {
            STATE.notifications = JSON.parse(savedNotifications);
            updateNotificationUI();
        } catch (e) {
            STATE.notifications = [];
        }
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        const menu = document.getElementById('notification-menu');
        const dropdown = document.getElementById('notification-dropdown');
        if (menu && dropdown && !menu.contains(e.target)) {
            dropdown.classList.remove('active');
        }
    });
}

/**
 * Toggle notification dropdown
 */
export function toggleNotifications(e) {
    e?.stopPropagation();
    const dropdown = document.getElementById('notification-dropdown');
    dropdown?.classList.toggle('active');

    // Mark all as read when opening
    if (dropdown?.classList.contains('active')) {
        STATE.notifications.forEach(n => n.read = true);
        saveNotifications();
        updateNotificationUI();
    }
}

/**
 * Add a new notification
 */
export function addNotification(type, title, message, jobId = null) {
    const notification = {
        id: Date.now(),
        type: type, // 'success', 'error', 'info', 'warning'
        title: title,
        message: message,
        jobId: jobId,
        timestamp: new Date().toISOString(),
        read: false
    };

    STATE.notifications.unshift(notification);

    // Keep only last 50 notifications
    if (STATE.notifications.length > 50) {
        STATE.notifications = STATE.notifications.slice(0, 50);
    }

    saveNotifications();
    updateNotificationUI();
}

/**
 * Save notifications to localStorage
 */
function saveNotifications() {
    localStorage.setItem('notifications', JSON.stringify(STATE.notifications));
}

/**
 * Update notification UI
 */
export function updateNotificationUI() {
    const badge = document.getElementById('notification-badge');
    const list = document.getElementById('notification-list');

    // Update badge
    const unreadCount = STATE.notifications.filter(n => !n.read).length;
    if (badge) {
        badge.textContent = unreadCount > 9 ? '9+' : unreadCount;
        badge.style.display = unreadCount > 0 ? 'flex' : 'none';
    }

    // Update list
    if (list) {
        if (STATE.notifications.length === 0) {
            list.innerHTML = `
                <div class="notification-empty">
                    <i class="fas fa-bell-slash"></i>
                    <p>No notifications</p>
                </div>
            `;
        } else {
            list.innerHTML = STATE.notifications.slice(0, 20).map(n => `
                <div class="notification-item ${n.type} ${n.read ? 'read' : 'unread'}" 
                     onclick="handleNotificationClick('${n.id}', '${n.jobId || ''}')" 
                     data-id="${n.id}">
                    <div class="notification-icon ${n.type}">
                        ${getNotificationIcon(n.type)}
                    </div>
                    <div class="notification-content">
                        <span class="notification-title">${n.title}</span>
                        <span class="notification-message">${n.message}</span>
                        <span class="notification-time">${formatDate(n.timestamp)}</span>
                    </div>
                    <button class="notification-dismiss" onclick="dismissNotification(event, '${n.id}')" title="Dismiss">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `).join('');
        }
    }
}

/**
 * Get icon for notification type
 */
function getNotificationIcon(type) {
    const icons = {
        success: '<i class="fas fa-check-circle"></i>',
        error: '<i class="fas fa-times-circle"></i>',
        warning: '<i class="fas fa-exclamation-triangle"></i>',
        info: '<i class="fas fa-info-circle"></i>'
    };
    return icons[type] || icons.info;
}

/**
 * Handle notification click
 */
export function handleNotificationClick(notificationId, jobId) {
    // Mark as read
    const notification = STATE.notifications.find(n => n.id == notificationId);
    if (notification) {
        notification.read = true;
        saveNotifications();
        updateNotificationUI();
    }

    // Navigate to job if jobId provided
    if (jobId && viewJobDetailsCallback) {
        document.getElementById('notification-dropdown')?.classList.remove('active');
        viewJobDetailsCallback(jobId);
    }
}

/**
 * Dismiss a notification
 */
export function dismissNotification(e, notificationId) {
    e.stopPropagation();
    STATE.notifications = STATE.notifications.filter(n => n.id != notificationId);
    saveNotifications();
    updateNotificationUI();
}

/**
 * Clear all notifications
 */
export function clearAllNotifications() {
    STATE.notifications = [];
    saveNotifications();
    updateNotificationUI();
    showToast('info', 'Cleared', 'All notifications cleared');
}

// Make notification functions global
window.toggleNotifications = toggleNotifications;
window.handleNotificationClick = handleNotificationClick;
window.dismissNotification = dismissNotification;
window.clearAllNotifications = clearAllNotifications;
window.addNotification = addNotification;
