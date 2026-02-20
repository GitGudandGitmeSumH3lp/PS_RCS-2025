/*
 * PS_RCS_PROJECT
 * Copyright (c) 2026. All rights reserved.
 * File: frontend/static/js/dashboard-core.js
 * Description: Core logic for the service dashboard, handling state, themes, API polling,
 *              keyboard hold-to-move motor control, and recent scans display.
 */

class DashboardCore {
    constructor() {
        this.currentTheme = 'dark';
        this.moduleStates = {};
        this.pollIntervalId = null;
        this.visionPanel = null;
        this.ocrPanel = null;
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

        this.keyStack = [];
        this.motorModalOpen = false;
        this.keyCommandMap = {
            'w': 'forward',
            'ArrowUp': 'forward',
            's': 'backward',
            'ArrowDown': 'backward',
            'a': 'left',
            'ArrowLeft': 'left',
            'd': 'right',
            'ArrowRight': 'right'
        };

        this.handleKeyDown = this.handleKeyDown.bind(this);
        this.handleKeyUp = this.handleKeyUp.bind(this);

        // Timer for refreshing recent scans
        this.recentScansInterval = null;
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

        window.addEventListener('keydown', this.handleKeyDown);
        window.addEventListener('keyup', this.handleKeyUp);

        this._setupMainCameraStream();

        // Fetch recent scans immediately and start periodic refresh
        this._fetchRecentScans();
        this.recentScansInterval = setInterval(() => this._fetchRecentScans(), 10000); // every 10 seconds
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

        const motorModal = document.getElementById('controlModal');
        if (motorModal) {
            motorModal.addEventListener('close', () => {
                this.motorModalOpen = false;
                this.keyStack = [];
                this._sendMotorCommand('stop');
            });
        }
    }

    _setupCardClicks() {
        const cards = document.querySelectorAll('.linear-card.clickable');
        cards.forEach(card => {
            card.addEventListener('click', () => {
                if (card.id === 'card-vision-preview') {
                    this.visionPanel.openModal();
                } else if (card.id === 'control-card') {
                    const modal = document.getElementById('controlModal');
                    if (modal) {
                        this.motorModalOpen = true;
                        modal.showModal();
                    }
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
    }

    handleKeyDown(event) {
        if (!this.motorModalOpen) return;

        const key = event.key;
        const command = this.keyCommandMap[key];
        if (!command) return;

        event.preventDefault();

        if (!this.keyStack.includes(key)) {
            this.keyStack.push(key);
            this._sendMotorCommand(command);
        }
    }

    handleKeyUp(event) {
        if (!this.motorModalOpen) return;

        const key = event.key;
        const command = this.keyCommandMap[key];
        if (!command) return;

        event.preventDefault();

        this.keyStack = this.keyStack.filter(k => k !== key);

        if (this.keyStack.length === 0) {
            this._sendMotorCommand('stop');
        } else {
            const lastKey = this.keyStack[this.keyStack.length - 1];
            const lastCommand = this.keyCommandMap[lastKey];
            this._sendMotorCommand(lastCommand);
        }
    }

    _sendMotorCommand(direction) {
        const speedSlider = document.getElementById('speed-slider');
        const speed = speedSlider ? parseInt(speedSlider.value) : 50;
        fetch(`${this.apiBase}/api/motor/control`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: direction, speed: speed })
        }).catch(err => console.error('Motor command failed:', err));
    }

    _startStatusPolling() {
        if (this.pollIntervalId) this.stopStatusPolling();

        const poll = () => {
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

    _setupMainCameraStream() {
        const startBtn = document.getElementById('start-camera-btn');
        const stopBtn = document.getElementById('stop-camera-btn');
        const placeholder = document.getElementById('camera-placeholder');
        const liveContainer = document.getElementById('live-stream-container');
        const liveImg = document.getElementById('live-stream');

        if (!startBtn || !stopBtn || !placeholder || !liveContainer || !liveImg) return;

        startBtn.addEventListener('click', () => {
            if (liveImg.src) liveImg.src = '';
            liveImg.src = `${this.apiBase}/api/vision/stream?quality=70&t=${Date.now()}`;
            placeholder.classList.add('hidden');
            liveContainer.classList.remove('hidden');
        });

        stopBtn.addEventListener('click', () => {
            liveImg.src = '';
            liveContainer.classList.add('hidden');
            placeholder.classList.remove('hidden');
        });
    }

    // Fetch recent scans from the database and render them
    async _fetchRecentScans() {
        try {
            const res = await fetch(`${this.apiBase}/api/ocr/scans?limit=5`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            if (!data.success || !Array.isArray(data.scans)) return;
            this._renderRecentScans(data.scans);
        } catch (e) {
            console.warn('Failed to fetch recent scans:', e);
        }
    }

    _renderRecentScans(scans) {
        const container = document.getElementById('recent-scans-list');
        if (!container) return;

        if (scans.length === 0) {
            container.innerHTML = '<p class="empty-message">No scans yet.</p>';
            return;
        }

        let html = '<ul class="scan-list">';
        scans.forEach(scan => {
            const confidence = scan.confidence || 0;
            const pct = Math.round(confidence * 100);
            let dotClass = 'confidence-dot low';
            if (confidence >= 0.85) dotClass = 'confidence-dot high';
            else if (confidence >= 0.7) dotClass = 'confidence-dot medium';

            const tracking = scan.tracking_id || 'N/A';
            const buyer = scan.buyer_name || '';
            const time = scan.timestamp ? new Date(scan.timestamp).toLocaleTimeString() : '';

            html += `<li class="scan-item" onclick="window.location.href='/track/${tracking}'">
                <span class="${dotClass}"></span>
                <span class="scan-tracking">${tracking}</span>
                <span class="scan-buyer">${buyer}</span>
                <span class="scan-time">${time}</span>
                <span class="scan-conf">${pct}%</span>
            </li>`;
        });
        html += '</ul>';
        container.innerHTML = html;
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
        this.apiBase = window.location.origin;
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