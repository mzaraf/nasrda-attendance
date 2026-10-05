import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "NASRDA Attendance", short_name: "NASRDA", display: "standalone",
        background_color: "#0b2a4a", theme_color: "#0b2a4a", start_url: "/",
        icons: [
          { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
        ],
      },
      // No API caching: attendance must never work offline (spec §55).
      workbox: { navigateFallback: "/index.html", runtimeCaching: [] },
    }),
  ],
// server: { proxy: { "/api": "http://localhost:8000" } },
server: {
    host: "0.0.0.0",

    allowedHosts: [
      ".ngrok-free.app",
    ],

    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});