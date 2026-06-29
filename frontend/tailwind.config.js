/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Dark header / app chrome
        ink: {
          DEFAULT: '#0B0E14',
          800: '#11151F',
          700: '#1B2130',
          600: '#2A3242',
        },
        // Indigo accent
        accent: {
          50: '#EEEFFE',
          100: '#E0E1FD',
          200: '#C4C6FB',
          300: '#A1A4F7',
          400: '#7F83F3',
          500: '#5B5FEF',
          600: '#4A4ED6',
          700: '#3D40B0',
        },
        // Back-compat alias so any lingering `brand-*` classes still resolve to indigo.
        brand: {
          50: '#EEEFFE',
          100: '#E0E1FD',
          400: '#7F83F3',
          500: '#5B5FEF',
          600: '#4A4ED6',
          700: '#3D40B0',
          900: '#3D40B0',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      borderRadius: {
        card: '12px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(11, 14, 20, 0.04), 0 4px 12px rgba(11, 14, 20, 0.06)',
      },
    },
  },
  plugins: [],
}
