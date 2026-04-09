import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'
import path from 'node:path'
import type { Plugin } from 'vite'

const towaAppSrc = fileURLToPath(new URL('./src', import.meta.url))
const bitmapperySrc = fileURLToPath(new URL('../bitmappery/src', import.meta.url))

/**
 * Resolves @/ imports based on which project the importer belongs to.
 * - Files inside bitmappery/ → @/ resolves to bitmappery/src/
 * - Files inside towa-app/ → @/ resolves to towa-app/src/
 */
function smartAliasResolver(): Plugin {
  return {
    name: 'smart-alias-resolver',
    enforce: 'pre',
    resolveId(source, importer) {
      if (!source.startsWith('@/')) return null

      const targetSrc = importer?.includes('bitmappery') ? bitmapperySrc : towaAppSrc
      const resolved = path.join(targetSrc, source.slice(2))
      return this.resolve(resolved, importer, { skipSelf: true })
    },
  }
}

export default defineConfig({
  plugins: [
    smartAliasResolver(),
    vue(),
    tailwindcss(),
  ],
  test: {
    environment: 'node',
  },
  resolve: {
    alias: {
      // @/ is handled by smartAliasResolver plugin
      '@bitmappery': bitmapperySrc,
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "${bitmapperySrc}/styles/_colors.scss" as *;\n`,
        importers: [{
          findFileUrl(url: string) {
            if (url.startsWith('@/')) {
              // SCSS @use "@/..." in bitmappery files → bitmappery/src/
              return new URL(url.slice(2), new URL('file://' + bitmapperySrc + '/'))
            }
            return null
          }
        }],
      },
    },
  },
  worker: {
    plugins: () => [smartAliasResolver()],
  },
  server: {
    fs: {
      allow: ['..'],  // allow access to bitmappery assets
    },
  },
  define: {
    'global': 'globalThis',
  },
})
