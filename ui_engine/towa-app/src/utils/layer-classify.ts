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
  const group = classifyLayer(layer)
  // 인페인트 결과도 사용자가 일부를 지우거나 수정할 수 있어야 한다 — 모델 결과가 항상
  // 완벽하지 않으므로 후처리가 필요. 원본/텍스트는 여전히 보호 (issue #50)
  return group === 'custom' || group === 'inpaint'
}
