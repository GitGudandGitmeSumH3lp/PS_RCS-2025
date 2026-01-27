# gui.py
# GUI application for Parcel Robot System using PyQt5

import sys
import threading
import time
import cv2
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFrame
)
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView

class ParcelRobotGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parcel Robot System")
        self.setGeometry(100, 100, 1200, 800)
        
        # Camera setup
        self.camera = cv2.VideoCapture(0)
        self.lock = threading.Lock()
        
        # Timer for camera updates
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_camera_feed)
        self.timer.start(50)  # Update every 50ms
        
        self.init_ui()
        
    def init_ui(self):
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Title
        title = QLabel("📦 Parcel Robot System")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title)
        
        # Content layout
        content_layout = QHBoxLayout()
        
        # Left panel - Camera feed
        left_panel = QFrame()
        left_panel.setFrameStyle(QFrame.StyledPanel)
        left_layout = QVBoxLayout(left_panel)
        
        camera_label = QLabel("Camera Feed")
        camera_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        left_layout.addWidget(camera_label)
        
        self.camera_label = QLabel()
        self.camera_label.setMinimumSize(640, 480)
        self.camera_label.setStyleSheet("background-color: black;")
        left_layout.addWidget(self.camera_label)
        
        content_layout.addWidget(left_panel)
        
        # Right panel - Controls and data
        right_panel = QFrame()
        right_panel.setFrameStyle(QFrame.StyledPanel)
        right_layout = QVBoxLayout(right_panel)
        
        # Control buttons
        controls_label = QLabel("Robot Controls")
        controls_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        right_layout.addWidget(controls_label)
        
        # Grid for control buttons
        controls_grid = QGridLayout()
        
        forward_btn = QPushButton("↑ FORWARD")
        forward_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 15px;")
        forward_btn.clicked.connect(lambda: self.send_command("forward"))
        controls_grid.addWidget(forward_btn, 0, 1)
        
        left_btn = QPushButton("← LEFT")
        left_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 15px;")
        left_btn.clicked.connect(lambda: self.send_command("left"))
        controls_grid.addWidget(left_btn, 1, 0)
        
        stop_btn = QPushButton("STOP")
        stop_btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 15px;")
        stop_btn.clicked.connect(lambda: self.send_command("stop"))
        controls_grid.addWidget(stop_btn, 1, 1)
        
        right_btn = QPushButton("RIGHT →")
        right_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 15px;")
        right_btn.clicked.connect(lambda: self.send_command("right"))
        controls_grid.addWidget(right_btn, 1, 2)
        
        backward_btn = QPushButton("↓ BACKWARD")
        backward_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 15px;")
        backward_btn.clicked.connect(lambda: self.send_command("backward"))
        controls_grid.addWidget(backward_btn, 2, 1)
        
        right_layout.addLayout(controls_grid)
        
        # System status
        status_label = QLabel("System Status")
        status_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 20px;")
        right_layout.addWidget(status_label)
        
        self.status_display = QLabel("System running...")
        self.status_display.setStyleSheet("background-color: #ecf0f1; padding: 10px; border-radius: 5px;")
        self.status_display.setWordWrap(True)
        right_layout.addWidget(self.status_display)
        
        # Data displays
        data_label = QLabel("Sensor Data")
        data_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 20px;")
        right_layout.addWidget(data_label)
        
        self.data_display = QLabel("Waiting for data...")
        self.data_display.setStyleSheet("background-color: #ecf0f1; padding: 10px; border-radius: 5px;")
        self.data_display.setWordWrap(True)
        right_layout.addWidget(self.data_display)
        
        content_layout.addWidget(right_panel)
        
        # Add content layout to main
        main_layout.addLayout(content_layout)
        
        # Web view for dashboard
        web_label = QLabel("Web Dashboard")
        web_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 20px;")
        main_layout.addWidget(web_label)
        
        self.web_view = QWebEngineView()
        self.web_view.setUrl(QUrl("http://localhost:5000/dashboard"))
        main_layout.addWidget(self.web_view)
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
    def update_camera_feed(self):
        """Update the camera feed in the GUI."""
        with self.lock:
            ret, frame = self.camera.read()
            
        if ret:
            # Convert to RGB
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            self.camera_label.setPixmap(pixmap.scaled(
                self.camera_label.width(),
                self.camera_label.height(),
                Qt.KeepAspectRatio
            ))
    
    def send_command(self, command):
        """Send motor command to the robot."""
        try:
            response = requests.get(f"http://localhost:5000/api/motor/{command}")
            if response.status_code == 200:
                self.statusBar().showMessage(f"Command sent: {command}")
            else:
                self.statusBar().showMessage(f"Failed to send command: {command}")
        except Exception as e:
            self.statusBar().showMessage(f"Error: {str(e)}")
    
    def closeEvent(self, event):
        """Clean up when closing the application."""
        self.timer.stop()
        self.camera.release()
        event.accept()

def generate_frames():
    """Generate frames for web streaming (reused from camstream)."""
    camera = cv2.VideoCapture(0)
    lock = threading.Lock()
    
    while True:
        with lock:
            success, frame = camera.read()
            if not success:
                continue

            # Encode as JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

        # Stream as multipart response
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# Main execution
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ParcelRobotGUI()
    window.show()
    sys.exit(app.exec_())