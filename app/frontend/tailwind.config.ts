import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#f7f4ec",
        wash: "#efebe2",
        ink: "#191915",
        muted: "#706d66",
        line: "#ded9cf",
        mustard: "#e8bc4a",
        "mustard-dark": "#8c6413",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        soft: "0 12px 36px -28px rgba(24, 23, 20, 0.45)",
      },
    },
  },
  plugins: [],
};

export default config;
