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
        name: "oddlot - AI 台股零股選股",
        short_name: "oddlot",
        description: "AI 驅動的台股零股投資參考平台",
        theme_color: "#2563eb",
        background_color: "#f9fafb",
        display: "standalone",
        scope: "/oddlot/",
        start_url: "/oddlot/",
        icons: [
          {
            src: "/oddlot/icon.svg",
            sizes: "any",
            type: "image/svg+xml",
            purpose: "any maskable",
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
