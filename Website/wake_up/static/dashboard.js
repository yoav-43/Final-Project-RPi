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
                { label, data: dataset, borderColor: color, tension: 0.2, fill: false, pointRadius: 3, pointHoverRadius: 6, hitRadius: 10 },
                { label: 'Threshold', data: thresholdLine(threshold, labels.length),
                  borderColor: '#ff0000', borderDash: [6, 3], borderWidth: 1.5,
                  pointRadius: 0, hitRadius: 0, fill: false }
            ]
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            scales: { y: { beginAtZero: false, grid: { color: '#27293d' } } }
        }
    });

    makeChart('perclosChart', 'PERCLOS Score (%)',   data.map(d => d.perclos), '#5ba4a4', THRESHOLDS.perclos);
    makeChart('earChart',     'Eye Aspect Ratio',    data.map(d => d.ear),     '#e8a838', THRESHOLDS.ear);
    makeChart('yawChart',     'Head Yaw (°)',        data.map(d => d.yaw),     '#7eb8d4', THRESHOLDS.yaw);
    makeChart('pitchChart',   'Head Pitch (°)',      data.map(d => d.pitch),   '#a8c97f', THRESHOLDS.pitch);

    data.forEach(d => {
        if (d.distracted || d.perclos > 25) {
            const type = d.perclos > 25 ? "Fatigue / Drowsiness" : "Distraction Alert";
            tableBody.innerHTML += `<tr class="alert-row"><td>${d.time}</td><td>${type}</td><td>CRITICAL</td></tr>`;
        }
    });
}

window.onload = initDashboard;
