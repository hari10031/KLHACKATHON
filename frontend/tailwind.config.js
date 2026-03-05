/** @type {import('tailwindcss').Config} */
export default {
    content: ['./index.html', './src/**/*.{js,jsx}'],
    theme: {
        extend: {
            colors: {
                nexus: {
                    50:  '#eefbfa',
                    100: '#d4f4f1',
                    200: '#ade9e4',
                    300: '#78d7cf',
                    400: '#3fbdb4',
                    500: '#14b8a6',
                    600: '#0d9488',
                    700: '#0f766e',
                    800: '#115e59',
                    900: '#134e4a',
                },
                navy: {
                    800: '#0f172a',
                    850: '#0d1424',
                    900: '#080d1a',
                    950: '#04070f',
                },
                risk: {
                    low:      '#22c55e',
                    medium:   '#f59e0b',
                    high:     '#ef4444',
                    critical: '#991b1b',
                },
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
                mono: ['"DM Mono"', '"JetBrains Mono"', 'ui-monospace', 'monospace'],
            },
            backgroundImage: {
                'grid-pattern': 'linear-gradient(rgba(20,184,166,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(20,184,166,0.03) 1px, transparent 1px)',
                'sidebar-gradient': 'linear-gradient(180deg, #0f172a 0%, #080d1a 100%)',
                'header-gradient': 'linear-gradient(135deg, #080d1a 0%, #0f172a 50%, #0d1424 100%)',
                'card-glow': 'radial-gradient(ellipse at top left, rgba(20,184,166,0.06) 0%, transparent 60%)',
            },
            backgroundSize: {
                'grid': '32px 32px',
            },
            boxShadow: {
                'nexus': '0 0 0 1px rgba(20,184,166,0.2), 0 4px 16px -4px rgba(20,184,166,0.15)',
                'nexus-lg': '0 0 0 1px rgba(20,184,166,0.3), 0 8px 32px -8px rgba(20,184,166,0.2)',
                'card': '0 1px 3px rgba(0,0,0,0.05), 0 4px 16px -4px rgba(0,0,0,0.06)',
                'card-hover': '0 4px 24px -4px rgba(0,0,0,0.12), 0 1px 4px rgba(0,0,0,0.06)',
            },
            animation: {
                'pulse-dot': 'pulse-dot 2s ease-in-out infinite',
                'fade-in': 'fadeIn 0.4s ease-out',
                'slide-up': 'slideUp 0.3s ease-out',
                'glow': 'glow 2s ease-in-out infinite',
                'shimmer': 'shimmer 1.5s infinite',
            },
        },
    },
    plugins: [],
}
