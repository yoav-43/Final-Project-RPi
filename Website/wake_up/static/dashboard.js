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

    const makeChart = (ctx, label, rawValues, color, threshold, condition, yLabel) => {
        const { labels, values } = withCrossings(data.map(d => d.time), rawValues, threshold);
        return new Chart(document.getElementById(ctx), {
            type: 'line',
            data: {
                labels,
                datasets: [
                    { label, data: values, borderColor: color, tension: 0, fill: false, pointRadius: 3, pointHoverRadius: 6 },
                    { label: `Threshold (${condition})`, data: thresholdLine(threshold, labels.length),
                      borderColor: '#ff0000', borderDash: [6, 3], borderWidth: 1.5,
                      pointRadius: 0, hitRadius: 0, fill: false }
                ]
            },
            options: {
                responsive: true,
                scales: {
                    x: { title: { display: true, text: 'Time', color: '#aaa' }, grid: { color: '#27293d' }, ticks: { color: '#aaa' } },
                    y: { title: { display: true, text: yLabel, color: '#aaa' }, beginAtZero: false, grid: { color: '#27293d' }, ticks: { color: '#aaa' } }
                }
            }
        });
    };

    // Yaw needs two threshold lines (±) so it gets its own chart builder.
    const makeYawChart = (ctx, rawValues, color, threshold) => {
        const labels = data.map(d => d.time);
        return new Chart(document.getElementById(ctx), {
            type: 'line',
            data: {
                labels,
                datasets: [
                    { label: 'Head Yaw (°) — near 0 is better ✅ | outside thresholds = DISTRACTED ⚠️', data: rawValues, borderColor: color, tension: 0, fill: false, pointRadius: 3, pointHoverRadius: 6 },
                    { label: `+${threshold}° threshold`, data: thresholdLine(threshold, labels.length),
                      borderColor: '#ff0000', borderDash: [6, 3], borderWidth: 1.5, pointRadius: 0, hitRadius: 0, fill: false },
                    { label: `-${threshold}° threshold`, data: thresholdLine(-threshold, labels.length),
                      borderColor: '#ff0000', borderDash: [6, 3], borderWidth: 1.5, pointRadius: 0, hitRadius: 0, fill: false }
                ]
            },
            options: {
                responsive: true,
                scales: {
                    x: { title: { display: true, text: 'Time', color: '#aaa' }, grid: { color: '#27293d' }, ticks: { color: '#aaa' } },
                    y: { title: { display: true, text: 'Yaw (°)', color: '#aaa' }, beginAtZero: false, grid: { color: '#27293d' }, ticks: { color: '#aaa' } }
                }
            }
        });
    };

    makeChart('perclosChart', 'PERCLOS Score (%) — lower is better ✅ | above threshold = FATIGUE ⚠️', data.map(d => d.perclos), '#5ba4a4', THRESHOLDS.perclos, `> ${THRESHOLDS.perclos}% = Fatigue`,  'PERCLOS (%)');
    makeChart('earChart',     'Eye Aspect Ratio — higher is better ✅ | below threshold = EYES CLOSED ⚠️',  data.map(d => d.ear),     '#e8a838', THRESHOLDS.ear,     `< ${THRESHOLDS.ear} = Eyes Closed`,  'EAR');
    makeYawChart('yawChart', data.map(d => d.yaw), '#7eb8d4', THRESHOLDS.yaw);
    makeChart('pitchChart',   'Head Pitch (°) — near 0 is better ✅ | below threshold = HEAD DOWN ⚠️',    data.map(d => d.pitch),   '#a8c97f', THRESHOLDS.pitch,   `< ${THRESHOLDS.pitch}° = Head Down`, 'Pitch (°)');

    data.forEach(d => {
        if (d.distracted || d.perclos > 25) {
            const type = d.perclos > 25 ? "Fatigue / Drowsiness" : "Distraction Alert";
            tableBody.innerHTML += `<tr class="alert-row"><td>${d.time}</td><td>${type}</td><td>CRITICAL</td></tr>`;
        }
    });

    // Load GPS route
    const gpsRes = await fetch(`/api/gps/${DRIVE_ID}`);
    const gps = await gpsRes.json();
    const map = L.map('map');
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    if (gps.length > 0) {
        const coords = gps.map(p => [p.lat, p.lon]);
        L.polyline(coords, { color: '#5ba4a4', weight: 3 }).addTo(map);
        L.marker(coords[0]).bindPopup('Start').addTo(map);
        L.marker(coords[coords.length - 1]).bindPopup('End').addTo(map);
        map.fitBounds(coords);
    } else {
        map.setView([0, 0], 2);
        L.popup().setLatLng([0, 0]).setContent('No GPS data for this session.').openOn(map);
    }
}

window.onload = initDashboard;
