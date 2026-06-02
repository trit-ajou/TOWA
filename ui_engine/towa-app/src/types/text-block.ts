export type TextBlockStatus = 'detected' | 'translated' | 'edited'
export type TextBoxMode = 'fixed' | 'auto'
export type WritingMode = 'horizontal' | 'vertical'
/** [[x, y], [x, y], ...] — detect가 잡아준 텍스트 영역의 실제 윤곽. */
export type TextPolygon = Array<[number, number]>

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
  // detect 응답에서 받은 메타. translate 요청 본문에 그대로 다시 실어 보내야
  // model-engine이 동일 geometry/컨텍스트로 번역만 수행한다 (TRANSLATE_REST_CONTRACT).
  polygon?: TextPolygon
  readingOrder?: number
  writingMode?: WritingMode
  sourceRegionRef?: string
}
