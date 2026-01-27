/**
 * @fileoverview Chart.js Configuration for Enterprise Theme.
 * Provides consistent styling for all application charts using the new 
 * variable palette defined in enterprise-theme.css.
 */

/**
 * Standard configuration object for Chart.js instances.
 * Ensures responsiveness and theme compliance (fonts, colors, grids).
 * 
 * @type {Object}
 */
const chartConfig = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            labels: {
                color: '#111827', // var(--text-primary)
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
                color: '#6b7280', // var(--neutral-gray)
                font: { 
                    family: 'SF Mono, Fira Code, monospace' 
                } 
            },
            grid: { 
                color: '#e5e7eb' // var(--border-light)
            }
        },
        x: {
            ticks: { 
                color: '#6b7280', // var(--neutral-gray)
                font: { 
                    family: 'SF Mono, Fira Code, monospace' 
                } 
            },
            grid: { 
                color: '#e5e7eb' // var(--border-light)
            }
        }
    }
};