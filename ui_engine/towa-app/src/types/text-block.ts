export type TextBlockStatus = 'detected' | 'translated' | 'edited'
export type TextBoxMode = 'fixed' | 'auto'

export interface LayerTextMeta {
  blockId: string
  original: string
  status: TextBlockStatus
  /**
   * 'fixed': TOWA 텍스트 layer. layer.left/top/width/height를 매 렌더마다 보존.
   *          (render-service.ts 분기에서 replaceLayerSource 우회)
   * 'auto'/undefined: native bitmappery 동작. layer를 텍스트 bbox 크기로 축소 + 중앙 보정.
   */
  boxMode?: TextBoxMode
}
