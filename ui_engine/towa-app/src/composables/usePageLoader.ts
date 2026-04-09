import { useStore } from 'vuex'
import { useFileAdapter } from './useFileAdapter'
import { PageCache } from '@/file-adapter/page-cache'
// @ts-expect-error bitmappery JS module
import DocumentFactory from '@bitmappery/factories/document-factory'
// @ts-expect-error bitmappery JS module
import LayerFactory from '@bitmappery/factories/layer-factory'

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
    // 1) 캐시에서 복원 시도
    const cached = await pageCache.get(pageId)
    if (cached) {
      const doc = await DocumentFactory.fromBlob(cached)
      store.commit('bmp/addNewDocument', doc)
      return
    }

    // 2) 영구 저장된 편집 상태에서 복원
    const layerBlob = await fileAdapter.getLayerData(pageId)
    if (layerBlob) {
      const doc = await DocumentFactory.fromBlob(layerBlob)
      store.commit('bmp/addNewDocument', doc)
      return
    }

    // 3) 원본 이미지에서 새 문서 생성
    const imageBlob = await fileAdapter.getOriginalImage(pageId)
    if (!imageBlob) {
      console.warn(`[PageLoader] No image found for page ${pageId}`)
      return
    }

    const image = await createImageFromBlob(imageBlob)
    const canvas = imageToCanvas(image)

    const doc = DocumentFactory.create({
      name: `page-${pageId}`,
      width: image.width,
      height: image.height,
      layers: [
        LayerFactory.create({
          name: 'original',
          source: canvas,
          width: image.width,
          height: image.height,
        }),
      ],
    })
    store.commit('bmp/addNewDocument', doc)
  }

  /**
   * bitmappery의 현재 편집 상태를 저장소에 저장.
   */
  async function savePage(pageId: string): Promise<void> {
    const doc = store.getters['bmp/activeDocument']
    if (!doc) return
    const blob = await DocumentFactory.toBlob(doc)
    await fileAdapter.saveLayerData(pageId, blob)
  }

  /**
   * 페이지 전환: 현재 → 새 페이지.
   * 1. 현재 페이지 직렬화 + 캐시 + 저장
   * 2. bitmappery 문서 해제
   * 3. 새 페이지 로드
   */
  async function switchPage(fromPageId: string | null, toPageId: string): Promise<void> {
    // 1. 현재 페이지 저장 + 캐시
    if (fromPageId) {
      const doc = store.getters['bmp/activeDocument']
      if (doc) {
        const blob = await DocumentFactory.toBlob(doc)
        await pageCache.set(fromPageId, blob)
        await fileAdapter.saveLayerData(fromPageId, blob)
      }
      // 2. 문서 해제
      store.commit('bmp/closeActiveDocument')
    }

    // 3. 새 페이지 로드
    await loadPage(toPageId)
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
