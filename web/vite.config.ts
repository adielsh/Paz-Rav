import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: proxy API + WebSocket to the FastAPI backend on :8000.
// Build: emits to web/dist, which the backend serves in production.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
