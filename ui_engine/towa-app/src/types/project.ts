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
  /** FK → folders.id. null = 루트. (See issue #33 spec.) */
  folderId: string | null
  /** Derived path string for display, e.g. "주간연재/점프". Computed on read. */
  folderPath?: string | null
  /** Soft delete timestamp; null = active, ISO string = in trash. */
  deletedAt: string | null
  config: ProjectConfig
}
