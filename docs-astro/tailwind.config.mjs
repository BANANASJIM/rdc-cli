/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        gpu: {
          dark: 'rgb(var(--bg-base) / <alpha-value>)',
          deeper: 'rgb(var(--bg-deeper) / <alpha-value>)',
          card: 'rgb(var(--bg-surface) / <alpha-value>)',
          'card-hover': 'rgb(var(--bg-surface-hover) / <alpha-value>)',
          border: 'rgb(var(--border) / <alpha-value>)',
          accent: 'rgb(var(--accent) / <alpha-value>)',
          'accent-dim': 'rgb(var(--accent-dim) / <alpha-value>)',
          green: '#00e676',
          purple: '#b388ff',
          orange: '#ff9100',
          pink: '#ff4081',
          cyan: '#18ffff',
        },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
        sans: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
      animation: {
        'glow-pulse': 'glow-pulse 4s ease-in-out infinite',
        'gradient-shift': 'gradient-shift 8s ease infinite',
        'float': 'float 6s ease-in-out infinite',
        'scan': 'scan 4s linear infinite',
      },
      keyframes: {
        'glow-pulse': {
          '0%, 100%': { opacity: '0.4' },
          '50%': { opacity: '1' },
        },
        'gradient-shift': {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        'scan': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
};
