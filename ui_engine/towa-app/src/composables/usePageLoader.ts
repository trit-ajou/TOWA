import { nextTick } from 'vue'
import { useStore } from 'vuex'
import { useFileAdapter } from './useFileAdapter'
import { PageCache } from '@/file-adapter/page-cache'
// @ts-expect-error bitmappery JS module
import DocumentFactory from '@bitmappery/factories/document-factory'
// @ts-expect-error bitmappery JS module
import LayerFactory from '@bitmappery/factories/layer-factory'
// @ts-expect-error bitmappery JS module
import { getCanvasInstance } from '@bitmappery/services/canvas-service'

const pageCache = new PageCache()

/**
 * bitmappery 캔버스와 FileAdapter(저장소) 사이의 오케스트레이션.
 * - loadPage: 저장소 → bitmappery에 문서 로드
 * - savePage: bitmappery 현재 상태 → 저장소에 저장
 * - switchPage: 현재 페이지 저장+캐시 → 해제 → 새 페이지 로드
 */
export function usePageLoader() {
  const store = useStore()
  const fileAdapter = useFileAdapter()

  /**
   * pageId에 해당하는 페이지를 bitmappery에 로드.
   * 1) 캐시 확인 (메모리 → IDB 캐시)
   * 2) page-layers (영구 저장 편집 상태) 확인
   * 3) page-images (원본 이미지)에서 새 문서 생성
   */
  async function loadPage(pageId: string): Promise<void> {
    let doc

    // 1) 캐시에서 복원 시도
    const cached = await pageCache.get(pageId)
    if (cached) {
      doc = await DocumentFactory.fromBlob(cached)
    }

    // 2) 영구 저장된 편집 상태에서 복원
    if (!doc) {
      const layerBlob = await fileAdapter.getLayerData(pageId)
      if (layerBlob) {
        doc = await DocumentFactory.fromBlob(layerBlob)
      }
    }

    // 3) 원본 이미지에서 새 문서 생성
    if (!doc) {
      const imageBlob = await fileAdapter.getOriginalImage(pageId)

      let canvas: HTMLCanvasElement
      if (imageBlob) {
        const image = await createImageFromBlob(imageBlob)
        canvas = imageToCanvas(image)
      } else {
        console.warn(`[PageLoader] No image found for page ${pageId}, using placeholder`)
        canvas = createPlaceholderCanvas(pageId)
      }

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
    // 캔버스가 display:none → visible 전환 직후일 수 있으므로 크기 재계산
    await nextTick()
    window.dispatchEvent(new Event('resize'))
  }

  /**
   * bitmappery의 현재 편집 상태를 저장소에 저장.
   * 동시에 캔버스 캡처로 썸네일도 갱신.
   */
  async function savePage(pageId: string): Promise<void> {
    const doc = store.getters['bmp/activeDocument']
    if (!doc) return
    const blob = await DocumentFactory.toBlob(doc)
    await fileAdapter.saveLayerData(pageId, blob)

    // 캔버스 캡처 → 썸네일 갱신
    await updateThumbnail(pageId)
  }

  /**
   * 현재 bitmappery 캔버스를 캡처하여 썸네일 갱신.
   */
  async function updateThumbnail(pageId: string): Promise<void> {
    const zCanvas = getCanvasInstance()
    if (!zCanvas) return
    const canvasEl = zCanvas.getElement() as HTMLCanvasElement
    if (!canvasEl) return

    // 캔버스를 축소하여 썸네일 생성
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

    const thumbBlob = await new Promise<Blob>((resolve) => {
      thumbCanvas.toBlob((blob) => resolve(blob!), 'image/png')
    })

    await fileAdapter.saveThumbnail(pageId, thumbBlob)

    // Vuex store의 페이지 thumbnail Blob URL도 갱신
    const url = URL.createObjectURL(thumbBlob)
    store.commit('pages/SET_THUMBNAIL_URL', { pageId, url })

    // Page 객체의 thumbnail도 갱신 (UI 반영)
    const projectId = store.getters['editor/currentProjectId']
    if (projectId) {
      const page = store.getters['pages/byId'](projectId, pageId)
      if (page) {
        store.commit('pages/UPDATE_PAGE', { ...page, thumbnail: url })
      }
    }
  }

  /**
   * 페이지 전환: 현재 → 새 페이지.
   * 1. 현재 페이지 직렬화 + 캐시 + 저장
   * 2. bitmappery 문서 해제
   * 3. 새 페이지 로드
   */
  async function switchPage(fromPageId: string | null, toPageId: string): Promise<void> {
    // 1. 현재 페이지 저장 + 캐시 + 썸네일 갱신
    let prevDocId: string | null = null
    if (fromPageId) {
      const doc = store.getters['bmp/activeDocument']
      if (doc) {
        prevDocId = doc.id
        // 썸네일 캡처 (savePage가 처리)
        await savePage(fromPageId)
        // 캐시에도 저장
        const blob = await DocumentFactory.toBlob(doc)
        await pageCache.set(fromPageId, blob)
      }
    }

    // 2. 새 페이지 먼저 로드 → bitmappery가 즉시 새 문서로 전환 (Get Started 깜빡임 없음)
    await loadPage(toPageId)

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
  }

  return { loadPage, savePage, switchPage, pageCache }
}

// --- helpers ---

function createImageFromBlob(blob: Blob): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(img.src)
      resolve(img)
    }
    img.onerror = reject
    img.src = URL.createObjectURL(blob)
  })
}

function imageToCanvas(img: HTMLImageElement): HTMLCanvasElement {
  const canvas = document.createElement('canvas')
  canvas.width = img.width
  canvas.height = img.height
  const ctx = canvas.getContext('2d')!
  ctx.drawImage(img, 0, 0)
  return canvas
}

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
