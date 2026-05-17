async function initDashboard() {
    const response = await fetch(`/api/history/${DRIVE_ID}`);
    const data = await response.json();
    
    const labels = data.map(d => d.time);
    const tableBody = document.getElementById('alertLogBody');

    const thresholdLine = (value, n) => Array(n).fill(value);

    const makeChart = (ctx, label, dataset, color, threshold) => new Chart(document.getElementById(ctx), {
        type: 'line',
        data: {
            labels,
            datasets: [
                { label, data: dataset, borderColor: color, tension: 0.2, fill: false, pointRadius: 0 },
                { label: 'Threshold', data: thresholdLine(threshold, labels.length),
                  borderColor: '#e94560', borderDash: [6, 3], borderWidth: 1.5,
                  pointRadius: 0, fill: false }
            ]
        },
        options: { responsive: true, scales: { y: { beginAtZero: false, grid: { color: '#27293d' } } } }
    });

    makeChart('perclosChart', 'PERCLOS Score (%)',   data.map(d => d.perclos), '#4ecca3', THRESHOLDS.perclos);
    makeChart('earChart',     'Eye Aspect Ratio',    data.map(d => d.ear),     '#fca311', THRESHOLDS.ear);
    makeChart('yawChart',     'Head Yaw (°)',        data.map(d => d.yaw),     '#36a2eb', THRESHOLDS.yaw);
    makeChart('pitchChart',   'Head Pitch (°)',      data.map(d => d.pitch),   '#ff6384', THRESHOLDS.pitch);

    data.forEach(d => {
        if (d.distracted || d.perclos > 25) {
            const type = d.perclos > 25 ? "Fatigue / Drowsiness" : "Distraction Alert";
            tableBody.innerHTML += `<tr class="alert-row"><td>${d.time}</td><td>${type}</td><td>CRITICAL</td></tr>`;
        }
    });
}

window.onload = initDashboard;
