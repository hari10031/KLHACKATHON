/** @type {import('tailwindcss').Config} */
export default {
    content: ['./index.html', './src/**/*.{js,jsx}'],
    theme: {
        extend: {
            colors: {
                gst: {
                    50: '#eff6ff',
                    100: '#dbeafe',
                    500: '#3b82f6',
                    600: '#2563eb',
                    700: '#1d4ed8',
                    900: '#1e3a5f',
                },
                risk: {
                    low: '#22c55e',
                    medium: '#f59e0b',
                    high: '#ef4444',
                    critical: '#991b1b',
                },
            },
        },
    },
    plugins: [],
}
