/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Trading specific colors
        profit: "#10b981",
        loss: "#ef4444",
        neutral: "#6b7280",
        long: "#10b981", 
        short: "#ef4444",
        pending: "#f59e0b",
        filled: "#10b981",
        cancelled: "#6b7280",
        chart: {
          bullish: "#10b981",
          bearish: "#ef4444",
          neutral: "#6b7280",
          volume: "#8b5cf6",
        },
      },
      keyframes: {
        pulse: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { transform: "translateY(10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
      },
      animation: {
        pulse: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        fadeIn: "fadeIn 0.5s ease-in-out",
        slideUp: "slideUp 0.3s ease-out",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Monaco", "Consolas", "Liberation Mono", "Courier New", "monospace"],
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
        '128': '32rem',
      },
    },
  },
  plugins: [],
} 