export type ProjectStatus = 'todo' | 'in-progress' | 'done'

export interface ProjectConfig {
  autoDetect: boolean
  autoInpaint: boolean
  autoTranslate: boolean
  inferenceMode: 'local' | 'cloud'
}

export interface Project {
  id: string
  name: string
  thumbnail?: string
  sourceLang: string
  targetLang: string
  pageCount: number
  createdAt: string
  updatedAt: string
  status: ProjectStatus
  folder: string
  config: ProjectConfig
}
