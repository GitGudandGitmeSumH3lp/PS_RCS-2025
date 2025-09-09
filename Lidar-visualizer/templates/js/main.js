document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('lidarCanvas');
    const ctx = canvas.getContext('2d');
    const socket = io();

    socket.on('lidar_data', (data) => {
        drawLidarData(data.points);
    });

    function drawLidarData(points) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw the center point
        ctx.fillStyle = 'red';
        ctx.beginPath();
        ctx.arc(canvas.width / 2, canvas.height / 2, 5, 0, 2 * Math.PI);
        ctx.fill();

        // Draw each data point
        ctx.fillStyle = 'blue';
        points.forEach(point => {
            const angle = point.angle;
            const distance = point.range * 100; // Scale for better visualization

            // Convert polar coordinates to Cartesian coordinates
            const x = (canvas.width / 2) + distance * Math.cos(angle);
            const y = (canvas.height / 2) + distance * Math.sin(angle);

            ctx.beginPath();
            ctx.arc(x, y, 2, 0, 2 * Math.PI);
            ctx.fill();
        });
    }
});