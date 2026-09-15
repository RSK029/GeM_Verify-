import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Mirrors the "@/*" path mapping in tsconfig.json.
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: { port: 5173, strictPort: true },
  // pdfjs ships an ESM worker; let Vite pre-bundle it rather than resolving at runtime.
  optimizeDeps: { include: ['react-pdf'] },
  build: { outDir: 'dist', sourcemap: false },
})
