/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#02040a",
        card: "#0d0d0d",
        "card-hover": "#141416",
        border: "rgba(255, 255, 255, 0.06)",
        "border-hover": "rgba(255, 255, 255, 0.12)",
        accent: "#f59e0b",
        "accent-glow": "rgba(245, 158, 11, 0.3)",
        success: "#10b981",
        warning: "#f43f5e",
        info: "#06b6d4",
        terminal: "#4ade80",
        muted: "#64748b",
      },
      borderRadius: {
        card: "20px",
      },
    },
  },
};
