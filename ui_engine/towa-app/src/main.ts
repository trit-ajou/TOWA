import { Buffer } from 'buffer'
import { createApp } from 'vue'
import FloatingVue, { vTooltip } from 'floating-vue'
import { createI18n } from 'vue-i18n'
import App from './App.vue'
import router from './router'
import store from './store'
import { createFileAdapter } from './file-adapter'
import { FILE_ADAPTER_KEY } from './composables/useFileAdapter'
import { seedDummyDataIfEmpty } from './data/dummy'
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
app.directive('tooltip', vTooltip)

// FileAdapter 초기화 + IndexedDB 연동
const fileAdapter = createFileAdapter()
app.provide(FILE_ADAPTER_KEY, fileAdapter)

// store 모듈에 adapter 주입 (동기적으로 즉시 실행 — Promise지만 실제로는 즉시 resolve)
store.dispatch('projects/init', fileAdapter)
store.dispatch('pages/init', fileAdapter)

// 앱을 먼저 마운트 (bitmappery 캔버스 초기화가 DOM에 의존)
app.mount('#app')

// 마운트 후 비동기로 데이터 로드
async function initFileSystem() {
  await seedDummyDataIfEmpty(fileAdapter)
  await store.dispatch('projects/loadAll')
}
initFileSystem()
