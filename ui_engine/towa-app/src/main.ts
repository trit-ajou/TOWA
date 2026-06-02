import { Buffer } from 'buffer'
import { createApp } from 'vue'
import FloatingVue, { vTooltip } from 'floating-vue'
import { createI18n } from 'vue-i18n'
import App from './App.vue'
import router from './router'
import store from './store'
import { createAppBackend } from './backend'
import { createFileAdapter } from './file-adapter'
import { FILE_ADAPTER_KEY } from './composables/useFileAdapter'
import { APP_BACKEND_KEY } from './composables/useAppBackend'
import { DEPLOYMENT_MODE } from './config/deployment'
import './app.css'
import 'floating-vue/dist/style.css'

// bitmappery i18n messages를 글로벌 인스턴스로 통합 등록.
// legacy: false (Composition API mode)에서는 컴포넌트별 `i18n: { messages }` 옵션이
// 동작하지 않으므로 모든 sub-component의 messages.json을 root i18n에 deep merge.
const bmpMessageModules = import.meta.glob<{ default: Record<string, Record<string, unknown>> }>(
  '/src/lib/bitmappery/**/messages.json',
  { eager: true },
)
const mergedMessages: Record<string, Record<string, unknown>> = {}
for (const mod of Object.values(bmpMessageModules)) {
  const payload = mod.default
  for (const [locale, dict] of Object.entries(payload)) {
    mergedMessages[locale] = { ...(mergedMessages[locale] ?? {}), ...dict }
  }
}

// required for psd.js
globalThis.Buffer = Buffer

// FloatingVue tooltip delay
FloatingVue.options.themes.tooltip.delay.show = 500

// bitmappery i18n (Composition API mode + global injection for $t in templates)
const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  messages: mergedMessages,
})

const app = createApp(App)
app.use(router)
app.use(store)
app.use(i18n)
app.directive('tooltip', vTooltip)

// 1) Backend SDK (auth + aiJobs + files) — 모드 무관하게 항상 생성
const backend = createAppBackend()
app.provide(APP_BACKEND_KEY, backend)

// 2) Auth 모듈에 AuthBackend 주입
store.dispatch('auth/init', backend.auth)

// 3) FileAdapter — cloud only for now. Standalone throws (see #37, file-adapter/index.ts).
const mode = DEPLOYMENT_MODE.value
const fileAdapter = createFileAdapter(mode, {
  backend,
  getSessionKey: () => (store.state as { auth?: { sessionKey: string | null } }).auth?.sessionKey ?? null,
})
app.provide(FILE_ADAPTER_KEY, fileAdapter)

// 4) store 모듈에 adapter 주입
store.dispatch('projects/init', fileAdapter)
store.dispatch('pages/init', fileAdapter)
store.dispatch('folders/init', fileAdapter)
store.dispatch('trash/init', fileAdapter)

// 5) 세션 복원 → 로그인 상태이면 프로젝트·폴더 로드
async function init() {
  await store.dispatch('auth/restoreFromStorage')
  const isLoggedIn = store.getters['auth/isLoggedIn']
  if (isLoggedIn) {
    try {
      await Promise.all([
        store.dispatch('projects/loadAll'),
        store.dispatch('folders/loadAll'),
      ])
    } catch (e) {
      // 서버 오류 시 빈 상태로 진입 (UI에서 재시도 안내)
      console.warn('[init] loadAll failed on cloud boot:', e)
    }
  }
  app.mount('#app')
}
init()
