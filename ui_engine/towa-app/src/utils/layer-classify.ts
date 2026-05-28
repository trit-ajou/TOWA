// 레이어를 4개 프리셋 그룹(원본/인페인트/텍스트/커스텀)으로 분류.
// LayerPanel의 그룹 표시 + paint guard의 "그림 가능 여부" 판정에 공통 사용.
import type { Layer } from '@bitmappery/definitions/document'
import { LayerTypes } from '@bitmappery/definitions/layer-types'

export type LayerGroupId = 'custom' | 'text' | 'inpaint' | 'original'

export function classifyLayer(layer: Layer): LayerGroupId {
  const role = (layer.meta as { role?: string } | undefined)?.role
  if (role === 'original' || layer.name === 'original') return 'original'
  if (role === 'inpaint') return 'inpaint'
  if (layer.type === LayerTypes.LAYER_TEXT) return 'text'
  return 'custom'
}

export function isPaintableLayer(layer: Layer | null | undefined): boolean {
  if (!layer) return false
  return classifyLayer(layer) === 'custom'
}
