/* frontend/static/js/dashboard-core.js */

/**
 * DashboardCore - Main dashboard controller
 * Contract §5.2: Integration with VisionPanel
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
        this._startStatusPolling();
        
        this.visionPanel = new VisionPanel();
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
            this.visionPanel.updateStatusIndicator(status === 'online');
        }
        
        return true;
    }

    setupModalInteractions() {
        const cards = document.querySelectorAll('.linear-card.clickable');
        const modals = document.querySelectorAll('.linear-modal');
        const closeButtons = document.querySelectorAll('.btn-ghost');

        cards.forEach(card => {
            card.addEventListener('click', (e) => {
                if (card.id === 'card-vision-preview') {
                    this.visionPanel.openModal();
                } else if (card.id === 'control-card') {
                    const modal = document.getElementById('controlModal');
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

        closeButtons.forEach(button => {
            button.addEventListener('click', () => {
                const modal = button.closest('.linear-modal');
                if (modal) modal.close();
            });
        });

        modals.forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
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
                const gradient = `linear-gradient(to right, var(--accent-primary) 0%, var(--accent-primary) ${value}%, var(--border-light) ${value}%, var(--border-light) 100%)`;
                speedSlider.style.background = gradient;
                speedValue.textContent = `${value}%`;
            });

            const initialValue = speedSlider.value;
            const initialGradient = `linear-gradient(to right, var(--accent-primary) 0%, var(--accent-primary) ${initialValue}%, var(--border-light) ${initialValue}%, var(--border-light) 100%)`;
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
                applyButton.style.backgroundColor = 'var(--accent-success)';
                
                setTimeout(() => {
                    applyButton.textContent = 'Apply';
                    applyButton.style.backgroundColor = '';
                }, 2000);
            });
        }
    }

    _startStatusPolling() {
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
                    this._updateConnectionIndicator(false);
                });
        };

        poll();
        this.pollIntervalId = setInterval(poll, 2000);
    }

    _pollStatus() {
        return fetch('/api/status')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                return response.json();
            })
            .then(data => this._processStatusUpdate(data))
            .catch(error => {
                console.error('Status poll failed:', error);
                this._updateConnectionIndicator(false);
            });
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
 * Contract §5.1: VisionPanel Class
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
        const elementIds = [
            'card-vision-preview',
            'modal-vision',
            'vision-stream',
            'btn-vision-scan',
            'btn-vision-close',
            'btn-vision-scan .btn-text',
            'btn-vision-scan .btn-spinner',
            '.error-state',
            '.results-data'
        ];

        elementIds.forEach(id => {
            const selector = id.startsWith('.') ? id : `#${id}`;
            if (id.includes(' ')) {
                const [parent, child] = id.split(' ');
                const parentEl = document.querySelector(`#${parent}`);
                this.elements[id] = parentEl ? parentEl.querySelector(child) : null;
            } else {
                this.elements[id] = document.querySelector(selector);
            }
        });
    }

    _initializeEventListeners() {
        if (this.elements['card-vision-preview']) {
            this.elements['card-vision-preview'].addEventListener('click', () => this.openModal());
            this.elements['card-vision-preview'].addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.openModal();
                }
            });
        }

        if (this.elements['btn-vision-close']) {
            this.elements['btn-vision-close'].addEventListener('click', () => this.closeModal());
        }

        if (this.elements['btn-vision-scan']) {
            this.elements['btn-vision-scan'].addEventListener('click', () => this.triggerScan());
        }

        if (this.elements['modal-vision']) {
            this.elements['modal-vision'].addEventListener('close', () => this._stopStream());
            this.elements['modal-vision'].addEventListener('keydown', (e) => {
                if (e.key === 'Escape') this.closeModal();
            });
        }
    }

    openModal() {
        if (!this.elements['modal-vision']) return;
        this.elements['modal-vision'].showModal();
        this._startStream();
    }

    closeModal() {
        if (!this.elements['modal-vision']) return;
        this.elements['modal-vision'].close();
    }

    _startStream() {
        const streamElement = this.elements['vision-stream'];
        if (!streamElement || this.streamActive) return;

        const streamUrl = streamElement.getAttribute('data-src');
        if (!streamUrl) return;

        streamElement.src = streamUrl;
        this.streamActive = true;

        streamElement.onerror = () => this._handleStreamError();
        streamElement.onload = () => {
            if (this.elements['.error-state']) {
                this.elements['.error-state'].classList.add('hidden');
            }
        };
    }

    _stopStream() {
        const streamElement = this.elements['vision-stream'];
        if (!streamElement) return;

        streamElement.src = '';
        this.streamActive = false;
    }

    _handleStreamError() {
        this.updateStatusIndicator(false);
        if (this.elements['.error-state']) {
            this.elements['.error-state'].classList.remove('hidden');
        }
        if (this.elements['btn-vision-scan']) {
            this.elements['btn-vision-scan'].disabled = true;
        }
    }

    updateStatusIndicator(isOnline) {
        const card = this.elements['card-vision-preview'];
        if (!card) return;

        const statusIndicator = card.querySelector('.status-indicator');
        const statusDot = card.querySelector('.status-dot');
        const statusText = card.querySelector('.status-text');
        const scanButton = this.elements['btn-vision-scan'];

        if (statusIndicator && statusDot && statusText) {
            statusIndicator.setAttribute('data-status', isOnline ? 'online' : 'offline');
            statusText.textContent = isOnline ? 'Online' : 'Offline';
        }

        if (scanButton) {
            scanButton.disabled = !isOnline;
        }
    }

    async triggerScan() {
        if (this.scanInProgress || !this.elements['btn-vision-scan']) return;

        this.scanInProgress = true;
        const btnText = this.elements['btn-vision-scan .btn-text'];
        const btnSpinner = this.elements['btn-vision-scan .btn-spinner'];
        const scanButton = this.elements['btn-vision-scan'];

        if (btnText) btnText.textContent = 'Scanning...';
        if (btnSpinner) btnSpinner.classList.remove('hidden');
        scanButton.disabled = true;

        try {
            const response = await fetch('/api/vision/scan', { method: 'POST' });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const data = await response.json();
            if (data.success || data.status === 'processing') {
                this._showToast('Scan started successfully', 'success');
                if (data.scan_id) {
                    await this._pollScanResults(data.scan_id);
                } else {
                    setTimeout(() => this.fetchLastScan(), 2000);
                }
            } else {
                throw new Error(data.error || 'Scan failed');
            }
        } catch (error) {
            this._showToast(`Scan error: ${error.message}`, 'error');
            this._resetScanButton();
        }
    }

    async _pollScanResults(scanId) {
        const maxAttempts = 30;
        let attempts = 0;

        while (attempts < maxAttempts) {
            try {
                const response = await fetch(`/api/vision/results/${scanId}`);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);

                const data = await response.json();
                if (data.status === 'completed') {
                    this._displayScanResults(data.data || data);
                    this._showToast('Text extracted successfully', 'success');
                    break;
                } else if (data.status === 'failed') {
                    throw new Error('Text extraction failed');
                }
            } catch (error) {
                if (attempts === maxAttempts - 1) {
                    this._showToast('Scan timeout', 'error');
                }
            }

            attempts++;
            await new Promise(resolve => setTimeout(resolve, 1000));
        }

        this._resetScanButton();
    }

    _displayScanResults(data) {
        const resultsElement = this.elements['.results-data'];
        if (!resultsElement) return;

        const formatResult = (value) => value || '-';
        const confidence = data.confidence ? `${(data.confidence * 100).toFixed(1)}%` : '-';
        const timestamp = data.timestamp ? new Date(data.timestamp).toLocaleString() : '-';

        resultsElement.innerHTML = `
            <div class="text-sm"><strong>Tracking ID:</strong> ${formatResult(data.tracking_id)}</div>
            <div class="text-sm"><strong>Order ID:</strong> ${formatResult(data.order_id)}</div>
            <div class="text-sm"><strong>RTS Code:</strong> ${formatResult(data.rts_code)}</div>
            <div class="text-sm"><strong>District:</strong> ${formatResult(data.district)}</div>
            <div class="text-sm"><strong>Confidence:</strong> ${confidence}</div>
            <div class="text-sm"><strong>Time:</strong> ${timestamp}</div>
        `;

        const scanCard = document.getElementById('scan-results-card');
        if (scanCard) {
            scanCard.classList.remove('hidden');
            this._updateScanCard(data);
        }
    }

    _updateScanCard(data) {
        const elements = {
            'tracking-id': data.tracking_id,
            'order-id': data.order_id,
            'rts-code': data.rts_code,
            'district': data.district,
            'confidence': data.confidence ? `${(data.confidence * 100).toFixed(1)}%` : '-',
            'scan-time': data.timestamp ? new Date(data.timestamp).toLocaleString() : '-'
        };

        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value || '-';
        });
    }

    async fetchLastScan() {
        try {
            const response = await fetch('/api/vision/last-scan');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const data = await response.json();
            if (data && data.success) {
                this._displayScanResults(data);
            }
        } catch (error) {
            console.error('Failed to fetch scan result:', error);
        }
    }

    _resetScanButton() {
        this.scanInProgress = false;
        const btnText = this.elements['btn-vision-scan .btn-text'];
        const btnSpinner = this.elements['btn-vision-scan .btn-spinner'];
        const scanButton = this.elements['btn-vision-scan'];

        if (btnText) btnText.textContent = 'Scan Label';
        if (btnSpinner) btnSpinner.classList.add('hidden');
        if (scanButton) scanButton.disabled = false;
    }

    _showToast(message, type) {
        console.log(`${type.toUpperCase()}: ${message}`);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new DashboardCore();
    dashboard.init();
});