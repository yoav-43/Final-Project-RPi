// Global Chart Object
let fatigueChart;

// Function to fetch data from the server
async function fetchTelemetry() {
    try {
        const response = await fetch('/api/history');
        if (!response.ok) throw new Error("Network response was not ok");
        
        const data = await response.json();
        updateChart(data);
    } catch (error) {
        console.error("Error fetching data:", error);
    }
}

// Function to initialize and update the chart
function updateChart(data) {
    const ctx = document.getElementById('fatigueChart').getContext('2d');
    
    // Extract arrays for X-axis (Time) and Y-axis (Values)
    const labels = data.map(entry => entry.time);
    const perclosValues = data.map(entry => entry.perclos);
    const marValues = data.map(entry => entry.mar);

    if (!fatigueChart) {
        // Create Chart for the first time
        fatigueChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Fatigue Level (PERCLOS %)',
                        data: perclosValues,
                        borderColor: 'rgb(255, 99, 132)', // Red
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        fill: true,
                        tension: 0.3,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Yawning (MAR)',
                        data: marValues,
                        borderColor: 'rgb(54, 162, 235)', // Blue
                        backgroundColor: 'rgba(54, 162, 235, 0.1)',
                        borderDash: [5, 5], // Dashed line
                        tension: 0.3,
                        yAxisID: 'y1' // Use a separate axis if scaling is different
                    }
                ]
            },
            options: {
                responsive: true,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        beginAtZero: true,
                        max: 100, // PERCLOS is 0-100%
                        title: { display: true, text: 'Fatigue (%)' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        beginAtZero: true,
                        suggestedMax: 1.0, // MAR is usually 0.0 - 1.0
                        grid: { drawOnChartArea: false }, // Don't show grid lines for this axis
                        title: { display: true, text: 'Mouth Openness (Ratio)' }
                    }
                },
                animation: { duration: 0 } // Disable animation for smoother realtime updates
            }
        });
    } else {
        // Update existing chart data without re-creating the object
        fatigueChart.data.labels = labels;
        fatigueChart.data.datasets[0].data = perclosValues;
        fatigueChart.data.datasets[1].data = marValues;
        fatigueChart.update();
    }
}

// Refresh data every 2 seconds
setInterval(fetchTelemetry, 2000);

// Initial load
fetchTelemetry();