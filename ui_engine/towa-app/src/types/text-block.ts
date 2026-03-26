export type TextBlockStatus = 'detected' | 'translated' | 'edited'

export interface BBox {
  x: number
  y: number
  width: number
  height: number
}

export interface TextBlock {
  id: string
  pageId: string
  bbox: BBox
  original: string
  translated: string
  font: string
  fontSize: number
  color: string
  status: TextBlockStatus
}
