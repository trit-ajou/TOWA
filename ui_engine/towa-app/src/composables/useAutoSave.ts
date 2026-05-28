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
  // 마지막으로 dirty 처리된 페이지 ID. 라우터 이동으로 selectedPageId가 reset된 뒤
  // onUnmounted가 돌면 selectedPageId가 null이라 저장이 누락된다. markDirty 시점에
  // 떠나는 페이지를 잡아두고 fallback으로 쓴다.
  let lastDirtyPageId: string | null = null
  let saveTimer: ReturnType<typeof setTimeout> | null = null

  function getCurrentPageId(): string | null {
    return store.state.editor?.selectedPageId ?? null
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
    // 우선순위: 명시 인자 > 현재 selectedPageId > 마지막 dirty 시 잡아둔 ID.
    // 마지막 옵션은 EditorTab unmount(라우터 이동) 시 selectedPageId가 reset된 케이스용.
    const pageId = explicitPageId ?? getCurrentPageId() ?? lastDirtyPageId
    if (!pageId) return
    try {
      await savePage(pageId)
      dirty.value = false
      lastDirtyPageId = null
    } catch (e) {
      console.error('[AutoSave] Failed:', e)
    }
  }

  // bmp/updateLayer/addLayer/removeLayer 같은 mutation은 bitmappery history에 기록되지
  // 않으므로 historyIndex watch가 못 잡는다. UI에서 layer를 직접 수정한 호출 지점에서
  // 이 함수를 호출해 dirty 플래그를 명시적으로 세팅하고 debounce 타이머를 (재)시작한다.
  function markDirty(): void {
    dirty.value = true
    lastDirtyPageId = getCurrentPageId() ?? lastDirtyPageId
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(async () => {
      await doSave()
    }, DEBOUNCE_MS)
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

  return { dirty, saveImmediately, markDirty }
}
