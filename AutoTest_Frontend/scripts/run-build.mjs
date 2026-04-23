import vue from '@vitejs/plugin-vue'
import { build } from 'vite'

await build({
  configFile: false,
  plugins: [vue()],
  resolve: {
    preserveSymlinks: true,
  },
  esbuild: false,
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'element-plus': ['element-plus'],
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'http-vendor': ['axios'],
        },
      },
    },
  },
})
