// script.js
// Frontend JavaScript for Parcel Robot System

class ParcelRobotUI {
    constructor() {
        this.updateInterval = 1000; // Update every second
        this.motorKeepAliveInterval = null; // For explicit keep-alive if needed (not used with new backend)
        this.isHoldingButton = false; // State flag (optional for UI)
        this.init();
    }

    init() {
        this.updateStatus();
        this.updateLidar();
        this.updateHuskyLens();
        this.updateOCR();
        this.setupEventListeners();
        
        // Start periodic updates
        setInterval(() => {
            this.updateStatus();
            this.updateLidar();
            this.updateHuskyLens();
            this.updateOCR();
        }, this.updateInterval);
    }

    setupEventListeners() {
        // Motor control buttons - Updated for hold-to-move
        document.querySelectorAll('[data-command]').forEach(button => {
            // Use mousedown for starting movement
            button.addEventListener('mousedown', (event) => {
                event.preventDefault(); // Prevent default drag behavior
                const command = button.getAttribute('data-command');
                console.log(`Mouse down on ${command}`);
                this.isHoldingButton = true;
                this.sendMotorCommand(command); // This will start keep-alive on backend
            });

            // Use mouseup for stopping movement
            button.addEventListener('mouseup', (event) => {
                event.preventDefault();
                const command = button.getAttribute('data-command');
                console.log(`Mouse up on ${command}`);
                this.isHoldingButton = false;
                this.sendMotorCommand('stop'); // Send explicit stop
            });

            // Use mouseleave to stop if mouse drags out of button while pressed
            button.addEventListener('mouseleave', (event) => {
                // Only stop if we were holding the button
                if (this.isHoldingButton) {
                     event.preventDefault();
                     const command = button.getAttribute('data-command');
                     console.log(`Mouse left ${command} while pressed`);
                     this.isHoldingButton = false;
                     this.sendMotorCommand('stop'); // Send explicit stop
                }
            });

            // Optional: Prevent context menu on long press
            button.addEventListener('contextmenu', (event) => {
                event.preventDefault();
            });
        });
    }


    async sendMotorCommand(command) {
        // Prevent sending commands if not connected (optional check)
        // You could add a check here or rely on backend error handling

        try {
            // Send command via POST request
            // The backend MotorController will handle starting/stopping keep-alive
            const response = await fetch(`/api/motor/command/${command}`, {
                method: 'POST' // Important: Use POST
            });

            const data = await response.json();

            if (response.ok && data.status === 'success') {
                console.log(`✅ Motor command '${command}' sent successfully`);
                // Update UI element if needed, e.g., status light
            } else {
                console.error(`❌ Failed to send motor command '${command}':`, data.message);
                // Update UI to show error
                // alert(`Error sending command '${command}': ${data.message}`);
            }
        } catch (error) {
            console.error(`🌐 Network error sending motor command '${command}':`, error);
            // alert(`Network error sending command '${command}'. Is the server running?`);
        }
    }

    // --- (Other methods like updateStatus, updateLidar, etc. remain the same) ---
    async updateStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            
            const statusElement = document.getElementById('system-status');
            if (statusElement) {
                statusElement.innerHTML = `
                    <div>
                        <span class="status-indicator ${data.status === 'running' ? 'status-ok' : 'status-error'}"></span>
                        System: ${data.status}
                    </div>
                    <div>Modules: ${Object.keys(data.modules).filter(m => data.modules[m]).length}/${Object.keys(data.modules).length} active</div>
                `;
            }
        } catch (error) {
            console.error('Error updating status:', error);
        }
    }

    async updateLidar() {
        try {
            const response = await fetch('/api/lidar');
            const data = await response.json();
            
            const lidarElement = document.getElementById('lidar-data');
            if (lidarElement) {
                lidarElement.textContent = `Points detected: ${data.count}`;
            }
        } catch (error) {
            console.error('Error updating LiDAR data:', error);
        }
    }

    async updateHuskyLens() {
        try {
            const response = await fetch('/api/huskylens');
            const data = await response.json();
            
            const huskyElement = document.getElementById('huskylens-data');
            if (huskyElement) {
                if (data.objects && data.objects.length > 0) {
                    huskyElement.innerHTML = data.objects.map(obj => 
                        `<div>${obj.label} at (${obj.x}, ${obj.y})</div>`
                    ).join('');
                } else {
                    huskyElement.textContent = 'No objects detected';
                }
            }
        } catch (error) {
            console.error('Error updating HuskyLens data:', error);
        }
    }

    async updateOCR() {
        try {
            const response = await fetch('/api/ocr');
            const data = await response.json();
            
            const ocrElement = document.getElementById('ocr-data');
            if (ocrElement) {
                if (data.rts_code) {
                    ocrElement.innerHTML = `
                        <div><strong>RTS Code:</strong> ${data.rts_code}</div>
                        <div><strong>Order ID:</strong> ${data.order_id || 'N/A'}</div>
                        <div><strong>Tracking:</strong> ${data.tracking_number || 'N/A'}</div>
                        <div><strong>Buyer:</strong> ${data.buyer_name || 'N/A'}</div>
                    `;
                } else {
                    ocrElement.textContent = 'No OCR data available';
                }
            }
        } catch (error) {
            console.error('Error updating OCR data:', error);
        }
    }
    // --- (End of other methods) ---
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ParcelRobotUI();
});