export type LayerType = 'original' | 'inpaint' | 'text'

export interface Layer {
  id: string
  pageId: string
  type: LayerType
  name: string
  visible: boolean
  opacity: number
}
