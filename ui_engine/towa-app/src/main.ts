import { Buffer } from 'buffer'
import { createApp } from 'vue'
import FloatingVue, { vTooltip } from 'floating-vue'
import { createI18n } from 'vue-i18n'
import { VueQueryPlugin } from '@tanstack/vue-query'
import App from './App.vue'
import router from './router'
import store from './store'
import { createAppBackend } from './backend'
import { createFileAdapter } from './file-adapter'
import { FILE_ADAPTER_KEY } from './composables/useFileAdapter'
import { APP_BACKEND_KEY } from './composables/useAppBackend'
import { DEPLOYMENT_MODE } from './config/deployment'
import { queryClient, setQueryUser, isAuthError } from './query/query-client'
import { queryKeys } from './composables/queryKeys'
import './app.css'
import 'floating-vue/dist/style.css'

// @ts-expect-error bitmappery i18n messages
import bmpMessages from '@bitmappery/messages.json'

// required for psd.js
globalThis.Buffer = Buffer

// FloatingVue tooltip delay
FloatingVue.options.themes.tooltip.delay.show = 500

// bitmappery i18n
const i18n = createI18n({
  legacy: true,
  messages: bmpMessages,
})

const app = createApp(App)
app.use(router)
app.use(store)
app.use(i18n)
app.use(VueQueryPlugin, { queryClient })
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

// 4) server-state queries are driven by composables (TanStack Query). No
//    legacy module init/dispatch needed; useFileAdapter() still pulls the
//    provided adapter via inject.
void fileAdapter

type AuthSliceShape = { auth?: { user?: { id?: string } } }
function readUserId(): string | null {
  return (store.state as AuthSliceShape).auth?.user?.id ?? null
}

// 5) 세션 복원 → 로그인 상태이면 query/cache user namespace 활성화
async function init() {
  await store.dispatch('auth/restoreFromStorage')
  const isLoggedIn = store.getters['auth/isLoggedIn']
  if (isLoggedIn) {
    const userId = readUserId()
    if (userId) await setQueryUser(userId)
  }

  // 로그인/로그아웃 시점에 cache DB와 query persister를 동기화.
  // setQueryUser는 async지만 mutation handler는 fire-and-forget.
  store.subscribe((mutation, state) => {
    if (mutation.type === 'auth/SET_SESSION') {
      const uid = (state as AuthSliceShape).auth?.user?.id ?? null
      if (uid) {
        setQueryUser(uid).catch((e) => console.warn('[main] setQueryUser failed', e))
      }
    } else if (mutation.type === 'auth/CLEAR_SESSION') {
      setQueryUser(null).catch((e) => console.warn('[main] setQueryUser(null) failed', e))
    }
  })

  // 401 안전망: 어떤 query/mutation이든 인증 만료가 떨어지면 세션을 정리하고
  // 로그인 화면으로 보낸다. (#39 §401 분기)
  let redirectingDueTo401 = false
  function on401() {
    if (redirectingDueTo401) return
    redirectingDueTo401 = true
    setTimeout(() => { redirectingDueTo401 = false }, 1000)
    store.dispatch('auth/logout').catch(() => {})
    if (router.currentRoute.value.name !== 'login') {
      router.replace({ path: '/login', query: { expired: '1' } }).catch(() => {})
    }
  }
  queryClient.getQueryCache().subscribe((event) => {
    if (event.type === 'updated' && event.action.type === 'error') {
      if (isAuthError(event.action.error)) on401()
    }
  })
  queryClient.getMutationCache().subscribe((event) => {
    if (event.type === 'updated' && event.action.type === 'error') {
      if (isAuthError(event.action.error)) on401()
    }
  })

  // Window focus 안전망: 사용자가 다른 탭에서 작업하고 돌아오면 현재 프로젝트의
  // 페이지 목록 메타가 outdated일 수 있음. staleTime: Infinity의 보조 트리거.
  window.addEventListener('focus', () => {
    if (!store.getters['auth/isLoggedIn']) return
    const pid = store.getters['editor/currentProjectId']
    if (pid) {
      queryClient.invalidateQueries({ queryKey: queryKeys.pages.byProject(pid) })
    }
  })

  app.mount('#app')
}
init()
