import { canvas as ZCanvas } from 'zcanvas'
import type { Document, Layer } from '@bitmappery/definitions/document'
import { LayerTypes } from '@bitmappery/definitions/layer-types'
// @ts-expect-error bitmappery JS module
import { createRendererForLayer, flushLayerRenderers } from '@bitmappery/factories/renderer-factory'
// @ts-expect-error bitmappery JS module
import { renderEffectsForLayer } from '@bitmappery/services/render-service'
// @ts-expect-error bitmappery JS module
import { createSyncSnapshot } from '@bitmappery/utils/document-util'

const THUMB_MAX_W = 200
const THUMB_MAX_H = 300

/**
 * Render a document that is NOT mounted in the live editor canvas.
 *
 * bitmappery draws (createSyncSnapshot) and renders text/effects
 * (renderEffectsForLayer) through a global renderer cache keyed by layer.id,
 * and only mounted documents have renderers. A detached document therefore
 * renders as a fully transparent canvas — or, because layer ids like
 * `layer_3` repeat across pages, picks up the *active* page's renderers and
 * draws the wrong page. We avoid both by rendering shallow clones whose ids
 * are unique, registering temporary renderers for them, and flushing those
 * renderers afterwards. The original layers are never mutated (text rendering
 * reassigns `layer.source`, which lands on the clone), so the layerBlob the
 * caller serializes stays untouched.
 */
export async function renderDetachedDocument(doc: Document): Promise<HTMLCanvasElement> {
  const nonce = Math.random().toString(36).slice(2, 10)
  const layers: Layer[] = doc.layers.map((layer) => ({ ...layer, id: `bgsnap-${nonce}-${layer.id}` }))
  const clone = { ...doc, layers } as Document

  await loadFontsFor(layers)

  const zcvs = new ZCanvas({
    width: doc.width,
    height: doc.height,
    viewport: { width: doc.width * 10, height: doc.height * 10 },
  })
  try {
    const visible = layers.filter((l) => l.visible)
    for (const layer of visible) {
      createRendererForLayer(zcvs, layer, false)
    }
    for (const layer of visible) {
      await renderEffectsForLayer(layer, false)
    }
    // A font that finished loading during the first pass may have been
    // measured with a fallback face; one more text pass settles it.
    for (const layer of visible) {
      if (layer.type === LayerTypes.LAYER_TEXT) await renderEffectsForLayer(layer, false)
    }
    return createSyncSnapshot(clone) as HTMLCanvasElement
  } finally {
    layers.forEach((layer) => flushLayerRenderers(layer))
    zcvs.dispose()
  }
}

/** Downscale a full-size render to the thumbnail box used everywhere else. */
export function toThumbnailCanvas(composed: HTMLCanvasElement): HTMLCanvasElement {
  const scale = Math.min(THUMB_MAX_W / composed.width, THUMB_MAX_H / composed.height, 1)
  const thumb = document.createElement('canvas')
  thumb.width = Math.max(1, Math.round(composed.width * scale))
  thumb.height = Math.max(1, Math.round(composed.height * scale))
  thumb.getContext('2d')?.drawImage(composed, 0, 0, thumb.width, thumb.height)
  return thumb
}

/**
 * True when every pixel is fully transparent. Used as a last-line guard so a
 * failed offscreen render never overwrites a good server thumbnail.
 */
export function isBlankCanvas(cvs: HTMLCanvasElement): boolean {
  const ctx = cvs.getContext('2d')
  if (!ctx || cvs.width === 0 || cvs.height === 0) return true
  const { data } = ctx.getImageData(0, 0, cvs.width, cvs.height)
  for (let i = 3; i < data.length; i += 4) {
    if (data[i] !== 0) return false
  }
  return true
}

async function loadFontsFor(layers: Layer[]): Promise<void> {
  if (typeof document === 'undefined' || !document.fonts) return
  const specs = new Set<string>()
  for (const layer of layers) {
    if (layer.type !== LayerTypes.LAYER_TEXT) continue
    const { font, size, unit } = (layer.text ?? {}) as { font?: string; size?: number; unit?: string }
    if (font) specs.add(`${size ?? 16}${unit ?? 'px'} "${font}"`)
  }
  await Promise.all(Array.from(specs, (spec) => document.fonts.load(spec).catch(() => undefined)))
}
