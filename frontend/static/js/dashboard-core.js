/*
 * PS_RCS_PROJECT
 * Copyright (c) 2026. All rights reserved.
 *
 * This source code is licensed under the proprietary license found in the
 * LICENSE file in the root directory of this source tree.
 *
 * File: dashboard-core.js
 * Description: Core logic for the Service Dashboard, managing themes,
 *              polling status APIs, and updating UI components.
 */

/**
 * Manages the core functionality of the Service Dashboard.
 * Handles theme switching, API polling, and DOM updates for module states.
 */
class DashboardCore {
  /**
   * Initialize configuration and state containers.
   */
  constructor() {
    this.currentTheme = 'dark';
    this.moduleStates = {};
    this.pollIntervalId = null;

    this.THEME_CONFIG = {
      DARK: 'dark',
      LIGHT: 'light',
      STORAGE_KEY: 'ps_rcs_theme_preference'
    };

    this.MODULE_STATUS_TYPES = {
      ONLINE: 'online',
      OFFLINE: 'offline',
      STANDBY: 'standby'
    };

    this.VALID_MODULES = ['motor', 'lidar', 'camera', 'ocr'];
  }

  /**
   * Initializes the dashboard logic.
   * Loads user preferences, attaches event listeners, and starts the polling loop.
   */
  init() {
    // Apply saved theme immediately
    const savedTheme = this.loadThemePreference();
    this.currentTheme = savedTheme;
    document.body.setAttribute('data-theme', savedTheme);

    // Attach theme toggle listener
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', () => this.toggleTheme());
    }

    // Capture initial static state
    this.VALID_MODULES.forEach(module => {
      const element = document.getElementById(`${module}-status`);
      if (element) {
        const status = element.getAttribute('data-status');
        this.moduleStates[module] = status;
      }
    });

