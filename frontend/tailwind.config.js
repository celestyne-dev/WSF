/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ivory: {
          DEFAULT: '#FBF7F2',
          50: '#FFFFFF',
          100: '#FBF7F2',
          200: '#F5EEE4',
        },
        cream: '#F3ECE1',
        blush: {
          50: '#FDF4F1',
          100: '#F9E4DD',
          200: '#F0CFC4',
          300: '#E3AFA0',
        },
        rose: {
          400: '#C98A85',
          500: '#B06A63',
          600: '#93504A',
        },
        plum: {
          500: '#5B3A4E',
          600: '#472C3D',
          700: '#33202C',
        },
        burgundy: {
          500: '#7A2438',
          600: '#611B2B',
          700: '#4A1220',
        },
        taupe: {
          100: '#EDE7DE',
          200: '#DCD2C4',
          300: '#BFB1A0',
          400: '#9C8C79',
        },
        charcoal: {
          DEFAULT: '#241F21',
          600: '#3A3335',
          700: '#241F21',
          800: '#171315',
        },
      },
      fontFamily: {
        serif: ['"Fraunces"', '"Playfair Display"', 'Georgia', 'serif'],
        sans: ['"Inter"', '"Helvetica Neue"', 'Arial', 'sans-serif'],
      },
      maxWidth: {
        'content': '1280px',
        'reading': '720px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(36,31,33,0.04), 0 8px 24px rgba(36,31,33,0.06)',
      },
      letterSpacing: {
        widest2: '0.18em',
      },
      transitionDuration: {
        250: '250ms',
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
