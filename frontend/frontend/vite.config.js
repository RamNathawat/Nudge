import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // allow external access from ngrok
    port: 5173,      // default Vite port
    allowedHosts: [
      'localhost',
      'nudgedemo.loca.lt',
      '3466-103-59-75-40.ngrok-free.app',
      'e2c3-103-59-75-40.ngrok-free.app',
      'https://bc76-103-59-75-40.ngrok-free.app' // <- THIS is the active one you're using
    ]
  }
})