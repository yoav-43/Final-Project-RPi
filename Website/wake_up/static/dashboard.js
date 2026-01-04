let charts = {}; // Global chart instances

/**
 * Fetches telemetry data for the specific DRIVE_ID defined in the HTML.
 */
async function fetchTelemetry() {
    if (typeof DRIVE_ID === 'undefined') return; // Safety check

    try {
        const response = await fetch(`/api/history/${DRIVE_ID}`);
        if (!response.ok) throw new Error("Failed to fetch drive history");
        
        const data = await response.json();
        updateDashboard(data);
    } catch (error) {
        console.error("Error:", error);
    }
}

function updateDashboard(data) {
    const labels = data.map(d => d.time);

    // 1. Update Charts
    updatePerclosChart(labels, data.map(d => d.perclos));
    updateFaceChart(labels, data.map(d => d.ear), data.map(d => d.mar));
    updateHeadChart(labels, data.map(d => d.yaw), data.map(d => d.pitch), data.map(d => d.roll));
    updateAlertsChart(labels, data);

    // 2. Update KPI numbers
    calculateStats(data);
}

// --- Chart Configurations ---

function updatePerclosChart(labels, perclosData) {
    const ctx = document.getElementById('perclosChart').getContext('2d');
    if (!charts.perclos) {
        charts.perclos = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Fatigue (PERCLOS %)',
                    data: perclosData,
                    borderColor: '#ff6384',
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: { responsive: true, scales: { y: { max: 100, beginAtZero: true, grid: { color: '#3d3d5c' } }, x: { grid: { color: '#3d3d5c' } } } }
        });
    } else {
        charts.perclos.data.labels = labels;
        charts.perclos.data.datasets[0].data = perclosData;
        charts.perclos.update('none');
    }
}

function updateFaceChart(labels, earData, marData) {
    const ctx = document.getElementById('faceChart').getContext('2d');
    if (!charts.face) {
        charts.face = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    { label: 'EAR', data: earData, borderColor: '#36a2eb', tension: 0.1 },
                    { label: 'MAR', data: marData, borderColor: '#ffcd56', tension: 0.1 }
                ]
            },
            options: { responsive: true, scales: { y: { grid: { color: '#3d3d5c' } }, x: { grid: { color: '#3d3d5c' } } } }
        });
    } else {
        charts.face.data.labels = labels;
        charts.face.data.datasets[0].data = earData;
        charts.face.data.datasets[1].data = marData;
        charts.face.update('none');
    }
}

function updateHeadChart(labels, yaw, pitch, roll) {
    const ctx = document.getElementById('headChart').getContext('2d');
    if (!charts.head) {
        charts.head = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    { label: 'Yaw', data: yaw, borderColor: '#4bc0c0', borderWidth: 1, pointRadius: 0 },
                    { label: 'Pitch', data: pitch, borderColor: '#9966ff', borderWidth: 1, pointRadius: 0 },
                    { label: 'Roll', data: roll, borderColor: '#ff9f40', borderWidth: 1, pointRadius: 0 }
                ]
            },
            options: { responsive: true, scales: { y: { grid: { color: '#3d3d5c' } }, x: { grid: { color: '#3d3d5c' } } } }
        });
    } else {
        charts.head.data.labels = labels;
        charts.head.data.datasets[0].data = yaw;
        charts.head.data.datasets[1].data = pitch;
        charts.head.data.datasets[2].data = roll;
        charts.head.update('none');
    }
}

function updateAlertsChart(labels, data) {
    const ctx = document.getElementById('alertsChart').getContext('2d');
    const fatiguePoints = data.map(d => d.perclos > 25 ? 1 : null);
    const distractPoints = data.map(d => d.distracted ? 2 : null);

    if (!charts.alerts) {
        charts.alerts = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    { label: 'Fatigue', data: fatiguePoints, backgroundColor: '#ff6384' },
                    { label: 'Distraction', data: distractPoints, backgroundColor: '#36a2eb' }
                ]
            },
            options: { 
                scales: { 
                    y: { min: 0, max: 3, grid: { color: '#3d3d5c' }, ticks: { callback: v => v==1?'Fatigue':v==2?'Distract':'' } },
                    x: { grid: { color: '#3d3d5c' } }
                } 
            }
        });
    } else {
        charts.alerts.data.labels = labels;
        charts.alerts.data.datasets[0].data = fatiguePoints;
        charts.alerts.data.datasets[1].data = distractPoints;
        charts.alerts.update('none');
    }
}

function calculateStats(data) {
    let fatigueCount = 0;
    let distractionCount = 0;

    data.forEach(row => {
        if (row.perclos > 25) fatigueCount++;
        if (row.distracted) distractionCount++;
    });

    const fEl = document.getElementById("fatigueCount");
    const dEl = document.getElementById("distractionCount");
    if(fEl) fEl.innerText = fatigueCount;
    if(dEl) dEl.innerText = distractionCount;
}

// Fetch immediately, then every 3 seconds
fetchTelemetry();
setInterval(fetchTelemetry, 3000);