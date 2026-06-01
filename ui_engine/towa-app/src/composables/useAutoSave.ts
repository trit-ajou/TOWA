import { watch, onUnmounted, onMounted, ref } from 'vue'
import { useStore } from 'vuex'
import { usePageLoader } from './usePageLoader'
// @ts-expect-error bitmappery JS module
import { getRendererForLayer } from '@bitmappery/factories/renderer-factory'

const DEBOUNCE_MS = 30_000  // 30초 — #39 Phase 0 결정: 5초보다 무거운 페이지
                            // binary 직렬화/업로드 부담을 줄이고 page-switch
                            // 즉시 저장 안전망이 있어 catastrophic loss 한도가
                            // 30초로 제한됨. (운영 후 필요하면 줄임)

// dirty 상태는 module-scope singleton — UI 뱃지가 어디 mount되든 (사이드패널,
// 홈 그리드, 라이브러리) 같은 정보를 구독할 수 있어야 한다. dirtyPageId는
// "지금 어떤 페이지에 미저장 변경분이 있는가"를 표시하기 위한 좌표.
const dirty = ref(false)
const dirtyPageId = ref<string | null>(null)

/** UI(뱃지 등)에서 미저장 상태를 구독하기 위한 read-only 핸들. */
export function useDirtyState() {
  return { dirty, dirtyPageId }
}

/**
 * bitmappery history 변화를 감지하여 자동 저장. (#39 §저장 모델)
 * - 편집 후 debounce 30초 (auto)
 * - Ctrl/Cmd+S 즉시 저장 (수동) — bitmappery의 Save Document 모달은 차단됨
 * - 컴포넌트 해제(페이지 전환 등) 시 즉시 저장
 * - 브라우저 탭 닫기 전 저장 시도
 * - dirty 페이지는 PageSidePanelItem / PageThumbnail 좌상단 뱃지로 표시
 */
export function useAutoSave() {
  const store = useStore()
  const { savePage } = usePageLoader()

  let saveTimer: ReturnType<typeof setTimeout> | null = null

  function getCurrentPageId(): string | null {
    return store.state.editor?.selectedPageId ?? null
  }

  // dirty 플래그 세팅 + debounce 타이머 (재)시작 + 현재 페이지 ID capture.
  // dirtyPageId 캡처는 라우터 이동으로 selectedPageId가 reset된 후 onUnmounted가
  // 돌면 doSave가 pageId=null로 bail out하는 케이스를 막기 위함이기도 하고,
  // UI 뱃지가 어떤 페이지에 미저장 변경분이 있는지 가리키는 좌표가 되기도 한다.
  function flagDirty(): void {
    dirty.value = true
    dirtyPageId.value = getCurrentPageId() ?? dirtyPageId.value
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(async () => {
      await doSave()
    }, DEBOUNCE_MS)
  }

  // bitmappery history 변화 감지. bmp/history 모듈의 실제 필드명은 historyIndex.
  // 상세 편집 탭의 브러시/지우개 등 bitmappery history API를 거치는 편집을 잡는다.
  const stopWatch = watch(
    () => store.state.bmp?.history?.historyIndex,
    () => flagDirty(),
  )

  // bitmappery는 brush/eraser stroke 끝(handleRelease) 직후 storePaintState를
  // 1초 debounce로 호출한다. canvasToBlob × 2가 async라 historyIndex 증가
  // (=flagDirty 트리거) 가 1초+ 지연됨. 사용자가 그 사이 페이지를 이동하거나
  // Ctrl+S를 누르면 doSave가 dirty=false를 보고 bail → 자동저장 누락.
  // bitmappery 자신도 undo action 진입 직전에 동일한 flush를 한다
  // (history-module.ts의 undo action 참고).
  async function flushPendingPaint(): Promise<void> {
    const layer = store.getters['bmp/activeLayer']
    if (!layer) return
    const renderer = getRendererForLayer(layer)
    if (renderer?.storePaintState) {
      try { await renderer.storePaintState() } catch { /* best-effort */ }
    }
  }

  async function doSave(explicitPageId?: string): Promise<void> {
    // brush의 pending paint state를 먼저 commit해야 historyIndex가 최신이 되고
    // dirty.value가 올바르게 반영됨. 페인트 없는 상태에서는 즉시 no-op.
    await flushPendingPaint()

    if (!dirty.value) return
    // 우선순위: 명시 인자 > 현재 selectedPageId > 마지막 dirty 시 잡아둔 ID.
    // 마지막 옵션은 EditorTab unmount(라우터 이동) 시 selectedPageId가 reset된 케이스용.
    const pageId = explicitPageId ?? getCurrentPageId() ?? dirtyPageId.value
    if (!pageId) return
    try {
      await savePage(pageId)
      dirty.value = false
      dirtyPageId.value = null
    } catch (e) {
      console.error('[AutoSave] Failed:', e)
    }
  }

  // bmp/updateLayer/addLayer/removeLayer 같은 mutation은 bitmappery history에 기록되지
  // 않으므로 historyIndex watch가 못 잡는다. UI에서 layer를 직접 수정한 호출 지점에서
  // 이 함수를 호출해 dirty 플래그를 명시적으로 세팅한다.
  function markDirty(): void {
    flagDirty()
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

  // Ctrl/Cmd+S 수동 저장. capture phase로 등록해 bitmappery의 keyboard-service
  // 보다 먼저 이벤트를 잡고 stopPropagation으로 차단한다. (bitmappery 측 핸들러
  // 자체는 #39 phase 5에서 무력화되어 있지만 capture phase가 명시적으로 안전.)
  function onKeydownCapture(e: KeyboardEvent) {
    const isSaveCombo = (e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')
    if (!isSaveCombo) return
    e.preventDefault()
    e.stopPropagation()
    void saveImmediately()
  }

  onMounted(() => {
    window.addEventListener('beforeunload', onBeforeUnload)
    window.addEventListener('keydown', onKeydownCapture, { capture: true })
  })

  onUnmounted(() => {
    stopWatch()
    if (saveTimer) clearTimeout(saveTimer)
    window.removeEventListener('beforeunload', onBeforeUnload)
    window.removeEventListener('keydown', onKeydownCapture, { capture: true })
    // 컴포넌트 해제 시 즉시 저장
    doSave()
  })

  return { dirty, saveImmediately, markDirty }
}
