/*
 * PS_RCS_PROJECT
 * Copyright (c) 2026. All rights reserved.
 * File: frontend/static/js/dashboard-core.js
 * Description: Core logic for the service dashboard, handling state, themes, and API polling.
 */

class DashboardCore {
    constructor() {
        this.currentTheme = 'dark';
        this.moduleStates = {};
        this.pollIntervalId = null;
        this.visionPanel = null;
        this.ocrPanel = null;
        // FIX: Capture the base URL (e.g., http://192.168.100.213:5000)
        this.apiBase = window.location.origin; 

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

        // NEW: Keyboard control state
        this.keyboardActive = false;
        this.keydownHandler = null;
        this.keyupHandler = null;
        this.activeKeys = new Set(); // track currently pressed keys
        this.keyDirectionMap = {
            'w': 'forward',
            'ArrowUp': 'forward',
            's': 'backward',
            'ArrowDown': 'backward',
            'a': 'left',
            'ArrowLeft': 'left',
            'd': 'right',
            'ArrowRight': 'right'
        };
    }

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
        
        if (typeof FlashExpressOCRPanel !== 'undefined') {
            this.ocrPanel = new FlashExpressOCRPanel();
        } else {
            console.warn('FlashExpressOCRPanel not found. OCR features disabled.');
        }
    }

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

    loadThemePreference() {
        const saved = localStorage.getItem(this.THEME_CONFIG.STORAGE_KEY);
        return (saved === this.THEME_CONFIG.DARK || saved === this.THEME_CONFIG.LIGHT)
            ? saved
            : this.THEME_CONFIG.DARK;
    }

    saveThemePreference(theme) {
        if (theme === this.THEME_CONFIG.DARK || theme === this.THEME_CONFIG.LIGHT) {
            localStorage.setItem(this.THEME_CONFIG.STORAGE_KEY, theme);
        }
    }

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
                } else if (card.id === 'ocr-scanner-card' && this.ocrPanel) {
                    this.ocrPanel.openModal();
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
                this._sendMotorCommand(direction);
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

        // NEW: Attach keyboard controls when motor modal opens/closes
        const controlModal = document.getElementById('controlModal');
        if (controlModal) {
            controlModal.addEventListener('open', () => this._attachKeyboardControls());
            controlModal.addEventListener('close', () => this._detachKeyboardControls());
        }
    }

    // NEW: Send motor command using current speed
    _sendMotorCommand(direction) {
        const speedSlider = document.getElementById('speed-slider');
        const speed = speedSlider ? parseInt(speedSlider.value) : 50;
        fetch(`${this.apiBase}/api/motor/control`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: direction, speed: speed })
        }).catch(console.error);
    }

    // NEW: Attach keyboard listeners for driving
    _attachKeyboardControls() {
        if (this.keyboardActive) return;
        this.keyboardActive = true;

        this.keydownHandler = (e) => {
            const key = e.key;
            const direction = this.keyDirectionMap[key];
            if (direction) {
                e.preventDefault(); // Prevent arrow key scrolling
                // If a different key was already pressed, this overrides it.
                this.activeKeys.add(key);
                this._sendMotorCommand(direction);
                // Optionally highlight the corresponding button
                this._highlightButton(direction, true);
            }
        };

        this.keyupHandler = (e) => {
            const key = e.key;
            if (this.keyDirectionMap[key]) {
                e.preventDefault();
                this.activeKeys.delete(key);
                // If no more driving keys are held, send stop
                if (this.activeKeys.size === 0) {
                    this._sendMotorCommand('stop');
                    this._clearButtonHighlights();
                } else {
                    // If another key is still held, we need to determine the new direction.
                    // For simplicity, we'll just stop and then re-send the first held key.
                    // But to keep it simple, we'll just stop and let the next keydown handle it.
                    // A more sophisticated approach would be to determine the composite direction,
                    // but for now we'll stop.
                    this._sendMotorCommand('stop');
                    // Then send the command for the first key still held
                    const remainingKeys = Array.from(this.activeKeys);
                    if (remainingKeys.length > 0) {
                        const firstKey = remainingKeys[0];
                        const dir = this.keyDirectionMap[firstKey];
                        this._sendMotorCommand(dir);
                        this._highlightButton(dir, true);
                    }
                }
            }
        };

        window.addEventListener('keydown', this.keydownHandler);
        window.addEventListener('keyup', this.keyupHandler);
    }

    // NEW: Remove keyboard listeners
    _detachKeyboardControls() {
        if (!this.keyboardActive) return;
        window.removeEventListener('keydown', this.keydownHandler);
        window.removeEventListener('keyup', this.keyupHandler);
        this.keyboardActive = false;
        this.activeKeys.clear();
        this._clearButtonHighlights();
    }

    // NEW: Visual feedback for pressed button
    _highlightButton(direction, highlight) {
        const btn = document.querySelector(`.dir-btn[data-dir="${direction}"]`);
        if (btn) {
            if (highlight) {
                btn.style.backgroundColor = 'var(--accent-primary)';
                btn.style.color = 'var(--text-on-accent)';
            } else {
                btn.style.backgroundColor = '';
                btn.style.color = '';
            }
        }
    }

    _clearButtonHighlights() {
        document.querySelectorAll('.dir-btn').forEach(btn => {
            btn.style.backgroundColor = '';
            btn.style.color = '';
        });
    }

    _startStatusPolling() {
        if (this.pollIntervalId) this.stopStatusPolling();

        const poll = () => {
            // FIX: Explicitly use apiBase to avoid malformed URL errors
            fetch(`${this.apiBase}/api/status`)
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

class VisionPanel {
    constructor() {
        this.elements = {};
        this.streamActive = false;
        this.streamStarting = false;
        this.streamStopping = false;
        this.scanInProgress = false;
        this.abortController = null;
        this.streamRestartTimeout = null;
        this.modalSessionId = 0;
        this.apiBase = window.location.origin; // FIX: API Base
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
            this.elements['modal-vision'].addEventListener('close', () => this._handleModalClose());
        }
    }

    openModal() {
        if (this.elements['modal-vision']) {
            this.modalSessionId++;
            const currentSession = this.modalSessionId;
            
            this._cleanupPendingOperations();
            
            const errorState = document.querySelector('.error-state');
            if (errorState) errorState.classList.add('hidden');
            
            this.elements['modal-vision'].showModal();
            
            this._scheduleStreamStart(currentSession);
        }
    }

    closeModal() {
        if (this.elements['modal-vision']) {
            this.elements['modal-vision'].close();
        }
    }

    _scheduleStreamStart(sessionId) {
        if (this.streamRestartTimeout) {
            clearTimeout(this.streamRestartTimeout);
            this.streamRestartTimeout = null;
        }
        
        this.streamRestartTimeout = setTimeout(() => {
            if (this.modalSessionId === sessionId && this.elements['modal-vision'].open) {
                this._startStream(sessionId);
            }
        }, 300);
    }

    _startStream(sessionId) {
        if (this.streamStarting || this.streamActive) {
            return;
        }
        
        const stream = this.elements['vision-stream'];
        if (!stream) return;
        
        // FIX: Ensure stream source uses full URL
        const srcPath = stream.getAttribute('data-src') || '/api/vision/stream';
        const src = srcPath.startsWith('http') ? srcPath : `${this.apiBase}${srcPath}`;
        
        this.streamStarting = true;
        
        this._abortPendingRequests();
        this.abortController = new AbortController();
        
        stream.onload = () => {
            if (this.modalSessionId !== sessionId) return;
            
            const errorState = document.querySelector('.error-state');
            if (errorState) errorState.classList.add('hidden');
            
            this.streamActive = true;
            this.streamStarting = false;
        };
        
        stream.onerror = () => {
            if (this.modalSessionId !== sessionId) return;
            this._handleStreamError();
        };
        
        stream.src = `${src}?t=${Date.now()}&session=${sessionId}`;
        
        const timeoutId = setTimeout(() => {
            if (this.modalSessionId === sessionId && !this.streamActive) {
                console.warn('Stream startup timeout, retrying...');
                this._handleStreamError();
            }
        }, 5000);
        
        this.abortController.signal.addEventListener('abort', () => {
            clearTimeout(timeoutId);
            stream.src = '';
            this.streamStarting = false;
        });
    }

    _stopStream(immediate = false) {
        if (this.streamRestartTimeout) {
            clearTimeout(this.streamRestartTimeout);
            this.streamRestartTimeout = null;
        }
        
        this._abortPendingRequests();
        
        if (immediate) {
            this._cleanupStream();
        } else {
            setTimeout(() => this._cleanupStream(), 100);
        }
    }

    _cleanupStream() {
        const stream = this.elements['vision-stream'];
        if (stream) {
            stream.src = '';
            stream.onload = null;
            stream.onerror = null;
        }
        
        this.streamActive = false;
        this.streamStarting = false;
        this.streamStopping = false;
    }

    _cleanupPendingOperations() {
        this._abortPendingRequests();
        
        if (this.streamRestartTimeout) {
            clearTimeout(this.streamRestartTimeout);
            this.streamRestartTimeout = null;
        }
        
        this._cleanupStream();
    }

    _abortPendingRequests() {
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
    }

    _handleModalClose() {
        this.streamStopping = true;
        this._stopStream(false);
    }

    _handleStreamError() {
        this.streamActive = false;
        this.streamStarting = false;
        
        const errorState = document.querySelector('.error-state');
        if (errorState) errorState.classList.remove('hidden');
        
        this.updateStatusIndicator(false);
        
        if (this.elements['modal-vision'] && this.elements['modal-vision'].open) {
            setTimeout(() => {
                if (this.elements['modal-vision'].open && !this.streamActive) {
                    this._scheduleStreamStart(this.modalSessionId);
                }
            }, 2000);
        }
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
            // FIX: Use apiBase
            const res = await fetch(`${this.apiBase}/api/vision/capture`, { method: 'POST' });
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

    _showCapturePreview(data) {
        const preview = this.elements['capture-preview'];
        const thumb = this.elements['capture-thumbnail'];
        const link = this.elements['download-link'];
        
        if (preview && thumb && link) {
            thumb.src = `${data.download_url}?t=${Date.now()}`;
            link.href = data.download_url;
            link.setAttribute('download', data.filename);
            preview.classList.remove('hidden');
        }
    }
    
    _hideCapturePreview() {
        const preview = this.elements['capture-preview'];
        if (preview) {
            preview.classList.add('hidden');
        }
    }

    async triggerScan() {
        if (this.scanInProgress) return;
        this.scanInProgress = true;
        
        try {
            // FIX: Use apiBase
            const res = await fetch(`${this.apiBase}/api/vision/scan`, { method: 'POST' });
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
            // FIX: Use apiBase
            const res = await fetch(`${this.apiBase}/api/vision/results/${scanId}`);
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