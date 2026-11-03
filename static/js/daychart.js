// static/js/daychart.js
function renderDayChart(dayData) {
    console.log("Rendering chart with data:", dayData);
    const canvas = document.getElementById('dayChart');
    if (!canvas) {
        console.error("Canvas element 'dayChart' not found!");
        return;
    }

    try {
        const history = dayData.history;
        if (!history || history.length === 0) {
            console.error("No history data provided.");
            return;
        }

        const hours = history.map(h => h.hour);
        const tOut = history.map(h => h.t_out);
        const tIn = history.map(h => h.t_in);
        const solar = history.map(h => h.solar_gain_w);
        const loss = history.map(h => h.heat_loss_w);

        const ctx = canvas.getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: hours,
                datasets: [
                    {
                        label: 'Indoor Temp (°C)',
                        data: tIn,
                        borderColor: '#38bdf8',
                        backgroundColor: 'rgba(56, 189, 248, 0.1)',
                        tension: 0.3,
                        fill: true,
                        pointRadius: 0,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Outdoor Temp (°C)',
                        data: tOut,
                        borderColor: '#f97316',
                        borderDash: [5, 5],
                        tension: 0.3,
                        fill: false,
                        pointRadius: 0,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Solar Gain (W)',
                        data: solar,
                        borderColor: '#22c55e',
                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                        tension: 0.3,
                        fill: true,
                        pointRadius: 0,
                        yAxisID: 'y1'
                    },
                    {
                        label: 'Heat Loss (W)',
                        data: loss,
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.05)',
                        tension: 0.3,
                        fill: false,
                        pointRadius: 0,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { labels: { color: '#e2e8f0', font: { size: 11 } } }
                },
                scales: {
                    x: {
                        title: { display: true, text: 'Hour of Day', color: '#94a3b8' },
                        ticks: { color: '#94a3b8', stepSize: 2 }
                    },
                    y: {
                        type: 'linear',
                        position: 'left',
                        title: { display: true, text: 'Temperature (°C)', color: '#94a3b8' },
                        ticks: { color: '#94a3b8' },
                        grid: { color: 'rgba(148, 163, 184, 0.1)' }
                    },
                    y1: {
                        type: 'linear',
                        position: 'right',
                        title: { display: true, text: 'Power (Watts)', color: '#94a3b8' },
                        ticks: { color: '#94a3b8' },
                        grid: { drawOnChartArea: false }
                    }
                }
            }
        });
        console.log("Chart rendered successfully!");
    } catch (e) {
        console.error("Chart rendering error:", e);
    }
}

// Wait for the page to load completely
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM loaded, looking for dayData...");
    const el = document.getElementById('dayData');
    if (el) {
        try {
            console.log("Raw JSON:", el.textContent);
            const data = JSON.parse(el.textContent);
            console.log("Parsed data:", data);
            renderDayChart(data);
        } catch (e) {
            console.error("Failed to parse dayData JSON:", e);
            // Show a fallback message on the page
            const container = document.getElementById('dayChart');
            if (container) {
                container.style.display = 'none';
                const fallback = document.createElement('p');
                fallback.textContent = '⚠️ Could not load chart data. Please check console for errors.';
                fallback.style.color = '#ef4444';
                document.querySelector('.card').appendChild(fallback);
            }
        }
    } else {
        console.warn("dayData element not found.");
    }
});