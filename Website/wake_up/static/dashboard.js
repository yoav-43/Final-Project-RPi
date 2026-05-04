/**
 * WakeUp Dashboard — Analytics Engine
 * =====================================
 * Fetches the telemetry history for the current session from the REST API
 * and renders four Chart.js time-series charts alongside a filtered alert log.
 *
 * Entry point: window.onload → initDashboard()
 * Data source: GET /api/history/<DRIVE_ID>
 */

async function initDashboard() {
    logInfo(`Fetching history for session #${DRIVE_ID}...`);
    const response = await fetch(`/api/history/${DRIVE_ID}`);
    const data = await response.json();
    
    const labels = data.map(d => d.time);
    const tableBody = document.getElementById('alertLogBody');

    /**
     * Creates a Chart.js line chart in the specified canvas element.
     *
     * @param {string} ctx      - ID of the target <canvas> element.
     * @param {string} label    - Dataset label shown in the chart legend.
     * @param {number[]} dataset - Array of numeric values to plot.
     * @param {string} color    - CSS color string for the line.
     */
    const chartConfig = (ctx, label, dataset, color) => new Chart(document.getElementById(ctx), {
        type: 'line',
        data: { labels, datasets: [{ label, data: dataset, borderColor: color, tension: 0.2, fill: false }] },
        options: { responsive: true, scales: { y: { beginAtZero: false, grid: { color: '#27293d' } } } }
    });

    // Render the four primary telemetry metrics as time-series charts.
    chartConfig('perclosChart', 'PERCLOS Score (%)', data.map(d => d.perclos), '#4ecca3');
    chartConfig('earChart', 'Eye Aspect Ratio', data.map(d => d.ear), '#fca311');
    chartConfig('yawChart', 'Head Yaw (Horizontal)', data.map(d => d.yaw), '#36a2eb');
    chartConfig('pitchChart', 'Head Pitch (Vertical)', data.map(d => d.pitch), '#ff6384');

    // Populate the alert log table with rows where fatigue or distraction was detected.
    data.forEach(d => {
        if (d.distracted || d.perclos > 25) {
            const type = d.perclos > 25 ? "Fatigue / Drowsiness" : "Distraction Alert";
            const row = `<tr class="alert-row"><td>${d.time}</td><td>${type}</td><td>CRITICAL</td></tr>`;
            tableBody.innerHTML += row;
        }
    });
    
    logInfo("Dashboard initialization complete.");
}

/** Logs an informational message to the browser console. */
function logInfo(msg) { console.log(`[DASHBOARD INFO] ${msg}`); }

window.onload = initDashboard;
