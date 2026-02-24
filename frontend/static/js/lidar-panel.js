/*
 * PS_RCS_PROJECT
 * Copyright (c) 2026. All rights reserved.
 * File: frontend/static/js/lidar-panel.js
 * Description: LiDAR visualization panel – displays real-time point cloud from LiDAR sensor.
 */

class LiDARPanel {
    constructor(apiBase = window.location.origin) {
        this.apiBase = apiBase;
        this.elements = {};
        this.isScanning = false;
        this.pollInterval = null;
        this.animationFrame = null;
        this.latestPoints = [];
        this.canvasContext = null;
        this.modalOpen = false;
        this.statusPollInterval = null;
        this.initializeElements();
        this.initializeEventListeners();
    }

    initializeElements() {
        const ids = [
            'modal-lidar', 'lidar-canvas', 'btn-lidar-start', 'btn-lidar-stop',
            'btn-lidar-close', 'lidar-info', 'lidar-modal-status'
        ];
        ids.forEach(id => this.elements[id] = document.getElementById(id));
        const canvas = this.elements['lidar-canvas'];
        if (canvas) this.canvasContext = canvas.getContext('2d');
    }

    initializeEventListeners() {
        if (this.elements['btn-lidar-start']) {
            this.elements['btn-lidar-start'].addEventListener('click', () => this.startScanning());
        }
        if (this.elements['btn-lidar-stop']) {
            this.elements['btn-lidar-stop'].addEventListener('click', () => this.stopScanning());
        }
        if (this.elements['btn-lidar-close']) {
            this.elements['btn-lidar-close'].addEventListener('click', () => this.closeModal());
        }
        if (this.elements['modal-lidar']) {
            this.elements['modal-lidar'].addEventListener('close', () => this.closeModal());
        }
    }

    openModal() {
        const modal = this.elements['modal-lidar'];
        if (!modal) return;
        modal.showModal();
        this.modalOpen = true;
        this._resetState();
        this.fetchStatus();
        this.statusPollInterval = setInterval(() => this.fetchStatus(), 2000);
    }

    closeModal() {
        this.modalOpen = false;
        this.stopScanning();
        if (this.statusPollInterval) {
            clearInterval(this.statusPollInterval);
            this.statusPollInterval = null;
        }
        if (this.elements['modal-lidar']) {
            this.elements['modal-lidar'].close();
        }
        this._clearCanvas();
    }

    async startScanning() {
        if (this.isScanning) return;
        try {
            const res = await fetch(`${this.apiBase}/api/lidar/start`, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                this.isScanning = true;
                this._updateButtonStates();
                this.pollInterval = setInterval(() => this.fetchScanData(), 500); // poll every 500ms
                this._showToast('LiDAR scanning started', 'success');
            } else {
                this._showToast('Failed to start LiDAR', 'error');
            }
        } catch (err) {
            console.error('Start LiDAR error:', err);
            this._showToast('Network error', 'error');
        }
    }

    async stopScanning() {
        if (!this.isScanning) return;
        try {
            const res = await fetch(`${this.apiBase}/api/lidar/stop`, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                this.isScanning = false;
                this._updateButtonStates();
                if (this.pollInterval) {
                    clearInterval(this.pollInterval);
                    this.pollInterval = null;
                }
                this._clearCanvas();
                this._showToast('LiDAR stopped', 'success');
            } else {
                this._showToast('Failed to stop LiDAR', 'error');
            }
        } catch (err) {
            console.error('Stop LiDAR error:', err);
            this._showToast('Network error', 'error');
        }
    }

    async fetchStatus() {
        if (!this.modalOpen) return;
        try {
            const res = await fetch(`${this.apiBase}/api/lidar/status`);
            if (!res.ok) throw new Error('Status fetch failed');
            const data = await res.json();
            this.updateStatusIndicator(data.connected, data.scanning);
            if (this.elements['lidar-info']) {
                const info = `Port: ${data.port || 'N/A'} | Uptime: ${data.uptime || 0}s`;
                this.elements['lidar-info'].textContent = info;
            }
            if (data.connected && data.scanning && !this.isScanning) {
                this.isScanning = true;
                this._updateButtonStates();
                if (!this.pollInterval) {
                    this.pollInterval = setInterval(() => this.fetchScanData(), 500);
                }
            } else if ((!data.connected || !data.scanning) && this.isScanning) {
                this.isScanning = false;
                this._updateButtonStates();
                if (this.pollInterval) {
                    clearInterval(this.pollInterval);
                    this.pollInterval = null;
                }
                this._clearCanvas();
            }
            const errorState = document.querySelector('#modal-lidar .error-state');
            if (errorState) {
                if (data.connected) errorState.classList.add('hidden');
                else errorState.classList.remove('hidden');
            }
        } catch (err) {
            console.error('Status poll error:', err);
        }
    }

