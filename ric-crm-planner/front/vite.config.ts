import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;

          if (id.includes("gantt-task-react") || id.includes("react-kanban-kit")) {
            return "planner-vendor";
          }

          if (
            id.includes("react") ||
            id.includes("react-dom") ||
            id.includes("react-router-dom") ||
            id.includes("scheduler") ||
            id.includes("antd") ||
            id.includes("@ant-design") ||
            id.includes("rc-") ||
            id.includes("@rc-component")
          ) {
            return "ui-vendor";
          }

          return "vendor";
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, '/api'),
      },
      '/parser/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: false,
        secure: false,
        rewrite: (path) => path.replace(/^\/parser\/api/, '/api'),
      },
    },
  },
})
