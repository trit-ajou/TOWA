import { nextTick, ref } from 'vue'
import { useStore } from 'vuex'
import { useQueryClient } from '@tanstack/vue-query'
import { useFileAdapter } from './useFileAdapter'
import { queryKeys } from './queryKeys'
import { pageBinaryCache } from '@/file-adapter/cache-instances'
import type { PageSummary } from '@/file-adapter'
// @ts-expect-error bitmappery JS module
import DocumentFactory from '@bitmappery/factories/document-factory'
// @ts-expect-error bitmappery JS module
import LayerFactory from '@bitmappery/factories/layer-factory'
// @ts-expect-error bitmappery JS module
import { getCanvasInstance } from '@bitmappery/services/canvas-service'

// page binary cache replaces the legacy `PageCache` singleton; the BlobCache
// instance is now user-namespaced via the cache-db layer.
const pageCache = pageBinaryCache

/** 원본 이미지 세션 캐시. 탭 종료 시 소멸. */
const originalImageCache = new Map<string, Blob>()

/** 페이지 전환 중 플래그 (모든 호출자 공유). overlay 노출 트리거. */
const isPageSwitching = ref(false)

/**
 * bitmappery 캔버스와 FileAdapter(저장소) 사이의 오케스트레이션.
 * - loadPage: 저장소 → bitmappery에 문서 로드
 * - savePage: bitmappery 현재 상태 → 저장소에 snapshot 저장
 * - switchPage: 현재 페이지 저장+캐시 → 해제 → 새 페이지 로드
 */
