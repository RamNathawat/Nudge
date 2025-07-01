// vite.config.js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy requests that start with '/memory' to your backend
      // Adjust this if your API endpoints have a different common prefix
      '/memory': {
        target: 'http://127.0.0.1:8000', // Your backend server address
        changeOrigin: true, // Needed for CORS to work correctly
        secure: false, // Set to true if your backend uses HTTPS
      },
      // If you have other API endpoints (e.g., /auth, /chat), add them here:
      '/auth': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
      '/chat': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
      // Add any other specific backend endpoints here if they don't fall under a common prefix
    }
  }
});