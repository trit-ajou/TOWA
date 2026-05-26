import { watch, onUnmounted, onMounted, ref } from 'vue'
import { useStore } from 'vuex'
import { usePageLoader } from './usePageLoader'

const DEBOUNCE_MS = 30_000  // 30초

/**
 * bitmappery history 변화를 감지하여 자동 저장.
 * - 편집 후 30초 동안 추가 편집 없으면 저장
 * - 컴포넌트 해제(페이지 전환 등) 시 즉시 저장
 * - 브라우저 탭 닫기 전 저장 시도
 */
export function useAutoSave() {
  const store = useStore()
  const { savePage } = usePageLoader()

  const dirty = ref(false)
  let saveTimer: ReturnType<typeof setTimeout> | null = null

  function getCurrentPageId(): string | null {
    return store.getters['editor/selectedPageId'] ?? null
  }

  // bitmappery history 변화 감지. bmp/history 모듈의 실제 필드명은 historyIndex.
  const stopWatch = watch(
    () => store.state.bmp?.history?.historyIndex,
    () => {
      dirty.value = true
      if (saveTimer) clearTimeout(saveTimer)
      saveTimer = setTimeout(async () => {
        await doSave()
      }, DEBOUNCE_MS)
    },
  )

  async function doSave(explicitPageId?: string): Promise<void> {
    if (!dirty.value) return
    // 페이지 전환 직전 호출 시 selectedPageId는 이미 새 페이지로 바뀐 상태이므로
    // 호출자가 명시적으로 떠나는 페이지 ID를 넘긴다.
    const pageId = explicitPageId ?? getCurrentPageId()
    if (!pageId) return
    try {
      await savePage(pageId)
      dirty.value = false
    } catch (e) {
      console.error('[AutoSave] Failed:', e)
    }
  }

  async function saveImmediately(explicitPageId?: string): Promise<void> {
    if (saveTimer) {
      clearTimeout(saveTimer)
      saveTimer = null
    }
    await doSave(explicitPageId)
  }

  // 브라우저 닫기 전 저장 시도
  function onBeforeUnload() {
    if (dirty.value) {
      const pageId = getCurrentPageId()
      if (pageId) {
        // 동기적으로는 Blob 직렬화를 못하므로 최선의 노력만
        // (일반적으로 beforeunload에서 async는 보장 안 됨)
        savePage(pageId).catch(() => {})
      }
    }
  }

  onMounted(() => {
    window.addEventListener('beforeunload', onBeforeUnload)
  })

  onUnmounted(() => {
    stopWatch()
    if (saveTimer) clearTimeout(saveTimer)
    window.removeEventListener('beforeunload', onBeforeUnload)
    // 컴포넌트 해제 시 즉시 저장
    doSave()
  })

  return { dirty, saveImmediately }
}
