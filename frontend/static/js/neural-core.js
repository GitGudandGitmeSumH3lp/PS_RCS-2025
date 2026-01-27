/**
 * Global configuration for Chart.js instances.
 * 
 * Sets the default theme to match the Enterprise SaaS aesthetic:
 * - Font: SF Mono / Fira Code (Monospace)
 * - Text Color: Dark Gray / Slate
 * - Grid Lines: Light Gray
 */
const chartConfig = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            labels: {
                color: '#111827',
                font: { 
                    family: 'SF Mono, Fira Code, monospace', 
                    size: 11 
                }
            }
        }
    },
    scales: {
        y: {
            beginAtZero: true,
            ticks: { 
                color: '#6b7280', 
                font: { family: 'SF Mono, Fira Code, monospace' } 
            },
            grid: { color: '#e5e7eb' }
        },
        x: {
            ticks: { 
                color: '#6b7280', 
                font: { family: 'SF Mono, Fira Code, monospace' } 
            },
            grid: { color: '#e5e7eb' }
        }
    }
};