/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        knight: { bg: '#0a0a14', surface: '#12121c', border: '#1e1e2e', cyan: '#22d3ee', purple: '#a855f7', orange: '#f97316', yellow: '#facc15', text: '#e2e8f0', muted: '#64748b' }
      }
    }
  },
  plugins: [],
};
