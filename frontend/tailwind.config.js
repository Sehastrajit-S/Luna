/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        luna: {
          bg:      'rgb(var(--luna-bg) / <alpha-value>)',
          surface: 'rgb(var(--luna-surface) / <alpha-value>)',
          card:    'rgb(var(--luna-card) / <alpha-value>)',
          border:  'rgb(var(--luna-border) / <alpha-value>)',
          primary: 'rgb(var(--luna-primary) / <alpha-value>)',
          glow:    'rgb(var(--luna-glow) / <alpha-value>)',
          accent:  'rgb(var(--luna-accent) / <alpha-value>)',
          muted:   'rgb(var(--luna-muted) / <alpha-value>)',
          text:    'rgb(var(--luna-text) / <alpha-value>)',
          dim:     'rgb(var(--luna-dim) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'bounce-dots': 'bounceDots 1.4s ease-in-out infinite',
        'scan-line': 'scan-line 0.9s linear forwards',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        bounceDots: {
          '0%, 80%, 100%': { transform: 'scale(0)' },
          '40%': { transform: 'scale(1)' },
        },
        'scan-line': {
          '0%':   { top: '0%',   opacity: '1' },
          '100%': { top: '100%', opacity: '0' },
        },
      },
      boxShadow: {
        'luna':    '0 0 40px rgb(var(--luna-primary) / 0.15)',
        'luna-lg': '0 0 80px rgb(var(--luna-primary) / 0.2)',
        'glow':    '0 0 20px rgb(var(--luna-primary) / 0.4)',
      },
    },
  },
  plugins: [],
}
