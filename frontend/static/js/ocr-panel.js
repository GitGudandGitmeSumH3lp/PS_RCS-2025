/*
 * PS_RCS_PROJECT
 * Copyright (c) 2026. All rights reserved.
 * File: frontend/static/js/ocr-panel.js
 * Description: Frontend controller for Flash Express OCR scanning.
 *              Handles camera streaming, image uploads, and result display.
 */

/**
 * Controller class for the Flash Express OCR Panel.
 * Manages the modal UI, camera stream, image processing, and result polling.
 */
class FlashExpressOCRPanel {
    /**
     * Initialize the OCR Panel.
     * Sets up state, references DOM elements, and binds event listeners.
     */
    constructor() {
        this.elements = {};
        this.activeTab = 'camera';
        this.currentImage = null;
        this.currentImageType = null;
        this.streamActive = false;
        this.analysisInProgress = false;
        this.lastScanId = null;
        this.scanHistory = [];
        this.streamSrc = '/api/vision/stream';
        this.pollInterval = null;

        this._initializeElements();
        this._initializeEventListeners();
        this._setupKeyboardShortcuts();
        this._setupClipboardPaste();
    }

    /**
     * gathering all DOM elements. Decomposed to strictly meet 50-line limit.
     * @private
     */
    _initializeElements() {
        this.elements.modal = document.getElementById('ocr-scanner-modal');
        this.elements.closeBtn = document.getElementById('btn-ocr-close');
        this.elements.toastContainer = document.getElementById('toast-container');
        
        this._initTabElements();
        this._initCameraElements();
        this._initUploadElements();
        this._initPasteElements();
        this._initResultElements();
        this._initActionElements();
    }

    /** @private */
    _initTabElements() {
        this.elements.tabs = {
            camera: document.getElementById('btn-tab-camera'),
            upload: document.getElementById('btn-tab-upload'),
            paste: document.getElementById('btn-tab-paste')
        };
        this.elements.panels = {
            camera: document.getElementById('tab-camera'),
            upload: document.getElementById('tab-upload'),
            paste: document.getElementById('tab-paste')
        };
    }

    /** @private */
    _initCameraElements() {
        this.elements.stream = document.getElementById('ocr-stream');
        this.elements.streamOverlay = document.querySelector('.stream-overlay');
        this.elements.errorState = document.querySelector('#tab-camera .error-state');
        this.elements.captureBtn = document.getElementById('btn-ocr-capture');
    }

    /** @private */
    _initUploadElements() {
        this.elements.fileInput = document.getElementById('ocr-file-input');
        this.elements.fileDropzone = document.querySelector('.file-dropzone');
        this.elements.uploadPreview = document.getElementById('upload-preview-container');
        this.elements.uploadPreviewImg = document.getElementById('upload-preview-img');
        this.elements.clearUploadBtn = document.getElementById('btn-clear-upload');
    }

    /** @private */
    _initPasteElements() {
        this.elements.pasteDropzone = document.getElementById('paste-dropzone');
        this.elements.pastePreview = document.getElementById('paste-preview-container');
        this.elements.pastePreviewImg = document.getElementById('paste-preview-img');
        this.elements.clearPasteBtn = document.getElementById('btn-clear-paste');
    }

    /** @private */
    _initActionElements() {
        this.elements.analyzeBtn = document.getElementById('btn-analyze');
        this.elements.clearAllBtn = document.getElementById('btn-clear-all');
        this.elements.saveScanBtn = document.getElementById('btn-save-scan');
        this.elements.exportJsonBtn = document.getElementById('btn-export-json');
    }

    /** @private */
    _initResultElements() {
        this.elements.resultsPanel = document.getElementById('ocr-results-panel');
        this.elements.confidenceDot = document.getElementById('confidence-dot');
        this.elements.confidenceValue = document.getElementById('confidence-value');
        this.elements.confidenceFill = document.getElementById('confidence-fill');
        
        const ids = [
            'tracking-id', 'order-id', 'rts-code', 'rider-id', 'buyer-name',
            'buyer-address', 'weight', 'quantity', 'payment-type', 
            'confidence-display', 'timestamp', 'engine'
        ];
        
        this.elements.resultFields = {};
        ids.forEach(id => {
            const key = id.replace(/-([a-z])/g, g => g[1].toUpperCase()); // camelCase
            this.elements.resultFields[key] = document.getElementById(`result-${id}`);
        });
        this.elements.resultFields.processingTime = document.getElementById('processing-time');
    }

