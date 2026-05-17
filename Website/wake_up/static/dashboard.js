async function initDashboard() {
    const response = await fetch(`/api/history/${DRIVE_ID}`);
    const data = await response.json();
    const tableBody = document.getElementById('alertLogBody');

    // Insert interpolated crossing points where the data crosses the threshold.
    // Returns new {labels, values} arrays with extra points at exact crossings.
    function withCrossings(rawLabels, rawValues, threshold) {
        const labels = [], values = [];
        for (let i = 0; i < rawValues.length; i++) {
            // Check if the segment from i-1 to i crosses the threshold
            if (i > 0) {
                const v0 = rawValues[i - 1], v1 = rawValues[i];
                if ((v0 < threshold) !== (v1 < threshold)) {
                    // Linear interpolation: t = fraction along segment where crossing occurs
                    const t = (threshold - v0) / (v1 - v0);
                    // Interpolate the time label (HH:MM:SS strings → seconds → back)
                    const toSec = s => s.split(':').reduce((a, b) => a * 60 + +b, 0);
                    const toStr = s => new Date(s * 1000).toISOString().substr(11, 8);
                    const crossTime = toStr(toSec(rawLabels[i - 1]) + t * (toSec(rawLabels[i]) - toSec(rawLabels[i - 1])));
                    labels.push(crossTime);
                    values.push(threshold);
                }
            }
            labels.push(rawLabels[i]);
            values.push(rawValues[i]);
        }
        return { labels, values };
    }

    const thresholdLine = (value, n) => Array(n).fill(value);

    const makeChart = (ctx, label, rawValues, color, threshold) => {
        const { labels, values } = withCrossings(data.map(d => d.time), rawValues, threshold);
        return new Chart(document.getElementById(ctx), {
            type: 'line',
            data: {
                labels,
                datasets: [
                    { label, data: values, borderColor: color, tension: 0, fill: false, pointRadius: 3, pointHoverRadius: 6, hitRadius: 10 },
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
    };

    makeChart('perclosChart', 'PERCLOS Score (%)', data.map(d => d.perclos), '#5ba4a4', THRESHOLDS.perclos);
    makeChart('earChart',     'Eye Aspect Ratio',  data.map(d => d.ear),     '#e8a838', THRESHOLDS.ear);
    makeChart('yawChart',     'Head Yaw (°)',      data.map(d => d.yaw),     '#7eb8d4', THRESHOLDS.yaw);
    makeChart('pitchChart',   'Head Pitch (°)',    data.map(d => d.pitch),   '#a8c97f', THRESHOLDS.pitch);

    data.forEach(d => {
        if (d.distracted || d.perclos > 25) {
            const type = d.perclos > 25 ? "Fatigue / Drowsiness" : "Distraction Alert";
            tableBody.innerHTML += `<tr class="alert-row"><td>${d.time}</td><td>${type}</td><td>CRITICAL</td></tr>`;
        }
    });
}

window.onload = initDashboard;
