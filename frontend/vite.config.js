import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "dist",
  },
  // server: {
  //   host: "0.0.0.0",
  //   // hosts: true,
  //   port: 5173,
  //   strictPort: true,
  //   watch: {
  //     usePolling: true,
  //   },
  //   proxy: {
  //     "/api": {
  //       target: "http://backend:8000",
  //       changeOrigin: true,
  //     },
  //   },
  // },
});
