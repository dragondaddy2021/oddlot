import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.ico"],
      manifest: {
        name: "龍爹地的零股投資學習平台",
        short_name: "零股學習",
        description: "AI 篩選 + 你掌控的自組 ETF — 台股零股長期投資學習平台",
        theme_color: "#2563eb",
        background_color: "#f9fafb",
        display: "standalone",
        scope: "/oddlot/",
        start_url: "/oddlot/",
        icons: [
          {
            src: "/oddlot/icon-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "/oddlot/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
          {
            src: "/oddlot/icon.svg",
            sizes: "any",
            type: "image/svg+xml",
          },
        ],
      },
    }),
  ],
  base: process.env.NODE_ENV === "production" ? "/oddlot/" : "/",
  // Load .env from the project root (parent of frontend/) instead of frontend/
  envDir: "..",
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
