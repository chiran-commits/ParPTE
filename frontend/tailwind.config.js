/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#17201C", soft: "#4A5550", mute: "#7A847F" },
        paper: { DEFAULT: "#F6F7F5", raised: "#FFFFFF", sunk: "#ECEEEA" },
        line: "#DCE0DB",
        pine: { DEFAULT: "#0F5C4A", deep: "#0A4134", tint: "#E3EFEA" },
        marigold: { DEFAULT: "#E9A20C", tint: "#FBF0D6" },
        coral: { DEFAULT: "#C8432F", tint: "#F8E3DF" },
        ok: { DEFAULT: "#1E8A5A", tint: "#DFF1E7" },
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', "system-ui", "sans-serif"],
        body: ['"Atkinson Hyperlegible"', "system-ui", "sans-serif"],
      },
      borderRadius: { panel: "10px" },
    },
  },
  plugins: [],
};
