import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],

    // Base path for production - served at /ui/
    base: '/ui/',

    // Development server proxy to backend API
    server: {
        port: 5173,
        proxy: {
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/auth': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/health': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
        },
    },

    // Resolve aliases for cleaner imports
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },

    // Build configuration
    build: {
        outDir: 'dist',
        emptyOutDir: true,
        sourcemap: false,
    },
})
