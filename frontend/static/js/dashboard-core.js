/*
 * PS_RCS_PROJECT
 * Copyright (c) 2026. All rights reserved.
 * File: frontend/static/js/dashboard-core.js
 * Description: Core logic for the service dashboard, handling state, themes, and API polling.
 */

/**
 * Manages the main dashboard state, theme switching, and module polling.
 */
class DashboardCore {
    constructor() {
        this.currentTheme = 'dark';
        this.moduleStates = {};
        this.pollIntervalId = null;
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

    /**
     * Initialize the dashboard components.
     */
    init() {
        const savedTheme = this.loadThemePreference();
        this.currentTheme = savedTheme;
        document.documentElement.setAttribute('data-theme', savedTheme);
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
        this._startStatusPolling();
        
        this.visionPanel = new VisionPanel();
    }

    /**
     * Toggle the application theme between light and dark.
     */
    toggleTheme() {
        this.currentTheme = this.currentTheme === this.THEME_CONFIG.DARK 
            ? this.THEME_CONFIG.LIGHT 
            : this.THEME_CONFIG.DARK;
        
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        document.body.setAttribute('data-theme', this.currentTheme);
        
        this.saveThemePreference(this.currentTheme);
        
        document.dispatchEvent(new CustomEvent('themeChanged', {
            detail: { theme: this.currentTheme }
        }));
    }

    /**
     * Load the saved theme preference from local storage.
     * @returns {string} 'dark' or 'light'
     */
    loadThemePreference() {
        const saved = localStorage.getItem(this.THEME_CONFIG.STORAGE_KEY);
        return (saved === this.THEME_CONFIG.DARK || saved === this.THEME_CONFIG.LIGHT)
            ? saved
            : this.THEME_CONFIG.DARK;
    }

    /**
     * Save the theme preference to local storage.
     * @param {string} theme - 'dark' or 'light'
     */
    saveThemePreference(theme) {
        if (theme === this.THEME_CONFIG.DARK || theme === this.THEME_CONFIG.LIGHT) {
            localStorage.setItem(this.THEME_CONFIG.STORAGE_KEY, theme);
        }
    }

    /**
     * Update the visual status of a module.
     * @param {string} moduleName - 'motor', 'camera', or 'system'
     * @param {string} status - 'online', 'offline', or 'standby'
     * @param {string} [displayText] - Optional text to display
     * @returns {boolean} True if successful
     */
    updateModuleStatus(moduleName, status, displayText) {
        if (!this.VALID_MODULES.includes(moduleName)) return false;
        
        const validStatuses = Object.values(this.MODULE_STATUS_TYPES);
        if (!validStatuses.includes(status)) return false;

        const elementId = `${moduleName}-status`;
        const element = document.getElementById(elementId);

        if (!element) return false;

        element.setAttribute('data-status', status);
        
        if (!element.classList.contains('status-indicator')) {
            element.textContent = displayText || status.toUpperCase();
        }
        
        this.moduleStates[moduleName] = status;
        
        if (moduleName === 'camera' && this.visionPanel) {
            this.visionPanel.updateStatusIndicator(status === 'online');
        }
        
        return true;
    }

    /**
     * Set up event listeners for modals and controls.
     */
    setupModalInteractions() {
        this._setupCardClicks();
        this._setupModalClosers();
        this._setupControls();
    }
    
    _setupCardClicks() {
        const cards = document.querySelectorAll('.linear-card.clickable');
        cards.forEach(card => {
            card.addEventListener('click', () => {
                if (card.id === 'card-vision-preview') {
                    this.visionPanel.openModal();
                } else if (card.id === 'control-card') {
                    const modal = document.getElementById('controlModal');
                    if (modal) modal.showModal();
                } else if (card.id === 'ocr-scanner-card') {
                    const modal = document.getElementById('ocr-scanner-modal');
                    if (modal) modal.showModal();
                }
            });

            card.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    card.click();
                }
            });
        });
    }

    _setupModalClosers() {
        const modals = document.querySelectorAll('.linear-modal');
        const closeButtons = document.querySelectorAll('.btn-ghost');
        
        closeButtons.forEach(button => {
            button.addEventListener('click', () => {
                const modal = button.closest('.linear-modal');
                if (modal) modal.close();
            });
        });

        modals.forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) modal.close();
            });
            modal.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') modal.close();
            });
        });
    }
    
    _setupControls() {
        const speedSlider = document.getElementById('speed-slider');
        const speedValue = document.getElementById('speed-value');
        
        if (speedSlider && speedValue) {
            const updateGradient = (val) => {
                 const gradient = `linear-gradient(to right, var(--accent-primary) 0%, var(--accent-primary) ${val}%, var(--border-light) ${val}%, var(--border-light) 100%)`;
                 speedSlider.style.background = gradient;
                 speedValue.textContent = `${val}%`;
            };
            
            speedSlider.addEventListener('input', () => updateGradient(speedSlider.value));
            updateGradient(speedSlider.value);
        }

        const dirButtons = document.querySelectorAll('.dir-btn');
        dirButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const direction = btn.getAttribute('data-dir');
                // Implementation for motor command via API
                fetch('/api/motor/control', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: direction, speed: speedSlider ? parseInt(speedSlider.value) : 150 })
                }).catch(console.error);
            });
        });

        const applyButton = document.getElementById('apply-controls');
        if (applyButton) {
            applyButton.addEventListener('click', () => {
                applyButton.textContent = 'Applied!';
                applyButton.style.backgroundColor = 'var(--accent-success)';
                setTimeout(() => {
                    applyButton.textContent = 'Apply';
                    applyButton.style.backgroundColor = '';
                }, 2000);
            });
        }
    }

    _startStatusPolling() {
        if (this.pollIntervalId) this.stopStatusPolling();

        const poll = () => {
            fetch('/api/status')
                .then(res => res.ok ? res.json() : Promise.reject(`HTTP ${res.status}`))
                .then(data => this._processStatusUpdate(data))
                .catch(error => {
                    console.error('Status poll failed:', error);
                    this._updateConnectionIndicator(false);
                });
        };

        poll();
        this.pollIntervalId = setInterval(poll, 2000);
    }

    stopStatusPolling() {
        if (this.pollIntervalId) {
            clearInterval(this.pollIntervalId);
            this.pollIntervalId = null;
        }
    }

    _processStatusUpdate(statusData) {
        if (!statusData || typeof statusData !== 'object') return;

        const cameraOnline = statusData.camera_connected || false;
        const motorOnline = statusData.motor_connected || false;
        const systemOnline = statusData.lidar_connected || false;

        this.updateModuleStatus('camera', cameraOnline ? 'online' : 'offline');
        this.updateModuleStatus('motor', motorOnline ? 'online' : 'offline');
        this.updateModuleStatus('system', systemOnline ? 'online' : 'offline');

        if (typeof statusData.battery_voltage === 'number') {
            this._updateBatteryDisplay(statusData.battery_voltage);
        }

        this._updateConnectionIndicator(cameraOnline || motorOnline || systemOnline);
    }

    _updateConnectionIndicator(isConnected) {
        const indicator = document.getElementById('connection-indicator');
        if (!indicator) return;

        if (isConnected) {
            indicator.setAttribute('data-connected', 'true');
            indicator.textContent = 'CONN: ONLINE';
        } else {
            indicator.setAttribute('data-connected', 'false');
            indicator.textContent = 'CONN: OFFLINE';
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
 * Manages the Vision Panel modal and streaming logic.
 */
class VisionPanel {
    constructor() {
        this.elements = {};
        this.streamActive = false;
        this.scanInProgress = false;
        this._initializeElements();
        this._initializeEventListeners();
    }

    _initializeElements() {
        const ids = [
            'card-vision-preview', 'modal-vision', 'vision-stream',
            'btn-vision-scan', 'btn-vision-close', 'btn-scan-label',
            'btn-capture-photo', 'capture-preview', 'capture-thumbnail',
            'download-link', 'btn-scan-capture', 'close-preview'
        ];
        ids.forEach(id => this.elements[id] = document.getElementById(id));
        this.elements['.results-data'] = document.querySelector('.results-data');
    }

    _initializeEventListeners() {
        if (this.elements['btn-vision-close']) {
            this.elements['btn-vision-close'].addEventListener('click', () => this.closeModal());
        }
        
        if (this.elements['close-preview']) {
            this.elements['close-preview'].addEventListener('click', () => this._hideCapturePreview());
        }

        const scanBtns = [this.elements['btn-vision-scan'], this.elements['btn-scan-label']];
        scanBtns.forEach(btn => {
            if (btn) btn.addEventListener('click', () => this.triggerScan());
        });

        if (this.elements['btn-capture-photo']) {
            this.elements['btn-capture-photo'].addEventListener('click', () => this.capturePhoto());
        }

        if (this.elements['modal-vision']) {
            this.elements['modal-vision'].addEventListener('close', () => this._stopStream());
        }
    }

    openModal() {
        if (this.elements['modal-vision']) {
            this.elements['modal-vision'].showModal();
            this._startStream();
        }
    }

    closeModal() {
        if (this.elements['modal-vision']) {
            this.elements['modal-vision'].close();
        }
    }

    // Contract §5.1: Updated _startStream to hide error overlay
    _startStream() {
        const stream = this.elements['vision-stream'];
        if (!stream || this.streamActive) return;

        // STEP 1: Hide any previous error state
        const errorOverlay = document.querySelector('.error-state');
        if (errorOverlay) {
            errorOverlay.classList.add('hidden');
        }

        // STEP 2: Set stream source
        const src = stream.getAttribute('data-src');
        if (src) {
            // Force reload by appending timestamp
            stream.src = `${src}?t=${Date.now()}`;
            this.streamActive = true;
            stream.onerror = () => this._handleStreamError();
        }
    }

    _stopStream() {
        const stream = this.elements['vision-stream'];
        if (stream) {
            stream.src = '';
            this.streamActive = false;
        }
    }

    _handleStreamError() {
        this.updateStatusIndicator(false);
        const errorState = document.querySelector('.error-state');
        if (errorState) errorState.classList.remove('hidden');
    }

    updateStatusIndicator(isOnline) {
        const card = this.elements['card-vision-preview'];
        if (!card) return;

        const indicator = card.querySelector('.status-indicator');
        const text = card.querySelector('.status-text');

        if (indicator && text) {
            indicator.setAttribute('data-status', isOnline ? 'online' : 'offline');
            text.textContent = isOnline ? 'Online' : 'Offline';
        }
    }

    async capturePhoto() {
        const btn = this.elements['btn-capture-photo'];
        if (btn) btn.disabled = true;

        try {
            const res = await fetch('/api/vision/capture', { method: 'POST' });
            if (!res.ok) throw new Error('Capture failed');
            
            const data = await res.json();
            if (data.success) {
                this._showCapturePreview(data);
            }
        } catch (err) {
            console.error(err);
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    // Contract §5.2: Updated _showCapturePreview to set download attribute
    _showCapturePreview(data) {
        const preview = this.elements['capture-preview'];
        const thumb = this.elements['capture-thumbnail'];
        const link = this.elements['download-link'];
        
        if (preview && thumb && link) {
            // Contract §5.2: Set download attribute dynamically
            thumb.src = `${data.download_url}?t=${Date.now()}`;
            link.href = data.download_url;
            link.setAttribute('download', data.filename);  // CRITICAL FIX
            preview.classList.remove('hidden');
        }
    }
    
    // Contract §5.3: Updated _hideCapturePreview to clear image source
    _hideCapturePreview() {
        const preview = this.elements['capture-preview'];
        const thumbnail = this.elements['capture-thumbnail'];

        if (preview) preview.classList.add('hidden');
        if (thumbnail) thumbnail.src = '';  // Clear to free memory
    }

    async triggerScan() {
        if (this.scanInProgress) return;
        this.scanInProgress = true;
        
        try {
            const res = await fetch('/api/vision/scan', { method: 'POST' });
            if (!res.ok) throw new Error('Scan failed');
            
            const data = await res.json();
            if (data.scan_id) {
                await this._pollScanResults(data.scan_id);
            }
        } catch (err) {
            console.error(err);
        } finally {
            this.scanInProgress = false;
        }
    }
    
    async _pollScanResults(scanId) {
        let attempts = 0;
        while (attempts < 30) {
            const res = await fetch(`/api/vision/results/${scanId}`);
            const data = await res.json();
            
            if (data.status === 'completed') {
                this._displayResults(data.data);
                return;
            }
            if (data.status === 'failed') break;
            
            attempts++;
            await new Promise(r => setTimeout(r, 1000));
        }
    }
    
    _displayResults(data) {
        const results = document.getElementById('scan-results-card');
        if (results) {
            results.classList.remove('hidden');
            
            const fields = ['tracking-id', 'order-id', 'rts-code', 'district', 'confidence', 'scan-time'];
            const values = {
                'tracking-id': data.tracking_id,
                'order-id': data.order_id,
                'rts-code': data.rts_code,
                'district': data.district,
                'confidence': data.confidence,
                'scan-time': data.timestamp
            };
            
            fields.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.textContent = values[id] || '-';
            });
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new DashboardCore();
    dashboard.init();
});