    // Begin live updates
    this.startStatusPolling(2000);
  }

  /**
   * Toggles the UI theme between dark and light modes.
   * Persists the choice to localStorage and dispatches a 'themeChanged' event.
   */
  toggleTheme() {
    this.currentTheme = this.currentTheme === this.THEME_CONFIG.DARK ?
      this.THEME_CONFIG.LIGHT : this.THEME_CONFIG.DARK;

    document.body.setAttribute('data-theme', this.currentTheme);
    this.saveThemePreference(this.currentTheme);

    const event = new CustomEvent('themeChanged', {
      detail: { theme: this.currentTheme }
    });
    document.dispatchEvent(event);
  }

  /**
   * Retrieves the stored theme preference from localStorage.
   * @returns {string} The preferred theme ('dark' or 'light'). Defaults to 'dark'.
   */
  loadThemePreference() {
    const saved = localStorage.getItem(this.THEME_CONFIG.STORAGE_KEY);
    if (saved === this.THEME_CONFIG.DARK || saved === this.THEME_CONFIG.LIGHT) {
      return saved;
    }
    return this.THEME_CONFIG.DARK;
  }

  /**
   * Saves the theme preference to localStorage.
   * @param {string} theme - The theme to save ('dark' or 'light').
   */
  saveThemePreference(theme) {
    if (theme === this.THEME_CONFIG.DARK || theme === this.THEME_CONFIG.LIGHT) {
      localStorage.setItem(this.THEME_CONFIG.STORAGE_KEY, theme);
    }
  }

  /**
   * Updates the UI status badge for a specific module.
   * 
   * @param {string} moduleName - The identifier of the module (e.g., 'motor').
   * @param {string} status - The new status ('online', 'offline', 'standby').
   * @param {string} [displayText] - Optional text to display. Defaults to status uppercase.
   * @returns {boolean} True if update was successful, False if element missing.
   * @throws {Error} If moduleName or status is invalid.
   */
  updateModuleStatus(moduleName, status, displayText) {
    if (!this.VALID_MODULES.includes(moduleName)) {
      throw new Error(`Invalid module name: ${moduleName}`);
    }

    const validStatuses = Object.values(this.MODULE_STATUS_TYPES);
    if (!validStatuses.includes(status)) {
      throw new Error(`Invalid status: ${status}. Must be online|offline|standby`);
    }

    const elementId = `${moduleName}-status`;
    const element = document.getElementById(elementId);

    if (!element) {
      // Element might not exist in current layout (e.g., OCR status removed), which is fine.
      return false;
    }

    element.setAttribute('data-status', status);
    
    // Check if the element is a textual badge or a status indicator (dot)
    // If it's a dot (status-indicator), preserve the symbol, only update attribute.
    if (!element.classList.contains('status-indicator')) {
      element.textContent = displayText || status.toUpperCase();
    }
    
    this.moduleStates[moduleName] = status;
    return true;
  }

  /**
   * Starts the polling loop to fetch status data from the backend.
   * Clears any existing polling interval before starting a new one.
   * 
   * @param {number} interval - Polling interval in milliseconds. Default 2000ms.
   */
  startStatusPolling(interval = 2000) {
    if (this.pollIntervalId) {
      this.stopStatusPolling();
    }

    const poll = () => {
      fetch('/api/status')
        .then(response => {
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }
          return response.json();
        })
        .then(data => this._processStatusUpdate(data))
        .catch(error => {
          console.error('Status poll failed:', error);
          // Fallback: Assume critical connections are down on error
          this._updateConnectionIndicator({
            motor: false,
            lidar: false,
            camera: false
          });
        });
    };

    // Execute immediately, then set interval
    poll();
    this.pollIntervalId = setInterval(poll, interval);
  }

  /**
   * Stops the active status polling loop.
   */
  stopStatusPolling() {
    if (this.pollIntervalId) {
      clearInterval(this.pollIntervalId);
      this.pollIntervalId = null;
    }
  }

  /**
   * Internal handler for processing raw API status data.
   * 
   * @param {Object} statusData - The JSON payload from /api/status.
   * @private
   */
  _processStatusUpdate(statusData) {
    if (!statusData || typeof statusData !== 'object') {
      return;
    }

    // Update individual module statuses based on connection map
    if (statusData.connections && typeof statusData.connections === 'object') {
      Object.entries(statusData.connections).forEach(([module, connected]) => {
        // Map backend connection state to UI status
        const status = connected ? this.MODULE_STATUS_TYPES.ONLINE :
          this.MODULE_STATUS_TYPES.OFFLINE;
        
        // Attempt update; will silently fail if element ID doesn't exist (e.g. OCR)
        if (this.VALID_MODULES.includes(module)) {
          this.updateModuleStatus(module, status);
        }
      });
    }

    // Update battery telemetry
    if (typeof statusData.battery_voltage === 'number') {
      this._updateBatteryDisplay(statusData.battery_voltage);
    }

    // Update global connection badge
    if (statusData.connections) {
      this._updateConnectionIndicator(statusData.connections);
    }
  }

  /**
   * Updates the global connection indicator in the header.
   * 
   * @param {Object} connections - Map of module connection booleans.
   * @private
   */
  _updateConnectionIndicator(connections) {
    const indicator = document.getElementById('connection-indicator');
    if (!indicator) return;

    const connectedCount = Object.values(connections).filter(Boolean).length;
    const total = Object.keys(connections).length;

    if (connectedCount === total) {
      indicator.setAttribute('data-connected', 'true');
      indicator.textContent = 'CONN: ONLINE';
    } else if (connectedCount === 0) {
      indicator.setAttribute('data-connected', 'false');
      indicator.textContent = 'CONN: OFFLINE';
    } else {
      indicator.setAttribute('data-connected', 'true');
      indicator.textContent = `CONN: ${connectedCount}/${total}`;
    }
  }

  /**
   * Updates the battery voltage display in the header.
   * 
   * @param {number} voltage - Current battery voltage.
   * @private
   */
  _updateBatteryDisplay(voltage) {
    const display = document.getElementById('battery-display');
    if (!display) return;

    display.setAttribute('data-voltage', voltage.toFixed(1));
    display.textContent = `${voltage.toFixed(1)}V`;
  }
}

/**
 * Manages the Vision System UI components.
 * Handles camera stream events, scan triggers, and result display updates.
 */
