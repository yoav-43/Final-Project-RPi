// Asynchronous function to fetch data
async function fetchFatigueData() {
    try {
        // Call the API built in Flask (GET route)
        const response = await fetch('/api/data');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        return data; // Returns an array of data
 
    } catch (error) {
        console.error("Could not fetch data:", error);
        return []; // Return empty array on error
    }
}
 
// Function to draw the chart
function createChart(data) {
    // Get the element from HTML
    const ctx = document.getElementById('fatigueChart').getContext('2d');
    
    // Process data for Chart.js
    // 1. Time axis (X)
    const labels = data.map(item => 
        new Date(item.timestamp).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' })
    );
    // 2. Data axis (Y)
    const fatigueLevels = data.map(item => item.fatigue);
 
    // Create the chart
    new Chart(ctx, {
        type: 'line', // Chart type (Line chart)
        data: {
            labels: labels,
            datasets: [{
                label: 'Fatigue Level (0-1)',
                data: fatigueLevels,
                borderColor: 'rgb(255, 99, 132)',
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                fill: true,
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    suggestedMax: 1.0 // Set Y axis from 0 to 1
                }
            }
        }
    });
}
 
// Initialize process when page loads
async function initDashboard() {
    const data = await fetchFatigueData();
    if (data.length > 0) {
        createChart(data);
    } else {
        console.log("No data to display.");
        // Can display a message to the user if no data
    }
}
 
// Call the main function
initDashboard();