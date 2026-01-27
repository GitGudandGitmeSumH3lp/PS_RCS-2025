// Send HTTP POST command to backend
function sendCommand(endpoint) {
    fetch(endpoint, { method: 'POST' })
        .then(response => response.json())
        .then(data => console.log("✅ Success:", data))
        .catch(err => console.error("❌ Error:", err));
}

// Hold command while button is pressed
function holdCommand(endpoint) {
    sendCommand(endpoint);
}

// Stop on release
function sendStop() {
    sendCommand('/motor/stop');
}