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
  constructor() {
    this.currentTheme = 'dark';
    this.moduleStates = {};
    this.pollIntervalId = null;
    this.visionStreamLoaded = false;
    this.visionPanel = null;

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
    
    if (typeof VisionPanel !== 'undefined') {
      this.visionPanel = new VisionPanel();
    }
  }

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

  loadThemePreference() {
    const saved = localStorage.getItem(this.THEME_CONFIG.STORAGE_KEY);
    if (saved === this.THEME_CONFIG.DARK || saved === this.THEME_CONFIG.LIGHT) {
      return saved;
    }
    return this.THEME_CONFIG.DARK;
  }

  saveThemePreference(theme) {
    if (theme === this.THEME_CONFIG.DARK || theme === this.THEME_CONFIG.LIGHT) {
      localStorage.setItem(this.THEME_CONFIG.STORAGE_KEY, theme);
    }
  }

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
    
    if (moduleName === 'camera' && this.visionPanel) {
      this.visionPanel.updateCameraStatus(status === 'online');
    }
    
    return true;
  }

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

  stopStatusPolling() {
    if (this.pollIntervalId) {
      clearInterval(this.pollIntervalId);
      this.pollIntervalId = null;
    }
  }

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

  _updateBatteryDisplay(voltage) {
    const display = document.getElementById('battery-display');
    if (!display) return;

    display.setAttribute('data-voltage', voltage.toFixed(1));
    display.textContent = `${voltage.toFixed(1)}V`;
  }
}

/**
 * Contract §4.1: VisionPanel Class
 * Manages the Vision Panel modal functionality.
 */
class VisionPanel {
  constructor() {
    this._elements = {};
    this._streamUrl = '/api/vision/stream';
    this._pollInterval = null;
    this._initElements();
    this._initListeners();
  }

  _initElements() {
    const ids = [
      'visionModal', 'video-stream-modal', 'stream-error-overlay',
      'btn-open-vision', 'btn-close-vision', 'btn-scan-trigger',
      'camera-status'
    ];
    ids.forEach(id => {
      this._elements[id] = document.getElementById(id);
    });
  }

  _initListeners() {
    if (this._elements.btnOpenVision) {
      this._elements.btnOpenVision.addEventListener('click', () => this.openModal());
    }
    if (this._elements.btnCloseVision) {
      this._elements.btnCloseVision.addEventListener('click', () => this.closeModal());
    }
    if (this._elements.btnScanTrigger) {
      this._elements.btnScanTrigger.addEventListener('click', () => this.triggerScan());
    }
    if (this._elements.visionModal) {
      this._elements.visionModal.addEventListener('close', () => this._onModalClose());
    }
    const previewCard = document.getElementById('card-camera-preview');
    if (previewCard) {
      previewCard.addEventListener('click', () => this.openModal());
      previewCard.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          this.openModal();
        }
      });
    }
  }

  openModal() {
    if (!this._elements.visionModal) return;
    if (this._elements.videoStreamModal) {
      this._elements.videoStreamModal.src = this._streamUrl;
    }
    this._elements.visionModal.showModal();
  }

  closeModal() {
    if (!this._elements.visionModal) return;
    this._elements.visionModal.close();
  }

  _onModalClose() {
    if (this._elements.videoStreamModal) {
      this._elements.videoStreamModal.src = '';
    }
    if (this._pollInterval) {
      clearInterval(this._pollInterval);
      this._pollInterval = null;
    }
    if (this._elements.streamErrorOverlay) {
      this._elements.streamErrorOverlay.hidden = true;
    }
  }

  triggerScan() {
    if (!this._elements.btnScanTrigger) return;
    this._elements.btnScanTrigger.disabled = true;
    this._elements.btnScanTrigger.textContent = 'Scanning...';
    
    fetch('/api/vision/scan', { method: 'POST' })
      .then(response => response.json())
      .then(data => {
        if (data.success || data.status === 'processing') {
          this._showToast('Scan started', 'success');
          if (data.scan_id) {
            this._pollScanResults(data.scan_id);
          } else {
            setTimeout(() => this.fetchLastScan(), 2000);
          }
        } else {
          throw new Error(data.error || 'Scan failed');
        }
      })
      .catch(error => {
        this._showToast(`Scan error: ${error.message}`, 'error');
        this._resetScanButton();
      });
  }

  _pollScanResults(scanId) {
    let attempts = 0;
    const maxAttempts = 30;
    
    this._pollInterval = setInterval(() => {
      fetch(`/api/vision/results/${scanId}`)
        .then(response => response.json())
        .then(data => {
          if (data.status === 'completed') {
            clearInterval(this._pollInterval);
            this._pollInterval = null;
            this._showToast('Text extracted successfully', 'success');
            this._resetScanButton();
            this.updateScanDisplay(data);
          } else if (data.status === 'failed') {
            clearInterval(this._pollInterval);
            this._pollInterval = null;
            this._showToast('Text extraction failed', 'error');
            this._resetScanButton();
          }
          attempts++;
          if (attempts >= maxAttempts) {
            clearInterval(this._pollInterval);
            this._pollInterval = null;
            this._showToast('Scan timeout', 'error');
            this._resetScanButton();
          }
        })
        .catch(() => {
          clearInterval(this._pollInterval);
          this._pollInterval = null;
          this._showToast('Results fetch failed', 'error');
          this._resetScanButton();
        });
    }, 100);
  }

  fetchLastScan() {
    fetch('/api/vision/last-scan')
      .then(response => response.json())
      .then(data => {
        if (data && data.success) {
          this.updateScanDisplay(data);
          this._resetScanButton();
        } else if (data && data.error) {
          throw new Error(data.error);
        }
      })
      .catch(error => {
        console.error('Failed to fetch scan result:', error);
        this._resetScanButton();
      });
  }

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

  _resetScanButton() {
    if (this._elements.btnScanTrigger) {
      this._elements.btnScanTrigger.disabled = false;
      this._elements.btnScanTrigger.textContent = 'Scan Document';
    }
  }

  _showToast(message, type) {
    if (typeof DashboardCore !== 'undefined' && DashboardCore.toast) {
      DashboardCore.toast(message, type);
    } else {
      console.log(`${type}: ${message}`);
    }
  }

  updateCameraStatus(isConnected) {
    if (!this._elements.cameraStatus) return;
    const statusEl = this._elements.cameraStatus;
    const btnScan = this._elements.btnScanTrigger;
    
    if (isConnected) {
      statusEl.textContent = 'Camera Online';
      statusEl.parentElement.setAttribute('data-status', 'online');
      if (btnScan) btnScan.disabled = false;
      if (this._elements.streamErrorOverlay) {
        this._elements.streamErrorOverlay.hidden = true;
      }
    } else {
      statusEl.textContent = 'Camera Offline';
      statusEl.parentElement.setAttribute('data-status', 'offline');
      if (btnScan) btnScan.disabled = true;
      if (this._elements.streamErrorOverlay) {
        this._elements.streamErrorOverlay.hidden = false;
      }
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const dashboard = new DashboardCore();
  dashboard.init();
  const visionPanel = new VisionPanel();
  dashboard.visionPanel = visionPanel;
});