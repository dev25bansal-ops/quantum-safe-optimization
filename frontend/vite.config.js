import { defineConfig } from "vite";
import { resolve } from "path";

export default defineConfig({
  root: ".",
  publicDir: "assets",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    minify: "terser",
    sourcemap: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        dashboard: resolve(__dirname, "dashboard.html"),
        simple: resolve(__dirname, "simple.html"),
      },
      output: {
        entryFileNames: "js/[name].[hash].js",
        chunkFileNames: "js/chunks/[name].[hash].js",
        assetFileNames: "assets/[name].[hash].[ext]",
        manualChunks(id) {
          const normalizedId = id.replace(/\\/g, "/");
          if (normalizedId.includes("/node_modules/chart.js/")) {
            return "vendor";
          }
          if (
            normalizedId.endsWith("/js/modules/utils.js") ||
            normalizedId.endsWith("/js/modules/api.js")
          ) {
            return "utils";
          }
          return undefined;
        },
      },
    },
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
    },
    target: "es2020",
    cssCodeSplit: true,
  },
  server: {
    port: 3000,
    open: true,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "js"),
      "@modules": resolve(__dirname, "js/modules"),
      "@components": resolve(__dirname, "js/components"),
    },
  },
  css: {
    devSourcemap: true,
  },
  optimizeDeps: {
    include: ["chart.js"],
  },
  test: {
    environment: "jsdom",
  },
  plugins: [],
});
