/**
 * DASHBOARD ANALYTICS ENGINE
 * Handles real-time Chart.js rendering and dynamic table population.
 */

async function initDashboard() {
    logInfo(`Fetching history for session #${DRIVE_ID}...`);
    const response = await fetch(`/api/history/${DRIVE_ID}`);
    const data = await response.json();
    
    const labels = data.map(d => d.time);
    const tableBody = document.getElementById('alertLogBody');

    // Chart Helper Configuration
    const chartConfig = (ctx, label, dataset, color) => new Chart(document.getElementById(ctx), {
        type: 'line',
        data: { labels, datasets: [{ label, data: dataset, borderColor: color, tension: 0.2, fill: false }] },
        options: { responsive: true, scales: { y: { beginAtZero: false, grid: { color: '#27293d' } } } }
    });

    // Render 4 Primary Metrics
    chartConfig('perclosChart', 'PERCLOS Score (%)', data.map(d => d.perclos), '#4ecca3');
    chartConfig('earChart', 'Eye Aspect Ratio', data.map(d => d.ear), '#fca311');
    chartConfig('yawChart', 'Head Yaw (Horizontal)', data.map(d => d.yaw), '#36a2eb');
    chartConfig('pitchChart', 'Head Pitch (Vertical)', data.map(d => d.pitch), '#ff6384');

    // Populate the Historical Alert Log Table
    data.forEach(d => {
        if (d.distracted || d.perclos > 25) {
            const type = d.perclos > 25 ? "Fatigue / Drowsiness" : "Distraction Alert";
            const row = `<tr class="alert-row"><td>${d.time}</td><td>${type}</td><td>CRITICAL</td></tr>`;
            tableBody.innerHTML += row;
        }
    });
    
    logInfo("Dashboard initialization complete.");
}

function logInfo(msg) { console.log(`[DASHBOARD INFO] ${msg}`); }

window.onload = initDashboard;