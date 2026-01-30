/*
 * PS_RCS_PROJECT
 * Copyright (c) 2026. All rights reserved.
 * File: frontend/static/js/dashboard-core.js
 * Description: Apple/Bento dashboard with modal interactions.
 */

/**
 * Manages the Apple/Bento dashboard functionality.
 * Handles theme switching, modal interactions, and status polling.
 */
class DashboardCore {
  /**
   * Initialize the dashboard core state.
   */
  constructor() {
    this.currentTheme = 'dark';
    this.moduleStates = {};
    this.pollIntervalId = null;
    this.visionStreamLoaded = false;

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

    this.VALID_MODULES = ['motor', 'camera', 'system'];
  }

  /**
   * Initialize the dashboard components.
   * Loads theme, sets up event listeners, and starts status polling.
   */
  init() {
    const savedTheme = this.loadThemePreference();
    this.currentTheme = savedTheme;
    document.body.setAttribute('data-theme', savedTheme);

    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', () => this.toggleTheme());
    }

    this.VALID_MODULES.forEach(module => {
      const element = document.getElementById(`${module}-status`);
      if (element) {
        const status = element.getAttribute('data-status');
        this.moduleStates[module] = status;
      }
    });

    this.setupModalInteractions();
    this.startStatusPolling(2000);
  }

  /**
   * Toggle between light and dark themes.
   * Updates local storage and dispatches a 'themeChanged' event.
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
   * Load theme preference from local storage.
   * @returns {string} The saved theme ('dark' or 'light'). Defaults to 'dark'.
   */
  loadThemePreference() {
    const saved = localStorage.getItem(this.THEME_CONFIG.STORAGE_KEY);
    if (saved === this.THEME_CONFIG.DARK || saved === this.THEME_CONFIG.LIGHT) {
      return saved;
    }
    return this.THEME_CONFIG.DARK;
  }

  /**
   * Save theme preference to local storage.
   * @param {string} theme - The theme to save ('dark' or 'light').
   */
  saveThemePreference(theme) {
    if (theme === this.THEME_CONFIG.DARK || theme === this.THEME_CONFIG.LIGHT) {
      localStorage.setItem(this.THEME_CONFIG.STORAGE_KEY, theme);
    }
  }

  /**
   * Update the visual status of a module.
   * @param {string} moduleName - The name of the module (motor, camera, system).
   * @param {string} status - The new status (online, offline, standby).
   * @param {string} [displayText] - Optional text to display on the badge.
   * @returns {boolean} True if update was successful, false if element not found.
   * @throws {Error} If module name or status is invalid.
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
      return false;
    }

    element.setAttribute('data-status', status);
    
    if (!element.classList.contains('status-indicator')) {
      element.textContent = displayText || status.toUpperCase();
    }
    
    this.moduleStates[moduleName] = status;
    return true;
  }

  /**
   * Setup event listeners for modal interactions (open, close, click-outside).
   * Also configures sliders and directional buttons.
   */
  setupModalInteractions() {
    const cards = document.querySelectorAll('.bento-card[data-modal]');
    const modals = document.querySelectorAll('.bento-modal');
    const closeButtons = document.querySelectorAll('[data-close]');
    const videoStream = document.getElementById('video-stream');

    cards.forEach(card => {
      card.addEventListener('click', () => {
        const modalId = card.getAttribute('data-modal');
        const modal = document.getElementById(modalId);
        
        if (modal) {
          // Fix: Ensure correct endpoint is used for vision stream
          if (modalId === 'visionModal' && !this.visionStreamLoaded) {
            videoStream.src = '/api/vision/stream';
            this.visionStreamLoaded = true;
          }
          
          modal.showModal();
          
          const closeBtn = modal.querySelector('.modal-close');
          if (closeBtn) {
            closeBtn.focus();
          }
        }
      });

      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          card.click();
        }
      });
    });

    closeButtons.forEach(button => {
      button.addEventListener('click', () => {
        const modalId = button.getAttribute('data-close');
        const modal = document.getElementById(modalId);
        
        if (modal) {
          modal.close();
        }
      });
    });

    modals.forEach(modal => {
      modal.addEventListener('click', (e) => {
        const rect = modal.getBoundingClientRect();
        const isInDialog = (
          rect.top <= e.clientY && 
          e.clientY <= rect.top + rect.height && 
          rect.left <= e.clientX && 
          e.clientX <= rect.left + rect.width
        );
        
        if (!isInDialog) {
          modal.close();
        }
      });

      modal.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          modal.close();
        }
      });
    });

    const speedSlider = document.getElementById('speed-slider');
    const speedValue = document.getElementById('speed-value');
    
    if (speedSlider && speedValue) {
      speedSlider.addEventListener('input', () => {
        const value = speedSlider.value;
        const gradient = `linear-gradient(to right, var(--bento-primary) 0%, var(--bento-primary) ${value}%, #e5e5ea ${value}%, #e5e5ea 100%)`;
        speedSlider.style.background = gradient;
        speedValue.textContent = `${value}%`;
      });

      const initialValue = speedSlider.value;
      const initialGradient = `linear-gradient(to right, var(--bento-primary) 0%, var(--bento-primary) ${initialValue}%, #e5e5ea ${initialValue}%, #e5e5ea 100%)`;
      speedSlider.style.background = initialGradient;
    }

    const dirButtons = document.querySelectorAll('.dir-btn');
    dirButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const direction = btn.getAttribute('data-dir');
        console.log(`Direction: ${direction}`);
      });
    });

    const applyButton = document.getElementById('apply-controls');
    if (applyButton) {
      applyButton.addEventListener('click', () => {
        const speed = speedSlider ? speedSlider.value : 50;
        console.log('Applying controls - Speed:', speed);
        
        applyButton.textContent = 'Applied!';
        applyButton.style.backgroundColor = 'var(--bento-success)';
        
        setTimeout(() => {
          applyButton.textContent = 'Apply';
          applyButton.style.backgroundColor = '';
        }, 2000);
      });
    }
  }

  /**
   * Start polling the backend for status updates.
   * @param {number} interval - Polling interval in milliseconds.
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
          this._updateConnectionIndicator({
            motor: false,
            camera: false,
            system: false
          });
        });
    };

    poll();
    this.pollIntervalId = setInterval(poll, interval);
  }

  /**
   * Stop the status polling interval.
   */
  stopStatusPolling() {
    if (this.pollIntervalId) {
      clearInterval(this.pollIntervalId);
      this.pollIntervalId = null;
    }
  }

  /**
   * Process data received from status API.
   * @param {Object} statusData - The JSON response from the server.
   * @private
   */
  _processStatusUpdate(statusData) {
    if (!statusData || typeof statusData !== 'object') {
      return;
    }

    if (statusData.connections && typeof statusData.connections === 'object') {
      Object.entries(statusData.connections).forEach(([module, connected]) => {
        const status = connected ? this.MODULE_STATUS_TYPES.ONLINE :
          this.MODULE_STATUS_TYPES.OFFLINE;
        
        if (this.VALID_MODULES.includes(module)) {
          this.updateModuleStatus(module, status);
        }
      });
    }

    if (typeof statusData.battery_voltage === 'number') {
      this._updateBatteryDisplay(statusData.battery_voltage);
    }

    if (statusData.connections) {
      this._updateConnectionIndicator(statusData.connections);
    }
  }

  /**
   * Update the global connection indicator based on module statuses.
   * @param {Object} connections - Map of module names to boolean connection status.
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
   * Update the battery voltage display.
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
 * Manages the Vision Panel modal functionality.
 * Handles scanning triggers, camera status updates, and scan result display.
 */
