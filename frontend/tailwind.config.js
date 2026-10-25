/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#172554',
        peri: { DEFAULT: '#5269A8', dark: '#435898' },
        lavender: '#B9B8E5',
        misty: '#E9E7F4',
        wash: '#D8D7EF',
        track: '#C9C8E8',
        muted: '#4B5373',
        protected: '#17624A',
        exposed: '#A6402D',
        caution: '#8A6A12',
      },
      fontFamily: {
        serif: ['Newsreader', 'serif'],
        sans: ['"Public Sans"', 'sans-serif'],
      },
      borderRadius: { DEFAULT: '4px' },
      boxShadow: { none: 'none' },
    },
  },
  plugins: [],
};
