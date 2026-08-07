import type { Config } from "tailwindcss";

const config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          0: "var(--ink-0)",
          1: "var(--ink-1)",
          2: "var(--ink-2)",
          3: "var(--ink-3)",
          4: "var(--ink-4)",
        },
        surface: {
          chrome: "var(--surface-chrome)",
          content: "var(--surface-content)",
        },
        line: {
          DEFAULT: "var(--line)",
          2: "var(--line-2)",
        },
        text: {
          DEFAULT: "var(--text)",
          2: "var(--text-2)",
          3: "var(--text-3)",
          4: "var(--text-4)",
        },
        brand: "var(--brand)",
        amber: "var(--brand)",
        green: "var(--green)",
        blue: "var(--blue)",
        yellow: "var(--yellow)",
        warn: "var(--warn)",
        red: "var(--red)",
        violet: "var(--violet)",
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["Hanken Grotesk", "PingFang SC", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "SF Mono", "Menlo", "monospace"],
        display: ["Bricolage Grotesque", "Hanken Grotesk", "PingFang SC", "system-ui", "sans-serif"],
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "tracesurface-spin": {
          to: { transform: "rotate(360deg)" },
        },
      },
      animation: {
        "fade-up": "fade-up .18s ease-out both",
        "tracesurface-spin": "tracesurface-spin 24s linear infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;

export default config;