    /**
     * Attach event listeners to DOM elements.
     * @private
     */
    _initializeEventListeners() {
        if (this.elements.closeBtn) this.elements.closeBtn.addEventListener('click', () => this.closeModal());
        if (this.elements.captureBtn) this.elements.captureBtn.addEventListener('click', () => this._captureFrame());
        if (this.elements.analyzeBtn) this.elements.analyzeBtn.addEventListener('click', () => this.analyzeDocument());
        if (this.elements.clearAllBtn) this.elements.clearAllBtn.addEventListener('click', () => this._clearAll());
        if (this.elements.saveScanBtn) this.elements.saveScanBtn.addEventListener('click', () => this._saveToDatabase());
        if (this.elements.exportJsonBtn) this.elements.exportJsonBtn.addEventListener('click', () => this._exportToJson());
        
        this._bindTabEvents();
        this._bindFileEvents();
        this._bindCopyEvents();
        
        if (this.elements.modal) {
            this.elements.modal.addEventListener('close', () => this._handleModalClose());
        }
    }

    /** @private */
    _bindTabEvents() {
        Object.entries(this.elements.tabs).forEach(([tabId, btn]) => {
            if (!btn) return;
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                this.switchTab(tabId);
            });
            btn.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.switchTab(tabId);
                }
            });
        });
    }

    /** @private */
    _bindFileEvents() {
        if (this.elements.fileInput) {
            this.elements.fileInput.addEventListener('change', (e) => this._handleFileSelect(e));
        }
        if (this.elements.clearUploadBtn) {
            this.elements.clearUploadBtn.addEventListener('click', () => this._clearUpload());
        }
        if (this.elements.clearPasteBtn) {
            this.elements.clearPasteBtn.addEventListener('click', () => this._clearPaste());
        }
        this._setupDragDrop();
    }

    /** @private */
    _setupDragDrop() {
        if (!this.elements.fileDropzone) return;
        
        const zone = this.elements.fileDropzone;
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        });
        zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                this.elements.fileInput.files = e.dataTransfer.files;
                this._handleFileSelect({ target: this.elements.fileInput });
            }
        });
        zone.addEventListener('click', () => this.elements.fileInput.click());
    }

    /** @private */
    _bindCopyEvents() {
        document.querySelectorAll('.btn-copy').forEach(btn => {
            btn.addEventListener('click', () => {
                const fieldId = btn.getAttribute('data-field');
                this._copyToClipboard(fieldId);
            });
        });
    }

    /** @private */
    _setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if (!this.elements.modal || !this.elements.modal.open) return;
            
            if (e.key === 'Escape') this.closeModal();
            
            if ((e.ctrlKey || e.metaKey) && e.key === 'v' && this.activeTab === 'paste') {
                e.preventDefault();
                this._handleClipboardPaste();
            }
            
            if (e.key === 'Enter' && e.ctrlKey && this.elements.analyzeBtn && !this.elements.analyzeBtn.disabled) {
                this.analyzeDocument();
            }
        });
    }

    /** @private */
    _setupClipboardPaste() {
        if (this.elements.pasteDropzone) {
            this.elements.pasteDropzone.addEventListener('click', () => this._handleClipboardPaste());
            this.elements.pasteDropzone.addEventListener('paste', (e) => this._handleClipboardPasteEvent(e));
        }
    }

    /**
     * Switches the active input tab.
     * @param {string} tabId - 'camera', 'upload', or 'paste'
     */
    switchTab(tabId) {
        if (this.activeTab === tabId) return;
        this.activeTab = tabId;
        
        this._updateTabUI(tabId);
        
        if (tabId === 'camera') {
            this._startCameraStream();
        } else {
            this._stopCameraStream();
        }
        
        this._updateAnalyzeButtonState();
    }

    /** @private */
    _updateTabUI(tabId) {
        Object.entries(this.elements.tabs).forEach(([id, btn]) => {
            if (!btn) return;
            const isActive = id === tabId;
            btn.setAttribute('aria-selected', isActive);
            btn.setAttribute('tabindex', isActive ? '0' : '-1');
            btn.classList.toggle('active', isActive);
        });
        
        Object.entries(this.elements.panels).forEach(([id, panel]) => {
            if (!panel) return;
            panel.classList.toggle('hidden', id !== tabId);
            panel.classList.toggle('active', id === tabId);
        });
    }

    /** @private */
    _startCameraStream() {
        if (this.streamActive || !this.elements.stream) return;
        
        if (this.elements.errorState) this.elements.errorState.classList.add('hidden');
        
        this.elements.stream.src = `${this.streamSrc}?t=${Date.now()}`;
        this.streamActive = true;
        
        this.elements.stream.onload = () => {
            if (this.elements.streamOverlay) this.elements.streamOverlay.classList.remove('hidden');
        };
        
        this.elements.stream.onerror = () => this._handleStreamError();
    }

    /** @private */
    _handleStreamError() {
        if (this.elements.errorState) this.elements.errorState.classList.remove('hidden');
        if (this.elements.streamOverlay) this.elements.streamOverlay.classList.add('hidden');
        this.streamActive = false;
        
        // Retry logic
        setTimeout(() => {
            if (this.activeTab === 'camera' && this.elements.modal.open) {
                this._startCameraStream();
            }
        }, 2000);
    }

    /** @private */
    _stopCameraStream() {
        if (!this.streamActive || !this.elements.stream) return;
        this.elements.stream.src = '';
        this.streamActive = false;
        
        if (this.elements.streamOverlay) {
            this.elements.streamOverlay.classList.add('hidden');
        }
    }

    /**
     * Captures a frame from the live camera feed via API.
     */
    async _captureFrame() {
        try {
            const response = await fetch('/api/vision/capture', { method: 'POST' });
            if (!response.ok) throw new Error(`Capture failed: ${response.status}`);
            
            const data = await response.json();
            if (data.success && data.download_url) {
                this.currentImage = data.download_url;
                this.currentImageType = 'capture';
                this._showPreview(this.currentImage, 'camera');
                this._showToast('Frame captured successfully', 'success');
                this._updateAnalyzeButtonState();
            } else {
                throw new Error(data.error || 'Capture failed');
            }
        } catch (error) {
            console.error('[OCRPanel] Capture error:', error);
            this._showToast(`Failed to capture: ${error.message}`, 'error');
        }
    }

    /**
     * Handles file selection for upload.
     * @param {Event} event 
     */
    async _handleFileSelect(event) {
        const files = event.target.files;
        if (!files || files.length === 0) return;
        
        const file = files[0];
        if (file.size > 5 * 1024 * 1024) return this._showToast('File too large (max 5MB)', 'error');
        if (!file.type.match('image.*')) return this._showToast('Invalid file type', 'error');
        
        const reader = new FileReader();
        reader.onload = (e) => {
            this.currentImage = e.target.result;
            this.currentImageType = 'upload';
            this._showPreview(this.currentImage, 'upload');
            this._showToast('Image loaded', 'success');
            this._updateAnalyzeButtonState();
        };
        reader.readAsDataURL(file);
    }

    /** @private */
    _handleClipboardPasteEvent(event) {
        const items = event.clipboardData.items;
        for (const item of items) {
            if (item.type.indexOf('image') !== -1) {
                const blob = item.getAsFile();
                this._readBlobAsImage(blob);
                break;
            }
        }
    }

    /** @private */
    async _handleClipboardPaste() {
        try {
            const items = await navigator.clipboard.read();
            for (const item of items) {
                for (const type of item.types) {
                    if (type.startsWith('image/')) {
                        const blob = await item.getType(type);
                        this._readBlobAsImage(blob);
                        return;
                    }
                }
            }
            this._showToast('No image in clipboard', 'warning');
        } catch (error) {
            this._showToast('Clipboard access denied. Use Ctrl+V.', 'error');
        }
    }

    /** @private */
    _readBlobAsImage(blob) {
        const reader = new FileReader();
        reader.onload = (e) => {
            this.currentImage = e.target.result;
            this.currentImageType = 'paste';
            this._showPreview(this.currentImage, 'paste');
            this._showToast('Image pasted', 'success');
            this._updateAnalyzeButtonState();
        };
        reader.readAsDataURL(blob);
    }

    /** @private */
    _showPreview(imageDataUrl, tab) {
        if (tab === 'camera') {
            this._showToast('Frame captured', 'info');
            return;
        }

        const config = {
            upload: { container: this.elements.uploadPreview, img: this.elements.uploadPreviewImg },
            paste: { container: this.elements.pastePreview, img: this.elements.pastePreviewImg }
        };

        const target = config[tab];
        if (target && target.img) {
            target.img.src = imageDataUrl;
            target.container.classList.remove('hidden');
            
            // Hide dropzone
            const dropzone = tab === 'upload' ? this.elements.fileDropzone : this.elements.pasteDropzone;
            if (dropzone) dropzone.style.display = 'none';
        }
    }

    /** @private */
    _clearUpload() {
        this._resetImageState('upload');
        if (this.elements.uploadPreview) this.elements.uploadPreview.classList.add('hidden');
        if (this.elements.uploadPreviewImg) this.elements.uploadPreviewImg.src = '';
        if (this.elements.fileDropzone) this.elements.fileDropzone.style.display = '';
        if (this.elements.fileInput) this.elements.fileInput.value = '';
        this._updateAnalyzeButtonState();
    }

    /** @private */
    _clearPaste() {
        this._resetImageState('paste');
        if (this.elements.pastePreview) this.elements.pastePreview.classList.add('hidden');
        if (this.elements.pastePreviewImg) this.elements.pastePreviewImg.src = '';
        if (this.elements.pasteDropzone) this.elements.pasteDropzone.style.display = '';
        this._updateAnalyzeButtonState();
    }

    /** @private */
    _resetImageState(type) {
        this.currentImage = null;
        this.currentImageType = null;
    }

    /** @private */
    _clearAll() {
        this._clearUpload();
        this._clearPaste();
        if (this.activeTab === 'camera') this._resetImageState('camera');
        if (this.elements.resultsPanel) this.elements.resultsPanel.classList.add('hidden');
        this._resetResultFields();
        this._updateAnalyzeButtonState();
        this._showToast('All cleared', 'info');
    }

    /** @private */
    _updateAnalyzeButtonState() {
        if (!this.elements.analyzeBtn) return;
        const hasImage = this.currentImage !== null;
        this.elements.analyzeBtn.disabled = !hasImage || this.analysisInProgress;
        
        const content = this.analysisInProgress 
            ? '<span class="btn-icon">⏳</span><span class="btn-text">Processing...</span>'
            : '<span class="btn-icon">🔍</span><span class="btn-text">Analyze Receipt</span>';
        this.elements.analyzeBtn.innerHTML = content;
    }

    /**
     * Sends the current image for OCR analysis.
     */
    async analyzeDocument() {
        if (!this.currentImage || this.analysisInProgress) return;
        
        this.analysisInProgress = true;
        this._updateAnalyzeButtonState();
        
        try {
            const response = await this._submitImageForAnalysis();
            if (!response.ok) throw new Error(`Status ${response.status}`);
            
            const result = await response.json();
            if (result.success && result.scan_id) {
                this.lastScanId = result.scan_id;
                await this._pollForResults(result.scan_id);
            } else {
                throw new Error(result.error || 'Submission failed');
            }
        } catch (error) {
            console.error('[OCRPanel] Analysis error:', error);
            this._showToast(`Failed: ${error.message}`, 'error');
            this.analysisInProgress = false;
            this._updateAnalyzeButtonState();
        }
    }

    /** @private */
    async _submitImageForAnalysis() {
        if (this.currentImageType === 'capture') {
            const imageResponse = await fetch(this.currentImage);
            const blob = await imageResponse.blob();
            const formData = new FormData();
            formData.append('image', blob, 'capture.jpg');
            return fetch('/api/ocr/analyze', { method: 'POST', body: formData });
        } else {
            const base64Data = this.currentImage.split(',')[1];
            return fetch('/api/ocr/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image_data: base64Data })
            });
        }
    }

    /**
     * Polls for analysis results until completion or timeout.
     * @param {string|number} scanId 
     */
    async _pollForResults(scanId) {
        if (this.pollInterval) clearInterval(this.pollInterval);
        
        let attempts = 0;
        const maxAttempts = 40; // 20 seconds total
        
        return new Promise((resolve) => {
            this.pollInterval = setInterval(async () => {
                attempts++;
                const shouldStop = await this._checkResultStatus(scanId, attempts, maxAttempts);
                if (shouldStop) resolve();
            }, 500);
        });
    }

    /** @private */
    async _checkResultStatus(scanId, attempts, maxAttempts) {
        try {
            const response = await fetch(`/api/vision/results/${scanId}`);
            if (!response.ok) throw new Error('Poll failed');
            
            const data = await response.json();
            if (data.status === 'completed') {
                this._handleAnalysisComplete(data.data);
                return true;
            } else if (data.status === 'failed' || attempts >= maxAttempts) {
                this._handleAnalysisFailed(attempts >= maxAttempts);
                return true;
            }
        } catch (error) {
            if (attempts >= maxAttempts) {
                this._handleAnalysisFailed(true);
                return true;
            }
        }
        return false;
    }

    /** @private */
    _handleAnalysisComplete(data) {
        clearInterval(this.pollInterval);
        this.pollInterval = null;
        this._displayResults(data);
        this.analysisInProgress = false;
        this._updateAnalyzeButtonState();
        this._showToast('Analysis complete!', 'success');
    }

    /** @private */
    _handleAnalysisFailed(isTimeout) {
        clearInterval(this.pollInterval);
        this.pollInterval = null;
        this._showToast(isTimeout ? 'Analysis timeout' : 'Analysis failed', 'error');
        this.analysisInProgress = false;
        this._updateAnalyzeButtonState();
    }

    /**
     * Displays analysis results in the UI.
     * Decomposed to meet 50-line limit.
     * @param {Object} data 
     */
    _displayResults(data) {
        if (!this.elements.resultsPanel || !data) return;
        
        const fields = this._extractFieldsFromData(data);
        this._updateResultFields(fields);
        this._updateConfidenceIndicator(fields.confidence);
        
        this.elements.resultsPanel.classList.remove('hidden');
        this.elements.resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
        this.scanHistory.push({
            id: this.lastScanId,
            timestamp: new Date().toISOString(),
            fields: fields,
            imageType: this.currentImageType
        });
        
        this._updateDashboardLastScan(fields);
    }

    /** @private */
    _extractFieldsFromData(data) {
        const getVal = (snake, camel) => {
            const val = data[snake] ?? data[camel] ?? null;
            return val && String(val).trim() !== '' ? String(val).trim() : null;
        };

        return {
            trackingId: getVal('tracking_id', 'trackingId'),
            orderId: getVal('order_id', 'orderId'),
            rtsCode: getVal('rts_code', 'rtsCode'),
            riderId: getVal('rider_id', 'riderId'),
            buyerName: getVal('buyer_name', 'buyerName'),
            buyerAddress: getVal('buyer_address', 'buyerAddress'),
            weight: getVal('weight_g', 'weightG'),
            quantity: getVal('quantity', 'quantity'),
            paymentType: getVal('payment_type', 'paymentType'),
            confidence: Math.max(0, Math.min(1, parseFloat(data.confidence ?? 0))),
            timestamp: data.timestamp ?? data.scan_time ?? null,
            engine: data.engine ?? 'unknown',
            processingTimeMs: data.processing_time_ms ?? null
        };
    }

    /** @private */
    _updateResultFields(fields) {
        const setTxt = (key, val) => {
            if (this.elements.resultFields[key]) {
                this.elements.resultFields[key].textContent = val || '-';
            }
        };

        setTxt('trackingId', fields.trackingId);
        setTxt('orderId', fields.orderId);
        setTxt('rtsCode', fields.rtsCode);
        setTxt('riderId', fields.riderId);
        setTxt('buyerName', fields.buyerName);
        setTxt('buyerAddress', fields.buyerAddress);
        setTxt('weight', fields.weight ? `${fields.weight}g` : '-');
        setTxt('quantity', fields.quantity);
        setTxt('paymentType', fields.paymentType);
        setTxt('confidenceDisplay', fields.confidence ? `${(fields.confidence * 100).toFixed(1)}%` : '-');
        setTxt('timestamp', fields.timestamp ? this._formatTimestamp(fields.timestamp) : '-');
        setTxt('engine', fields.engine.charAt(0).toUpperCase() + fields.engine.slice(1));
        
        if (this.elements.resultFields.processingTime) {
            this.elements.resultFields.processingTime.textContent = 
                fields.processingTimeMs ? `Processed in ${fields.processingTimeMs}ms` : '';
        }
    }

    /** @private */
    _updateConfidenceIndicator(confidence) {
        if (!this.elements.confidenceDot) return;
        
        const percentage = Math.round(confidence * 100);
        if (this.elements.confidenceValue) {
            this.elements.confidenceValue.textContent = `${percentage}%`;
        }
        
        let colorClass = 'low';
        if (confidence >= 0.85) colorClass = 'high';
        else if (confidence >= 0.7) colorClass = 'medium';
        
        this.elements.confidenceDot.className = `confidence-dot ${colorClass}`;
        if (this.elements.confidenceFill) {
            this.elements.confidenceFill.style.width = `${percentage}%`;
            this.elements.confidenceFill.className = `confidence-fill ${colorClass}`;
        }
    }

    /** @private */
    _formatTimestamp(timestamp) {
        try {
            const date = new Date(timestamp);
            if (isNaN(date.getTime())) return timestamp;
            return date.toLocaleString('en-US', {
                year: 'numeric', month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit', second: '2-digit'
            });
        } catch { return timestamp; }
    }

    /** @private */
    _resetResultFields() {
        Object.values(this.elements.resultFields).forEach(el => {
            if (el) el.textContent = '-';
        });
        this._updateConfidenceIndicator(0);
    }

    /** @private */
    async _saveToDatabase() {
        if (!this.lastScanId) {
            this._showToast('No scan results to save', 'warning');
            return;
        }
        
        try {
            this._showToast('Scan saved automatically to database', 'success');
            
            console.log('[OCRPanel] Scan saved to database:', {
                scan_id: this.lastScanId,
                timestamp: new Date().toISOString()
            });
        } catch (error) {
            console.error('[OCRPanel] Save error:', error);
            this._showToast('Failed to save scan', 'error');
        }
    }

    /** @private */
    _exportToJson() {
        if (!this.lastScanId || this.scanHistory.length === 0) {
            return this._showToast('No results to export', 'warning');
        }
        
        const latestScan = this.scanHistory[this.scanHistory.length - 1];
        const blob = new Blob([JSON.stringify(latestScan, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `scan_${this.lastScanId}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        this._showToast('Exported JSON', 'success');
    }

    /** @private */
    _copyToClipboard(fieldId) {
        const key = fieldId.replace(/-([a-z])/g, g => g[1].toUpperCase());
        const element = this.elements.resultFields[key];
        
        if (!element) return;
        const text = element.textContent;
        
        if (!text || text === '-') return this._showToast('No data', 'warning');
        
        navigator.clipboard.writeText(text)
            .then(() => this._showToast('Copied', 'success'))
            .catch(() => this._showToast('Copy failed', 'error'));
    }

    /** @private */
    _updateDashboardLastScan(fields) {
        const card = document.getElementById('scan-results-card');
        if (!card) return;
        card.classList.remove('hidden');
        
        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val || '-';
        };
        
        setVal('tracking-id', fields.trackingId);
        setVal('order-id', fields.orderId);
        setVal('rts-code', fields.rtsCode);
        setVal('district', fields.riderId);
        setVal('confidence', fields.confidence ? `${(fields.confidence * 100).toFixed(1)}%` : '-');
        setVal('scan-time', this._formatTimestamp(fields.timestamp));
    }

    /** @private */
    _showToast(message, type = 'info') {
        if (!this.elements.toastContainer) return;
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.setAttribute('role', 'alert');
        
        const iconMap = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
        
        toast.innerHTML = `
            <span class="toast-icon">${iconMap[type] || 'ℹ️'}</span>
            <span class="toast-message">${message}</span>
            <button class="toast-close" aria-label="Close">✕</button>
        `;
        
        this.elements.toastContainer.appendChild(toast);
        
        const close = () => {
            toast.classList.add('hiding');
            setTimeout(() => toast.remove(), 300);
        };
        
        toast.querySelector('.toast-close').addEventListener('click', close);
        setTimeout(close, 5000);
    }

    /** @private */
    _handleModalClose() {
        this._stopCameraStream();
        if (this.pollInterval) clearInterval(this.pollInterval);
        this.activeTab = 'camera';
        this._clearAll();
    }

    /**
     * Opens the OCR Modal and prepares the camera.
     */
    openModal() {
        if (!this.elements.modal) return;
        this._resetResultFields();
        if (this.elements.resultsPanel) this.elements.resultsPanel.classList.add('hidden');
        this.elements.modal.showModal();
        this.switchTab('camera');
        this._showToast('Scanner Ready', 'info');
    }

    /**
     * Closes the OCR Modal and cleans up resources.
     */
    closeModal() {
        if (!this.elements.modal) return;
        this.elements.modal.close();
    }
}