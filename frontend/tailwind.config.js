/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          primary: 'var(--brand-primary)',
          coral: 'var(--brand-coral)',
          ink: 'var(--brand-ink)',
          sand: 'var(--brand-sand)',
          sage: 'var(--brand-sage)',
          cloud: 'var(--brand-cloud)',
          mist: 'var(--brand-mist)',
        },
      },
      fontFamily: {
        display: ['Fraunces', 'Georgia', 'serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        brand: '12px',
        'brand-lg': '16px',
      },
      spacing: {
        block: '32px',
      },
      transitionDuration: {
        fast: '200ms',
        normal: '300ms',
      },
      transitionTimingFunction: {
        brand: 'var(--ease-brand)',
      },
    },
  },
  plugins: [],
};
