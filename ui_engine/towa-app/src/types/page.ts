import type { TextBlock } from './text-block'

export type PageStatus = 'waiting' | 'ai-processing' | 'in-progress' | 'done'

export interface Page {
  id: string
  projectId: string
  index: number
  originalImage?: string
  thumbnail?: string
  status: PageStatus
  textBlocks: TextBlock[]
}
