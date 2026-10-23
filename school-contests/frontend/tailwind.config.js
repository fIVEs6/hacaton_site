/** Палитра «бумага и чернила»: тёплый фон, чернильно-синий текст, терракотовый и хвойный акценты. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F4EFE6",
        card: "#FBF8F1",
        sand: "#EBE4D6",
        ink: "#1F2A44",
        soft: "#5A6480",
        rust: "#B5472F",
        pine: "#2F5D50",
        line: "#CFC6B3",
      },
      fontFamily: {
        serif: ['"PT Serif"', "Georgia", "serif"],
        sans: ['"PT Sans"', "system-ui", "sans-serif"],
      },
      borderRadius: { DEFAULT: "2px", md: "3px", lg: "4px" },
    },
  },
  plugins: [],
};