class VisionPanel {
  /**
   * Initialize VisionPanel and locate DOM elements.
   */
  constructor() {
    this.scanBtn = document.getElementById('scan-btn');
    this.cameraStatus = document.getElementById('camera-status');
    this.videoStream = document.getElementById('video-stream');

    if (this.scanBtn && this.videoStream) {
      this.setupEventListeners();
    }
  }

  /**
   * Setup event listeners for scan button and video stream status.
   */
  setupEventListeners() {
    this.scanBtn.addEventListener('click', () => this.triggerScan());
    
    this.videoStream.addEventListener('error', () => {
      this.updateCameraStatus(false);
    });
    this.videoStream.addEventListener('load', () => {
      this.updateCameraStatus(true);
    });
  }

  /**
   * Trigger a vision scan via the API.
   * Disables button during scan and fetches result upon success.
   */
  async triggerScan() {
    this.scanBtn.disabled = true;
    this.scanBtn.textContent = 'Scanning...';

    try {
      const response = await fetch('/api/vision/scan', {
        method: 'POST'
      });

      if (response.ok) {
        setTimeout(() => this.fetchLastScan(), 2000);
      } else {
        const error = await response.json();
        console.error('Scan failed:', error);
      }
    } catch (error) {
      console.error('Network error:', error);
    } finally {
      setTimeout(() => {
        this.scanBtn.disabled = false;
        this.scanBtn.textContent = 'Scan Label';
      }, 3000);
    }
  }

  /**
   * Fetch the result of the last successful scan.
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
   * Update the UI with scan results.
   * @param {Object} data - The scan result object.
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
   * Update the visual indicator for camera connection status.
   * @param {boolean} connected - Whether the camera stream is active.
   */
  updateCameraStatus(connected) {
    if (this.cameraStatus) {
      this.cameraStatus.style.color = connected ? 
        'var(--accent-success)' : 'var(--accent-danger)';
    }
  }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  const dashboard = new DashboardCore();
  dashboard.init();
  
  const visionPanel = new VisionPanel();
});