    async fetchScanData() {
        if (!this.modalOpen || !this.isScanning) return;
        try {
            const res = await fetch(`${this.apiBase}/api/lidar/scan`);
            if (!res.ok) throw new Error('Scan fetch failed');
            const data = await res.json();
            if (data.points && Array.isArray(data.points)) {
                this.latestPoints = data.points;
                if (!this.animationFrame) {
                    this.animationFrame = requestAnimationFrame(() => this.drawCanvas());
                }
            }
        } catch (err) {
            console.error('Scan data error:', err);
        }
    }

    drawCanvas() {
        this.animationFrame = null;
        const canvas = this.elements['lidar-canvas'];
        if (!canvas || !this.canvasContext || !this.modalOpen) return;
        const ctx = this.canvasContext;
        const w = canvas.width, h = canvas.height;
        ctx.clearRect(0, 0, w, h);

        const centerX = w / 2, centerY = h / 2;
        const maxDist = 8000; // mm
        const scale = (w / 2) / maxDist; // 250/8000

        // Draw grid lines (optional)
        ctx.strokeStyle = 'rgba(255,255,255,0.1)';
        ctx.lineWidth = 1;
        for (let i = 1; i <= 4; i++) {
            const r = i * maxDist / 4 * scale;
            ctx.beginPath();
            ctx.arc(centerX, centerY, r, 0, 2 * Math.PI);
            ctx.stroke();
        }

        // Draw robot center
        ctx.fillStyle = 'red';
        ctx.beginPath();
        ctx.arc(centerX, centerY, 5, 0, 2 * Math.PI);
        ctx.fill();

        // Draw points
        this.latestPoints.forEach(p => {
            const x = p.x || 0;
            const y = p.y || 0;
            const dist = Math.sqrt(x*x + y*y);
            const canvasX = centerX + x * scale;
            const canvasY = centerY - y * scale; // invert Y
            if (canvasX < 0 || canvasX > w || canvasY < 0 || canvasY > h) return;

            ctx.fillStyle = dist < 1000 ? 'orange' : 'cyan';
            ctx.beginPath();
            ctx.arc(canvasX, canvasY, 3, 0, 2 * Math.PI);
            ctx.fill();
        });
    }

    updateStatusIndicator(connected, scanning) {
        const statusEl = this.elements['lidar-modal-status'];
        if (!statusEl) return;
        const dot = statusEl.querySelector('.status-dot');
        const text = statusEl.querySelector('.status-text');
        if (connected) {
            statusEl.setAttribute('data-status', scanning ? 'online' : 'standby');
            if (dot) dot.style.backgroundColor = scanning ? 'hsl(var(--status-online))' : 'hsl(var(--status-standby))';
            if (text) text.textContent = scanning ? 'Scanning' : 'Connected';
        } else {
            statusEl.setAttribute('data-status', 'offline');
            if (dot) dot.style.backgroundColor = 'hsl(var(--status-offline))';
            if (text) text.textContent = 'Offline';
        }
    }

    _updateButtonStates() {
        const startBtn = this.elements['btn-lidar-start'];
        const stopBtn = this.elements['btn-lidar-stop'];
        if (startBtn) startBtn.disabled = this.isScanning;
        if (stopBtn) stopBtn.disabled = !this.isScanning;
    }

    _clearCanvas() {
        this.latestPoints = [];
        if (this.canvasContext) {
            const canvas = this.elements['lidar-canvas'];
            if (canvas) this.canvasContext.clearRect(0, 0, canvas.width, canvas.height);
        }
    }

    _resetState() {
        this.isScanning = false;
        this._updateButtonStates();
        this._clearCanvas();
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
            this.animationFrame = null;
        }
        this.updateStatusIndicator(false, false);
    }

    _showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => {
            if (toast.parentNode) toast.remove();
        }, 3000);
    }
}