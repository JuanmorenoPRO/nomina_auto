import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, /api se redirige al backend FastAPI (evita CORS).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174, // 5173 suele estar ocupado por otra app en esta máquina
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8001", // 8000 suele estar ocupado en esta máquina

        changeOrigin: true,
        rewrite: (ruta) => ruta.replace(/^\/api/, ""),
      },
    },
  },
});
