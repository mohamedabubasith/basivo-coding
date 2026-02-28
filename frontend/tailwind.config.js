/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // IDE dark theme palette
        surface: {
          DEFAULT: "#0f1117",
          50: "#1a1d27",
          100: "#16192240",
          200: "#1e2130",
          300: "#252836",
          400: "#2d3144",
        },
        brand: {
          DEFAULT: "#6366f1",
          50: "#eef2ff",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
        },
        success: "#22c55e",
        warning: "#f59e0b",
        danger: "#ef4444",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "Cascadia Code", "Consolas", "monospace"],
      },
      animation: {
        "fade-in": "fadeIn 0.15s ease-out",
        "slide-up": "slideUp 0.2s ease-out",
        "pulse-dot": "pulseDot 2s infinite",
      },
      keyframes: {
        fadeIn: { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp: { from: { opacity: 0, transform: "translateY(8px)" }, to: { opacity: 1, transform: "translateY(0)" } },
        pulseDot: { "0%,100%": { opacity: 1 }, "50%": { opacity: 0.3 } },
      },
    },
  },
  plugins: [],
};
