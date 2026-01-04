/**
 * DRIVE ANALYTICS ENGINE
 * Fetches telemetry and renders Chart.js visualizations.
 */

async function initDashboard() {
    const response = await fetch(`/api/history/${DRIVE_ID}`);
    const data = await response.json();

    const labels = data.map(d => d.time);

    // 1. PERCLOS Chart
    new Chart(document.getElementById('perclosChart'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{ label: 'PERCLOS %', data: data.map(d => d.perclos), borderColor: '#4ecca3', tension: 0.3 }]
        }
    });

    // 2. EAR Chart
    new Chart(document.getElementById('earChart'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{ label: 'EAR Value', data: data.map(d => d.ear), borderColor: '#fca311', tension: 0.1 }]
        }
    });

    // 3. Yaw Chart
    new Chart(document.getElementById('yawChart'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{ label: 'Yaw (Horizontal)', data: data.map(d => d.yaw), borderColor: '#36a2eb' }]
        }
    });

    // 4. Pitch Chart
    new Chart(document.getElementById('pitchChart'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{ label: 'Pitch (Vertical)', data: data.map(d => d.pitch), borderColor: '#ff6384' }]
        }
    });
}

window.onload = initDashboard;