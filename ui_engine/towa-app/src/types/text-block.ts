export type TextBlockStatus = 'detected' | 'translated' | 'edited'

export interface LayerTextMeta {
  blockId: string
  original: string
  status: TextBlockStatus
}
