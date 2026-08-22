import type { Config } from "tailwindcss";

/**
 * Centralized design tokens — every color/spacing/motion value is a CSS custom
 * property defined once in src/styles/tokens.css. Tailwind maps semantic names
 * onto those variables. Never scatter raw hex values through components.
 */
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "var(--rf-ink-950)", // canvas
          900: "var(--rf-ink-900)", // surface
          850: "var(--rf-ink-850)", // raised surface
          800: "var(--rf-ink-800)", // hover surface
        },
        line: {
          DEFAULT: "var(--rf-line)", // hairline border
          strong: "var(--rf-line-strong)",
        },
        txt: {
          primary: "var(--rf-text-primary)",
          secondary: "var(--rf-text-secondary)",
          muted: "var(--rf-text-muted)",
          inverse: "var(--rf-text-inverse)",
        },
        gold: {
          DEFAULT: "var(--rf-gold)", // the one signal accent
          soft: "var(--rf-gold-soft)",
        },
        pass: "var(--rf-pass)",
        warn: "var(--rf-warn)",
        fail: "var(--rf-fail)",
        info: "var(--rf-info)",
      },
      fontFamily: {
        sans: ["var(--rf-font-sans)"],
        mono: ["var(--rf-font-mono)"],
      },
      borderRadius: {
        DEFAULT: "var(--rf-radius)",
        lg: "var(--rf-radius-lg)",
      },
      boxShadow: {
        card: "var(--rf-shadow-card)",
        pop: "var(--rf-shadow-pop)",
      },
      transitionDuration: {
        DEFAULT: "var(--rf-dur-fast)",
        slow: "var(--rf-dur-slow)",
      },
    },
  },
  plugins: [],
};

export default config;
