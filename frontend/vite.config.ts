import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Le frontend ne connaît que /api : en développement, Vite transmet
// vers le backend Flask (127.0.0.1:5000). Aucun token ni secret ici.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5000",
        changeOrigin: false,
      },
    },
  },
  preview: {
    port: 5173,
    strictPort: true,
  },
});
