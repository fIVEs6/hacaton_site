import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// В режиме разработки запросы /api проксируются на backend
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
