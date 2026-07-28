import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api to the FastAPI service so the app is same-origin in dev too.
export default defineConfig({
  plugins: [react()],
  build: {
    // AG Grid and Recharts are large and change rarely — keep them in their own
    // chunks so app edits don't invalidate the whole bundle.
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks: {
          aggrid: ["ag-grid-community", "ag-grid-react"],
          charts: ["recharts"],
          vendor: ["react", "react-dom", "react-router-dom", "react-redux", "@reduxjs/toolkit"],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true,
                rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
});
