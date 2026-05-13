import type { Layer } from '@bitmappery/definitions/document'
import { LayerTypes } from '@bitmappery/definitions/layer-types'
import type { LayerTextMeta, TextBlockStatus } from '@/types/text-block'

export function isTextLayer(layer: Layer): boolean {
  return layer.type === LayerTypes.LAYER_TEXT
}

export function getTextMeta(layer: Layer): LayerTextMeta | null {
  const meta = layer.meta as Partial<LayerTextMeta> | undefined
  if (!meta || typeof meta.blockId !== 'string') return null
  return {
    blockId: meta.blockId,
    original: typeof meta.original === 'string' ? meta.original : '',
    status: (meta.status as TextBlockStatus) ?? 'detected',
  }
}

export function mergeTextMeta(layer: Layer, patch: Partial<LayerTextMeta>): Record<string, unknown> {
  return { ...(layer.meta ?? {}), ...patch }
}