export function usePageLoader() {
  const store = useStore()
  const fileAdapter = useFileAdapter()
  const qc = useQueryClient()

  /**
   * pageId에 해당하는 페이지를 bitmappery에 로드.
   * 1) 캐시 확인 (메모리 → IDB 캐시)
   * 2) snapshot에서 layerBlob으로 복원, originalImage는 세션 캐시에 보관
   * 3) 원본 이미지에서 새 문서 생성 (fallback)
   */
  async function loadPage(pageId: string): Promise<void> {
    let doc

    // 1) 캐시에서 복원 시도
    const cached = await pageCache.get(pageId)
    if (cached) {
      doc = await DocumentFactory.fromBlob(cached)
    }

    // 2) snapshot에서 복원
    if (!doc) {
      const snapshot = await fileAdapter.getPageSnapshot(pageId)
      if (snapshot) {
        doc = await DocumentFactory.fromBlob(snapshot.layerBlob)
        // 원본 이미지를 세션 캐시에 보관
        originalImageCache.set(pageId, snapshot.originalImage)
      }
    }

    // 3) placeholder fallback
    if (!doc) {
      console.warn(`[PageLoader] No snapshot found for page ${pageId}, using placeholder`)
      const canvas = createPlaceholderCanvas(pageId)

      doc = DocumentFactory.create({
        name: `page-${pageId}`,
        width: canvas.width,
        height: canvas.height,
        layers: [
          LayerFactory.create({
            name: 'original',
            source: canvas,
            width: canvas.width,
            height: canvas.height,
          }),
        ],
      })
    }

    store.commit('bmp/addNewDocument', doc)
    // bitmappery activeDocument watcher가 자동으로 calcIdealDimensions(true)를
    // 호출하여 캔버스 크기를 재계산하므로 별도 트리거 불필요.
    // 이전 코드의 window.dispatchEvent('resize')는 bitmappery.handleResize를 호출하는데,
    // handleResize가 setToolOptionValue(ZOOM, level=1)로 zoom을 강제 reset해서
    // fit-to-window 비율(첫 진입 시 계산된 zoom)이 깨졌음. 페이지 전환마다 캔버스가
    // 가로로 늘어나는 ratio 버그의 원인이었음.
    await nextTick()
  }

  /**
   * bitmappery의 현재 편집 상태를 snapshot으로 저장.
   */
  async function savePage(pageId: string): Promise<void> {
    const doc = store.getters['bmp/activeDocument']
    if (!doc) return

    const layerBlob = await DocumentFactory.toBlob(doc)

    // 썸네일 캡처
    const thumbnail = await captureThumbnail()
    if (!thumbnail) return // 캔버스 없으면 저장 불가

    // originalImage: 세션 캐시에서 가져옴. 없으면 snapshot에서 재조회
    let originalImage = originalImageCache.get(pageId)
    if (!originalImage) {
      const existingSnapshot = await fileAdapter.getPageSnapshot(pageId)
      if (existingSnapshot) {
        originalImage = existingSnapshot.originalImage
        originalImageCache.set(pageId, originalImage)
      }
    }
    if (!originalImage) {
      console.warn(`[PageLoader] No originalImage for page ${pageId}, skipping save`)
      return
    }

    // page metadata 조회: query cache가 PageSummary[]을 갖고 있음.
    const projectId = store.getters['editor/currentProjectId']
    const summaries = qc.getQueryData<PageSummary[]>(queryKeys.pages.byProject(projectId)) ?? []
    const page = summaries.find((p) => p.id === pageId)
    if (!page) return

    await fileAdapter.savePageSnapshot({
      page: {
        id: pageId,
        projectId: page.projectId,
        index: page.index,
        status: page.status,
      },
      originalImage,
      layerBlob,
      thumbnail,
    })

    // Invalidate the page list and the thumbnail binary cache so consumers
    // (PageGrid, sidebars) pick up the new server-side thumbnailUrl/updatedAt.
    // Thumbnail Object URLs are managed by their owning components in Phase 3.
    qc.invalidateQueries({ queryKey: queryKeys.pages.byProject(projectId) })
    qc.invalidateQueries({ queryKey: queryKeys.binary.thumbnail(pageId) })
  }

  /**
   * 현재 bitmappery 캔버스를 캡처하여 썸네일 Blob 반환.
   */
  function captureThumbnail(): Promise<Blob | null> {
    const zCanvas = getCanvasInstance()
    if (!zCanvas) return Promise.resolve(null)
    const canvasEl = zCanvas.getElement() as HTMLCanvasElement
    if (!canvasEl) return Promise.resolve(null)

    const maxW = 200
    const maxH = 300
    const scale = Math.min(maxW / canvasEl.width, maxH / canvasEl.height, 1)
    const w = Math.round(canvasEl.width * scale)
    const h = Math.round(canvasEl.height * scale)

    const thumbCanvas = document.createElement('canvas')
    thumbCanvas.width = w
    thumbCanvas.height = h
    const ctx = thumbCanvas.getContext('2d')!
    ctx.drawImage(canvasEl, 0, 0, w, h)

    return new Promise<Blob | null>((resolve) => {
      thumbCanvas.toBlob((blob) => resolve(blob), 'image/png')
    })
  }

  /**
   * 페이지 전환: 현재 → 새 페이지.
   * 1. 현재 페이지 직렬화 + 캐시 + snapshot 저장
   * 2. bitmappery 문서 해제
   * 3. 새 페이지 로드
   */
  async function switchPage(fromPageId: string | null, toPageId: string): Promise<void> {
    isPageSwitching.value = true
    try {
      // 1. 현재 페이지 캐시. 서버 저장은 호출자(EditorTab 등)가 useAutoSave의
      //    saveImmediately로 switchPage 전에 dirty일 때만 처리.
      let prevDocId: string | null = null
      if (fromPageId) {
        const doc = store.getters['bmp/activeDocument']
        if (doc) {
          prevDocId = doc.id
          const blob = await DocumentFactory.toBlob(doc)
          await pageCache.set(fromPageId, blob)
        }
      }

      // 2. 새 페이지 먼저 로드 → bitmappery가 즉시 새 문서로 전환 (Get Started 깜빡임 없음)
      await loadPage(toPageId)

      // 2b. bitmappery document-canvas watcher의 cache flush + 첫 render 패스 완료까지 yield.
      //     overlay가 이 구간 동안 빈 캔버스를 가려 깜빡임 제거.
      await nextTick()
      await new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
      })

      // 3. 이전 문서를 documents 배열에서 제거 (메모리 정리)
      if (prevDocId) {
        const docs = store.state.bmp?.document?.documents
        if (docs) {
          const idx = docs.findIndex((d: { id: string }) => d.id === prevDocId)
          if (idx !== -1 && idx !== store.state.bmp.document.activeIndex) {
            docs[idx].layers.forEach((layer: { source?: HTMLCanvasElement; mask?: HTMLCanvasElement }) => {
              if (layer.source) { layer.source.width = 0; layer.source = undefined as any }
              if (layer.mask) { layer.mask.width = 0; layer.mask = undefined as any }
            })
            docs.splice(idx, 1)
            // activeIndex 보정
            if (store.state.bmp.document.activeIndex > idx) {
              store.state.bmp.document.activeIndex--
            }
          }
        }
      }
    } finally {
      isPageSwitching.value = false
    }
  }

  return { loadPage, savePage, switchPage, pageCache, isPageSwitching }
}

// --- helpers ---

function createPlaceholderCanvas(pageId: string): HTMLCanvasElement {
  const w = 1000
  const h = 1400
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#2a2a3a'
  ctx.fillRect(0, 0, w, h)
  ctx.fillStyle = '#6a6a8a'
  ctx.font = 'bold 32px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(`No image: ${pageId}`, w / 2, h / 2)
  return canvas
}
