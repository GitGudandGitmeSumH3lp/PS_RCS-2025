
/* frontend/static/js/ocr-panel.js - WITH BATCH UPLOAD AND CARD LAYOUT */

// Performance measurement utility (Phase 7.4)
const PerfMonitor = {
    marks: [],
    
    start(label) {
        try { performance.mark(`${label}-start`); } catch (e) {}
    },
    
    end(label) {
        try {
            performance.mark(`${label}-end`);
            performance.measure(label, `${label}-start`, `${label}-end`);
            const measure = performance.getEntriesByName(label).pop();
            if (measure) {
                console.log(`[PERF] ${label}: ${measure.duration.toFixed(2)}ms`);
                this.marks.push({ label, duration: measure.duration, timestamp: Date.now() });
            }
        } catch (e) {}
    },
    
    getReport() { return this.marks; },
    clear() {
        this.marks = [];
        try { performance.clearMarks(); performance.clearMeasures(); } catch (e) {}
    }
};

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
        PerfMonitor.start('panel-init');
        
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

        // Batch upload properties
        this.batchFiles = [];               // Array of selected files for batch
        this.batchResults = [];              // Results from batch upload
        this.batchInProgress = false;
        
        // Memory profiler (Phase 7.4)
        try {
            this.memoryCheckInterval = setInterval(() => {
                if (performance.memory) {
                    const usedMB = (performance.memory.usedJSHeapSize / 1048576).toFixed(2);
                    const totalMB = (performance.memory.totalJSHeapSize / 1048576).toFixed(2);
                    console.log(`[MEMORY] Used: ${usedMB}MB / Total: ${totalMB}MB`);
                    if (this.scanHistory.length > 50) {
                        console.warn('[MEMORY] History size exceeds 50 records');
                    }
                }
            }, 5000);
        } catch (e) {}
        
        this._initializeElements();
        this._initializeEventListeners();
        this._setupKeyboardShortcuts();
        this._setupClipboardPaste();
        
        PerfMonitor.end('panel-init');
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
        // New batch elements
        this.elements.batchFileList = document.getElementById('batch-file-list');
        this.elements.fileList = document.getElementById('file-list');
        this.elements.batchResultsContainer = document.getElementById('batch-results-container');
        this.elements.batchUploadBtn = document.getElementById('btn-batch-upload');
        this.elements.downloadBatchJson = document.getElementById('download-batch-json');
        this.elements.downloadBatchCsv = document.getElementById('download-batch-csv');
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
        this.elements.closeBatchBtn = document.getElementById('btn-close-batch');
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

        // Batch upload listeners
        if (this.elements.batchUploadBtn) {
            this.elements.batchUploadBtn.addEventListener('click', () => this._handleBatchUpload());
        }
        if (this.elements.downloadBatchJson) {
            this.elements.downloadBatchJson.addEventListener('click', () => this._downloadBatchJSON());
        }
        if (this.elements.downloadBatchCsv) {
            this.elements.downloadBatchCsv.addEventListener('click', () => this._downloadBatchCSV());
        }
        if (this.elements.closeBatchBtn) {
            this.elements.closeBatchBtn.addEventListener('click', () => this._closeBatchResults());
        }
        
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
        
        PerfMonitor.start('stream-start');
        
        this.elements.stream.src = `${this.streamSrc}?t=${Date.now()}`;
        this.streamActive = true;
        
        this.elements.stream.onload = () => {
            PerfMonitor.end('stream-start');
            if (this.elements.streamOverlay) this.elements.streamOverlay.classList.remove('hidden');
        };
        
        this.elements.stream.onerror = () => this._handleStreamError();
        
        // FPS Counter (Phase 7.4)
        try {
            let frameCount = 0;
            let lastFpsTime = performance.now();
            const fpsDisplay = document.createElement('div');
            fpsDisplay.id = 'fps-counter';
            fpsDisplay.style.cssText = 'position:absolute;top:10px;left:10px;background:rgba(0,0,0,0.7);color:#0f0;padding:5px;font-family:monospace;z-index:1000;';
            
            const updateFps = () => {
                frameCount++;
                const now = performance.now();
                if (now - lastFpsTime >= 1000) {
                    const fps = frameCount;
                    const latency = (1000 / fps).toFixed(1);
                    fpsDisplay.textContent = `FPS: ${fps} | Latency: ${latency}ms`;
                    frameCount = 0;
                    lastFpsTime = now;
                    if (latency > 16) {
                        console.warn(`[PERF] Frame latency ${latency}ms exceeds 16ms target`);
                    }
                }
                if (this.streamActive) requestAnimationFrame(updateFps);
            };
            
            this.elements.stream.parentElement.appendChild(fpsDisplay);
            requestAnimationFrame(updateFps);
            
            this._fpsCleanup = () => {
                fpsDisplay.remove();
                this.streamActive = false;
            };
        } catch (e) {}
    }

    /** @private */
    _handleStreamError() {
        if (this.elements.errorState) this.elements.errorState.classList.remove('hidden');
        if (this.elements.streamOverlay) this.elements.streamOverlay.classList.add('hidden');
        this.streamActive = false;
        
        setTimeout(() => {
            if (this.activeTab === 'camera' && this.elements.modal.open) {
                this._startCameraStream();
            }
        }, 2000);
    }

    /** @private */
    _stopCameraStream() {
        if (this._fpsCleanup) this._fpsCleanup();
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
        const files = Array.from(event.target.files);
        if (!files || files.length === 0) return;

        // Validate each file (size and type)
        const validFiles = [];
        const errors = [];
        for (const file of files) {
            if (file.size > 5 * 1024 * 1024) {
                errors.push(`${file.name} exceeds 5MB`);
                continue;
            }
            if (!file.type.match('image.*')) {
                errors.push(`${file.name} is not an image`);
                continue;
            }
            validFiles.push(file);
        }

        if (errors.length > 0) {
            this._showToast(errors.join('; '), 'error');
        }

        if (validFiles.length === 0) return;

        if (validFiles.length === 1) {
            // Single file – use existing preview logic
            const file = validFiles[0];
            const reader = new FileReader();
            reader.onload = (e) => {
                this.currentImage = e.target.result;
                this.currentImageType = 'upload';
                this._showPreview(this.currentImage, 'upload');
                this._updateAnalyzeButtonState();
                // Clear batch mode
                this.batchFiles = [];
                this.batchResults = [];
                if (this.elements.batchFileList) this.elements.batchFileList.classList.add('hidden');
                if (this.elements.batchResultsContainer) this.elements.batchResultsContainer.classList.remove('active');
            };
            reader.readAsDataURL(file);
        } else {
            // Multiple files – store for batch
            this.batchFiles = validFiles;
            this.batchResults = []; // clear previous results
            this.currentImage = null; // clear single preview
            // Hide single preview elements
            if (this.elements.uploadPreview) this.elements.uploadPreview.classList.add('hidden');
            if (this.elements.uploadPreviewImg) this.elements.uploadPreviewImg.src = '';
            if (this.elements.fileDropzone) this.elements.fileDropzone.style.display = '';
            // Show file list
            this._showFileList(validFiles);
            // Hide any previous batch results
            if (this.elements.batchResultsContainer) this.elements.batchResultsContainer.classList.remove('active');
            this._updateBatchButtonState();
        }
    }

    /**
     * Display the list of selected files for batch.
     * @private
     */
    _showFileList(files) {
        if (!this.elements.fileList) return;
        this.elements.fileList.innerHTML = '';
        files.forEach((file, idx) => {
            const li = document.createElement('li');
            li.innerHTML = `
                <span>${file.name}</span>
                <span class="file-size">${(file.size / 1024).toFixed(1)} KB</span>
            `;
            this.elements.fileList.appendChild(li);
        });
        if (this.elements.batchFileList) this.elements.batchFileList.classList.remove('hidden');
    }

    /**
     * Clear upload preview and batch file list.
     * @private
     */
    _clearUploadPreview() {
        if (this.elements.uploadPreview) this.elements.uploadPreview.classList.add('hidden');
        if (this.elements.uploadPreviewImg) this.elements.uploadPreviewImg.src = '';
        if (this.elements.fileDropzone) this.elements.fileDropzone.style.display = '';
        if (this.elements.batchFileList) this.elements.batchFileList.classList.add('hidden');
        this.batchFiles = [];
        this.batchResults = [];
        if (this.elements.batchResultsContainer) this.elements.batchResultsContainer.classList.remove('active');
    }

    /**
     * Update the batch upload button state.
     * @private
     */
    _updateBatchButtonState() {
        if (!this.elements.batchUploadBtn) return;
        const hasFiles = this.batchFiles.length > 0;
        this.elements.batchUploadBtn.disabled = !hasFiles || this.batchInProgress;
        this.elements.batchUploadBtn.innerHTML = this.batchInProgress
            ? '<span class="btn-icon">⏳</span><span class="btn-text">Uploading...</span>'
            : '<span class="btn-icon">📤</span><span class="btn-text">Upload All (Batch)</span>';
    }

    /**
     * Handle batch upload.
     * @private
     */
    async _handleBatchUpload() {
        if (this.batchFiles.length === 0 || this.batchInProgress) return;

        this.batchInProgress = true;
        this._updateBatchButtonState();

        const formData = new FormData();
        this.batchFiles.forEach(file => formData.append('images', file));

        try {
            const response = await fetch('/api/ocr/analyze_batch', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Batch upload failed');
            }

            this.batchResults = await response.json();

            // Update UI with results
            this._displayBatchResults(this.batchResults);

        } catch (error) {
            this._showToast(`Batch error: ${error.message}`, 'error');
        } finally {
            this.batchInProgress = false;
            this._updateBatchButtonState();
        }
    }

    /**
     * Displays batch OCR results in theme-compliant card layout
     * @param {Array<Object>} results - Array of OCR result objects
     * @private
     */
    _displayBatchResults(results) {
        if (!Array.isArray(results)) {
            console.error('Invalid results format');
            return;
        }

        const container = document.getElementById('batch-results-container');
        const grid = document.getElementById('batch-results-grid');
        
        if (!container || !grid) {
            console.error('Batch results container not found in DOM');
            return;
        }

        // Clear existing content
        grid.innerHTML = '';

        // Handle empty results
        if (results.length === 0) {
            grid.innerHTML = '<p class="batch-empty-message">No results to display</p>';
            container.classList.add('active');
            return;
        }

        // Generate cards
        results.forEach((result, index) => {
            const card = this._createBatchResultCard(result, index);
            grid.appendChild(card);
        });

        // Show container
        container.classList.add('active');
        
        // Set focus to close button
        const closeBtn = document.getElementById('btn-close-batch');
        if (closeBtn) {
            closeBtn.focus();
        }
    }

    /**
     * Creates a single batch result card element
     * @param {Object} result - OCR result object
     * @param {number} index - Card index in batch
     * @returns {HTMLElement} Card element
     * @private
     */
    _createBatchResultCard(result, index) {
        const card = document.createElement('article');
        card.className = 'batch-result-card';
        card.setAttribute('data-batch-index', index);
        card.setAttribute('role', 'article');

        const isSuccess = result.success === true;
        // Get filename
        const fileName = this.batchFiles[index] ? this.batchFiles[index].name : `File #${index + 1}`;
        
        // Header
        const header = `
            <div class="batch-card-header">
            <span class="batch-card-number">${this._escapeHtml(fileName)}</span>
            <span class="batch-card-status batch-status-${isSuccess ? 'success' : 'error'}" 
                    role="status" 
                    aria-label="${isSuccess ? 'Success' : 'Failed'}">
                ${isSuccess ? '✓ Success' : '✗ Failed'}
            </span>
            </div>
        `;

        let body = '';
        
        if (isSuccess) {
            // Get the raw data (either result.data or result itself)
            const rawData = result.data || result;
            // If rawData has a 'fields' property, use that; otherwise use rawData
            const fieldsData = rawData.fields || rawData;
            const fields = this._extractFieldsFromData(fieldsData);
            
            // UPDATED MAPPING
            const fieldMap = {
                trackingId: 'Tracking ID',
                orderId: 'Order ID',
                rtsCode: 'RTS Code',
                buyerName: 'Buyer Name',
                buyerAddress: 'Address',
                weight: 'Weight',
                quantity: 'Qty',
                paymentType: 'Payment'
            };

            const fieldRows = Object.entries(fieldMap).map(([key, label]) => {
            let value = fields[key];
            // Formatting
            if (value === null || value === undefined) value = 'N/A';
            if (key === 'weight' && value !== 'N/A' && !String(value).endsWith('g')) value += 'g';

            return `
                <div class="batch-field" data-field="${key}">
                <label class="batch-field-label">${label}</label>
                <div class="batch-field-value-wrapper">
                    <span class="batch-field-value">${this._escapeHtml(String(value))}</span>
                    <button class="btn-copy-field" 
                            data-field-id="${key}" 
                            data-batch-index="${index}"
                            data-value="${this._escapeHtml(String(value))}"
                            aria-label="Copy ${label}">
                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                        <path d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"/>
                        <path d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"/>
                    </svg>
                    </button>
                </div>
                </div>
            `;
            }).join('');

            body = `<div class="batch-card-body"><div class="batch-field-group">${fieldRows}</div></div>`;
        } else {
            // Error state
            const errorMessage = result.error || 'OCR processing failed';
            body = `
            <div class="batch-card-body">
                <div class="batch-error-message" role="alert">
                <svg class="batch-error-icon" width="20" height="20" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
                </svg>
                <span>${this._escapeHtml(errorMessage)}</span>
                </div>
            </div>
            `;
        }

        card.innerHTML = header + body;

        // Attach copy button event listeners
        if (isSuccess) {
            card.querySelectorAll('.btn-copy-field').forEach(btn => {
            btn.addEventListener('click', (e) => this._handleBatchCopyField(e));
            });
        }

        return card;
    }

    /**
     * Handles copy button click for batch result fields
     * @param {Event} event - Click event
     * @private
     */
    async _handleBatchCopyField(event) {
        const button = event.currentTarget;
        const value = button.getAttribute('data-value');
        const fieldId = button.getAttribute('data-field-id');

        const success = await this._copyText(value);
        if (success) {
            this._showToast(`${fieldId} copied`, 'success');
            // Visual feedback
            button.style.transform = 'scale(0.9)';
            setTimeout(() => {
            button.style.transform = 'scale(1)';
            }, 150);
        } else {
            this._showToast('Failed to copy', 'error');
        }
    }

    /**
     * Copy text to clipboard with fallback
     * @param {string} text - Text to copy
     * @returns {Promise<boolean>} True if successful
     * @private
     */
    async _copyText(text) {
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(text);
                return true;
            }
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            const success = document.execCommand('copy');
            document.body.removeChild(textarea);
            return success;
        } catch (e) {
            console.error('Copy failed:', e);
            return false;
        }
    }

    /**
     * Escapes HTML special characters
     * @param {string} unsafe - Unsafe string
     * @returns {string} Escaped string
     * @private
     */
    _escapeHtml(unsafe) {
        if (typeof unsafe !== 'string') return '';
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    /**
     * Close batch results container
     * @private
     */
    _closeBatchResults() {
        const container = document.getElementById('batch-results-container');
        if (container) {
            container.classList.remove('active');
        }
    }

    /**
     * Download batch results as JSON.
     * @private
     */
    _downloadBatchJSON() {
        if (!this.batchResults.length) return;
        const dataStr = JSON.stringify(this.batchResults, null, 2);
        const blob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `batch_results_${new Date().toISOString().slice(0,10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    /**
     * Download batch results as CSV.
     * @private
     */
    _downloadBatchCSV() {
        if (!this.batchResults.length) return;

        const headers = ['File', 'Success', 'Tracking Number', 'Order ID', 'Buyer Name', 'Weight', 'Quantity', 'Error'];
        const rows = this.batchResults.map((r, idx) => {
            const file = this.batchFiles[idx] ? this.batchFiles[idx].name : `File ${idx+1}`;
            if (!r.success) {
                return [file, 'No', '', '', '', '', '', r.error || 'Unknown error'];
            }
            const fields = this._extractFieldsFromData(r);
            return [
                file,
                'Yes',
                fields.trackingId || '',
                fields.orderId || '',
                fields.buyerName || '',
                fields.weight || '',
                fields.quantity || '',
                ''
            ];
        });

        let csvContent = headers.join(',') + '\n';
        rows.forEach(row => {
            csvContent += row.map(cell => `"${cell}"`).join(',') + '\n';
        });

        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `batch_results_${new Date().toISOString().slice(0,10)}.csv`;
        a.click();
        URL.revokeObjectURL(url);
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
        this._clearUploadPreview(); // our new method
        if (this.activeTab === 'camera') this._resetImageState('camera');
        if (this.elements.resultsPanel) this.elements.resultsPanel.classList.add('hidden');
        this._resetResultFields();
        this._updateAnalyzeButtonState();
        this.batchFiles = [];
        this.batchResults = [];
        if (this.elements.batchResultsContainer) this.elements.batchResultsContainer.classList.remove('active');
        if (this.elements.batchFileList) this.elements.batchFileList.classList.add('hidden');
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
        
        PerfMonitor.start('analyze-workflow');
        this.analysisInProgress = true;
        this._updateAnalyzeButtonState();
        
        try {
            const response = await this._submitImageForAnalysis();
            if (!response.ok) throw new Error(`Status ${response.status}`);
            
            const result = await response.json();
            if (result.success && result.scan_id) {
                this.lastScanId = result.scan_id;
                await this._pollForResults(result.scan_id);
                PerfMonitor.end('analyze-workflow'); // success path
            } else {
                throw new Error(result.error || 'Submission failed');
            }
        } catch (error) {
            console.error('[OCRPanel] Analysis error:', error);
            this._showToast(`Failed: ${error.message}`, 'error');
        } finally {
            this.analysisInProgress = false;
            this._updateAnalyzeButtonState();
            // Ensure the measurement ends even on error (but we won't double-call)
            if (!this.analysisInProgress) {
                PerfMonitor.end('analyze-workflow');
            }
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
        const maxAttempts = 40;
        
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
        PerfMonitor.start('display-results');
        
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
        
        PerfMonitor.end('display-results');
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
        // Clean up memory profiler
        if (this.memoryCheckInterval) {
            clearInterval(this.memoryCheckInterval);
            this.memoryCheckInterval = null;
        }
        this._stopCameraStream();
        if (this.pollInterval) clearInterval(this.pollInterval);
        this.activeTab = 'camera';
        this._clearAll();
    }

    /**
     * Opens the OCR Modal and prepares the camera.
     */
    openModal() {
        PerfMonitor.start('modal-open');
        
        if (!this.elements.modal) return;
        this._resetResultFields();
        if (this.elements.resultsPanel) this.elements.resultsPanel.classList.add('hidden');
        this.elements.modal.showModal();
        this.switchTab('camera');
        this._showToast('Scanner Ready', 'info');
        
        PerfMonitor.end('modal-open');
    }

    /**
     * Closes the OCR Modal and cleans up resources.
     */
    closeModal() {
        if (!this.elements.modal) return;
        this.elements.modal.close();
    }
}