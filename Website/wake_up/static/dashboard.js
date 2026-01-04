// Global storage for Chart instances to allow updating
let charts = {}; 

// -----------------------------------------------------------------------------
// Data Fetching Logic
// -----------------------------------------------------------------------------
async function fetchTelemetry() {
    try {
        const response = await fetch('/api/history');
        if (!response.ok) throw new Error("API Response Error");
        
        const data = await response.json();
        updateDashboard(data);
    } catch (error) {
        console.error("Error fetching telemetry:", error);
    }
}

// Main Update Function
function updateDashboard(data) {
    // Extract Time Labels
    const labels = data.map(d => d.time);

    // 1. Update all 4 Charts
    updatePerclosChart(labels, data.map(d => d.perclos));
    updateFaceChart(labels, data.map(d => d.ear), data.map(d => d.mar));
    updateHeadChart(labels, data.map(d => d.yaw), data.map(d => d.pitch), data.map(d => d.roll));
    updateAlertsChart(labels, data);

    // 2. Update Summary Table and KPI Counters
    calculateStats(data);
}

// -----------------------------------------------------------------------------
// Chart Logic
// -----------------------------------------------------------------------------

// Chart 1: PERCLOS (Fatigue)
function updatePerclosChart(labels, perclosData) {
    const ctx = document.getElementById('perclosChart').getContext('2d');
    if (!charts.perclos) {
        charts.perclos = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Fatigue (%)',
                    data: perclosData,
                    borderColor: '#ff6384', // Red
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: { 
                responsive: true, 
                scales: { 
                    y: { max: 100, beginAtZero: true, grid: { color: '#3d3d5c' } },
                    x: { grid: { color: '#3d3d5c' } }
                } 
            }
        });
    } else {
        charts.perclos.data.labels = labels;
        charts.perclos.data.datasets[0].data = perclosData;
        charts.perclos.update('none'); // 'none' prevents animation flickering
    }
}

// Chart 2: Face Metrics (EAR / MAR)
function updateFaceChart(labels, earData, marData) {
    const ctx = document.getElementById('faceChart').getContext('2d');
    if (!charts.face) {
        charts.face = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    { label: 'Eye Openness (EAR)', data: earData, borderColor: '#36a2eb', tension: 0.1 },
                    { label: 'Yawning (MAR)', data: marData, borderColor: '#ffcd56', tension: 0.1 }
                ]
            },
            options: { 
                responsive: true,
                scales: { 
                    y: { grid: { color: '#3d3d5c' } },
                    x: { grid: { color: '#3d3d5c' } }
                }
            }
        });
    } else {
        charts.face.data.labels = labels;
        charts.face.data.datasets[0].data = earData;
        charts.face.data.datasets[1].data = marData;
        charts.face.update('none');
    }
}

// Chart 3: Head Pose (Yaw / Pitch / Roll)
function updateHeadChart(labels, yaw, pitch, roll) {
    const ctx = document.getElementById('headChart').getContext('2d');
    if (!charts.head) {
        charts.head = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    { label: 'Yaw (Turn)', data: yaw, borderColor: '#4bc0c0', borderWidth: 1, pointRadius: 1 },
                    { label: 'Pitch (Nod)', data: pitch, borderColor: '#9966ff', borderWidth: 1, pointRadius: 1 },
                    { label: 'Roll (Tilt)', data: roll, borderColor: '#ff9f40', borderWidth: 1, pointRadius: 1 }
                ]
            },
            options: { 
                responsive: true,
                scales: { 
                    y: { grid: { color: '#3d3d5c' } },
                    x: { grid: { color: '#3d3d5c' } }
                }
            }
        });
    } else {
        charts.head.data.labels = labels;
        charts.head.data.datasets[0].data = yaw;
        charts.head.data.datasets[1].data = pitch;
        charts.head.data.datasets[2].data = roll;
        charts.head.update('none');
    }
}

// Chart 4: Alerts Timeline (Visualizes distinct events)
function updateAlertsChart(labels, data) {
    const ctx = document.getElementById('alertsChart').getContext('2d');
    
    // Map data to categories: 1 = Fatigue, 2 = Distraction, null = Normal
    const fatiguePoints = data.map(d => d.perclos > 25 ? 1 : null); 
    const distractPoints = data.map(d => d.distracted ? 2 : null);

    if (!charts.alerts) {
        charts.alerts = new Chart(ctx, {
            type: 'bar', // Bar chart used to show "blocks" of time
            data: {
                labels: labels,
                datasets: [
                    { label: 'Fatigue Alert', data: fatiguePoints, backgroundColor: '#ff6384', barThickness: 10 },
                    { label: 'Distraction Alert', data: distractPoints, backgroundColor: '#36a2eb', barThickness: 10 }
                ]
            },
            options: { 
                scales: { 
                    y: { 
                        min: 0, max: 3, 
                        grid: { color: '#3d3d5c' },
                        ticks: { callback: (v) => v==1?'Fatigue':v==2?'Distraction':'' } 
                    },
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

// -----------------------------------------------------------------------------
// Table & Stats Logic
// -----------------------------------------------------------------------------
function calculateStats(data) {
    let fatigueCount = 0;
    let distractionCount = 0;
    const tableBody = document.querySelector("#alertsTable tbody");
    tableBody.innerHTML = ""; // Clear existing rows

    // Iterate backwards (Newest first)
    [...data].reverse().forEach(row => {
        let alertType = "";
        let alertClass = "";
        let valString = "";

        // Check for Fatigue (Threshold > 25%)
        if (row.perclos > 25) { 
            fatigueCount++;
            alertType = "Fatigue Hazard";
            alertClass = "alert-fatigue";
            valString = `PERCLOS: ${row.perclos}%`;
        } 
        // Check for Distraction
        else if (row.distracted) {
            distractionCount++;
            alertType = "Distraction";
            alertClass = "alert-distraction";
            valString = `Yaw: ${row.yaw.toFixed(1)}°`;
        } else {
            return; // Skip normal rows
        }

        // Append Row to Table
        const tr = `<tr>
            <td>${row.time}</td>
            <td class="${alertClass}">${alertType}</td>
            <td>${valString}</td>
            <td>⚠️ Alert Active</td>
        </tr>`;
        tableBody.innerHTML += tr;
    });

    // Update Top Counters
    document.getElementById("fatigueCount").innerText = fatigueCount;
    document.getElementById("distractionCount").innerText = distractionCount;
}

// Refresh interval: 2 seconds
setInterval(fetchTelemetry, 2000);
fetchTelemetry();