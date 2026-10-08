/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/web/templates/**/*.html"],
  theme: {
    extend: {
      colors: {
        brand: {
          primary: '#2a389b',
          'primary-hover': '#1e2978',
          'primary-light': '#3d4cb8',
          light: '#e5e9eb',
          'light-surface': '#f3f6f8',
          accent: '#79b5b9',
          'accent-light': '#eaf4f5',
          'accent-dark': '#4e8d91',
          warm: '#e8d5b5',
          'warm-light': '#faf6f0',
        }
      }
    },
  },
  plugins: [],
}