class VisionPanel {
  /**
   * Initialize VisionPanel and bind elements.
   * Starts polling for updates if elements exist.
   */
  constructor() {
    /** @type {HTMLElement|null} */
    this.scanBtn = document.getElementById('scan-btn');
    /** @type {HTMLElement|null} */
    this.cameraStatus = document.getElementById('camera-status');
    /** @type {HTMLImageElement|null} */
    this.videoStream = document.getElementById('video-stream');

    if (this.scanBtn && this.videoStream) {
      this.setupEventListeners();
      this.startPolling();
    }
  }

  /**
   * Set up DOM event listeners.
   * Handles scan button clicks and camera feed stream status.
   */
  setupEventListeners() {
    this.scanBtn.addEventListener('click', () => this.triggerScan());
    
    // Monitor MJPEG stream connection status via image load/error events
    this.videoStream.addEventListener('error', () => {
      this.updateCameraStatus(false);
    });
    this.videoStream.addEventListener('load', () => {
      this.updateCameraStatus(true);
    });
  }

  /**
   * Trigger the OCR scanning process.
   * Sends POST request to API and handles button state.
   * @async
   */
  async triggerScan() {
    this.scanBtn.disabled = true;
    this.scanBtn.textContent = 'Scanning...';

    try {
      const response = await fetch('/api/vision/scan', {
        method: 'POST'
      });

      if (response.ok) {
        // Wait briefly for backend processing before fetching result
        setTimeout(() => this.fetchLastScan(), 2000);
      } else {
        const error = await response.json();
        console.error('Scan failed:', error);
      }
    } catch (error) {
      console.error('Network error:', error);
    } finally {
      // Reset button state after delay to prevent spamming
      setTimeout(() => {
        this.scanBtn.disabled = false;
        this.scanBtn.textContent = 'Scan Label';
      }, 3000);
    }
  }

  /**
   * Retrieve the latest scan result from the server.
   * Updates the UI with parsed data.
   * @async
   */
  async fetchLastScan() {
    try {
      const response = await fetch('/api/vision/last-scan');
      const data = await response.json();

      if (data && data.success) {
        this.updateScanDisplay(data);
      } else if (data && data.error) {
        console.error('Scan error:', data.error);
      }
    } catch (error) {
      console.error('Failed to fetch scan result:', error);
    }
  }

  /**
   * Update DOM elements with scan result data.
   * @param {Object} data - The ScanResult object from API.
   */
  updateScanDisplay(data) {
    const trackingEl = document.getElementById('tracking-id');
    const orderEl = document.getElementById('order-id');
    const rtsEl = document.getElementById('rts-code');
    const districtEl = document.getElementById('district');
    const confidenceEl = document.getElementById('confidence');
    const timeEl = document.getElementById('scan-time');

    if (trackingEl) trackingEl.textContent = data.tracking_id || '-';
    if (orderEl) orderEl.textContent = data.order_id || '-';
    if (rtsEl) rtsEl.textContent = data.rts_code || '-';
    if (districtEl) districtEl.textContent = data.district || '-';
    
    if (confidenceEl) {
      confidenceEl.textContent = data.confidence ? 
        (data.confidence * 100).toFixed(1) + '%' : '-';
    }
    
    if (timeEl) {
      timeEl.textContent = data.timestamp ? 
        new Date(data.timestamp).toLocaleString() : '-';
    }
  }

  /**
   * Update the visual indicator for camera connectivity.
   * Note: This overrides DashboardCore's status with live stream feedback.
   * @param {boolean} connected - True if stream is active.
   */
  updateCameraStatus(connected) {
    if (this.cameraStatus) {
      this.cameraStatus.style.color = connected ? 
        'var(--success-color)' : 'var(--error-color)';
    }
  }

  /**
   * Start periodic polling for background updates.
   * Used to refresh scan results if they come in asynchronously.
   */
  startPolling() {
    setInterval(() => this.fetchLastScan(), 5000);
  }
}

// Bootstrap the dashboard components when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const dashboard = new DashboardCore();
  dashboard.init();
  
  const visionPanel = new VisionPanel();
});