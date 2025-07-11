import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // This tells Vite to forward any request that starts with /auth
      // to your backend server running on http://localhost:8000
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // You can add other backend routes here if needed
      // For example, if you have /chat, /memory, etc. at the root
      '/chat': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/debug_nemo_mind': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/online_search': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/deep_research': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/memory': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
       '/traits': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
       '/reset-memory': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
       '/reset-traits': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
       '/safe-space-mode': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    }
  }
})
