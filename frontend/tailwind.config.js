/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',

    // Ou se estiver usando o diretório `src`:
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'licitai-bg-light': '#F0F5F9',
        'licitai-primary': '#003366',
        'licitai-secondary': '#005588',
        'licitai-visual-bg': '#D1F2EB',
        'licitai-visual-blob-light': '#C0EEDD',
        'licitai-visual-blob-dark': '#A0E0C0',
        'licitai-blue-primary': '#202cff',
        'licitai-blue-accent': '#6fd2e4',
      },
    },
  },
  plugins: [],
}
