import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

const towaAppSrc = fileURLToPath(new URL('./src', import.meta.url))
const bitmapperySrc = fileURLToPath(new URL('./src/lib/bitmappery/src', import.meta.url))

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
  ],
  test: {
    environment: 'node',
  },
  resolve: {
    alias: {
      '@': towaAppSrc,
      '@bitmappery': bitmapperySrc,
    },
  },
  optimizeDeps: {
    include: ['lz-string'],
  },
  css: {
    preprocessorOptions: {
      scss: {
        // sass 모듈은 vite resolve.alias를 알지 못하므로 importer로 직접 매핑.
        importers: [{
          findFileUrl(url: string) {
            if (url.startsWith('@bitmappery/')) {
              return new URL(url.slice('@bitmappery/'.length), new URL('file://' + bitmapperySrc + '/'))
            }
            return null
          }
        }],
      },
    },
  },
  server: (() => {
    const publicHost = process.env.VITE_PUBLIC_HOST
    return {
      host: '0.0.0.0',
      port: 5173,
      ...(publicHost
        ? {
            allowedHosts: [publicHost, `.${publicHost}`],
            hmr: {
              host: publicHost,
              clientPort: 443,
              protocol: 'wss',
            },
          }
        : {}),
    }
  })(),
  define: {
    'global': 'globalThis',
  },
})
