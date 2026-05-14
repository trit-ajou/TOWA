import type { PageSnapshot } from '@/file-adapter'
import { createUlid } from '@/utils/ulid'
// @ts-expect-error bitmappery JS module
import DocumentFactory from '@bitmappery/factories/document-factory'
// @ts-expect-error bitmappery JS module
import LayerFactory from '@bitmappery/factories/layer-factory'

function generateThumbnail(file: File, maxW = 200, maxH = 300): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const scale = Math.min(maxW / img.width, maxH / img.height, 1)
      const w = Math.round(img.width * scale)
      const h = Math.round(img.height * scale)
      const canvas = document.createElement('canvas')
      canvas.width = w
      canvas.height = h
      const ctx = canvas.getContext('2d')!
      ctx.drawImage(img, 0, 0, w, h)
      canvas.toBlob((blob) => {
        if (blob) resolve(blob)
        else reject(new Error('thumbnail blob creation failed'))
      }, 'image/png')
      URL.revokeObjectURL(img.src)
    }
    img.onerror = reject
    img.src = URL.createObjectURL(file)
  })
}

function blobToCanvas(blob: Blob): Promise<HTMLCanvasElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = img.width
      canvas.height = img.height
      const ctx = canvas.getContext('2d')!
      ctx.drawImage(img, 0, 0)
      URL.revokeObjectURL(img.src)
      resolve(canvas)
    }
    img.onerror = reject
    img.src = URL.createObjectURL(blob)
  })
}

export async function buildPageSnapshotFromFile(
  file: File,
  projectId: string,
  pageIndex: number,
): Promise<PageSnapshot> {
  const pageId = createUlid()
  const originalImage = file as Blob
  const thumbnail = await generateThumbnail(file)
  const imgCanvas = await blobToCanvas(file)
  const doc = DocumentFactory.create({
    name: `page-${pageId}`,
    width: imgCanvas.width,
    height: imgCanvas.height,
    layers: [
      LayerFactory.create({
        name: 'original',
        source: imgCanvas,
        width: imgCanvas.width,
        height: imgCanvas.height,
      }),
    ],
  })
  const layerBlob = (await DocumentFactory.toBlob(doc)) as Blob

  return {
    page: {
      id: pageId,
      projectId,
      index: pageIndex,
      status: 'waiting',
    },
    originalImage,
    layerBlob,
    thumbnail,
  }
}
