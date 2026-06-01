import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'
import path from 'node:path'
import type { Plugin } from 'vite'

const towaAppEntry = fileURLToPath(new URL('./src/main.ts', import.meta.url))
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

/**
 * bitmappery 소스는 towa-app 루트 바깥에 있으므로, bare import를 기본 Node
 * 알고리즘에 맡기면 `towa-app/node_modules`를 찾지 못한다.
 * bitmappery 내부 bare import는 towa-app 엔트리 기준으로 다시 해석해
 * 실행 주체인 towa-app의 node_modules를 authoritative source로 고정한다.
 */
function bitmapperyBareImportResolver(): Plugin {
  return {
    name: 'bitmappery-bare-import-resolver',
    enforce: 'pre',
    resolveId(source, importer) {
      if (!importer?.includes(`${path.sep}bitmappery${path.sep}`)) return null
      if (
        source.startsWith('.') ||
        source.startsWith('/') ||
        source.startsWith('@/') ||
        source.startsWith('@bitmappery')
      ) {
        return null
      }

      return this.resolve(source, towaAppEntry, { skipSelf: true })
    },
  }
}

export default defineConfig({
  plugins: [
    bitmapperyBareImportResolver(),
    smartAliasResolver(),
    vue(),
    tailwindcss(),
  ],
  test: {
    environment: 'node',
    // Playwright e2e specs live in ./e2e/ and use Playwright's `test` API,
    // which collides with vitest's. Exclude them from vitest.
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
  },
  resolve: {
    alias: {
      // @/ is handled by smartAliasResolver plugin
      '@bitmappery': bitmapperySrc,
    },
  },
  optimizeDeps: {
    include: ['lz-string'],
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
    plugins: () => [bitmapperyBareImportResolver(), smartAliasResolver()],
  },
  server: (() => {
    const publicHost = process.env.VITE_PUBLIC_HOST
    return {
      host: '0.0.0.0',
      port: 5173,
      fs: {
        allow: ['..'],  // allow access to bitmappery assets
      },
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
