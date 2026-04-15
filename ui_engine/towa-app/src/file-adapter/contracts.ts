import type { ProjectRecord, PageRecord } from './db'

export type ExportFormat = 'png' | 'jpeg' | 'webp' | 'psd'

export interface FileAdapter {
  // --- Project CRUD ---
  listProjects(): Promise<ProjectRecord[]>
  getProject(id: string): Promise<ProjectRecord | undefined>
  saveProject(project: ProjectRecord): Promise<void>
  deleteProject(id: string): Promise<void>

  // --- Page CRUD ---
  listPages(projectId: string): Promise<PageRecord[]>
  getPage(pageId: string): Promise<PageRecord | undefined>
  savePage(page: PageRecord): Promise<void>
  deletePage(pageId: string): Promise<void>
  deletePagesByProject(projectId: string): Promise<void>

  // --- Original images (Blob) ---
  getOriginalImage(pageId: string): Promise<Blob | undefined>
  saveOriginalImage(pageId: string, blob: Blob): Promise<void>

  // --- Thumbnails (Blob) ---
  getThumbnail(pageId: string): Promise<Blob | undefined>
  saveThumbnail(pageId: string, blob: Blob): Promise<void>

  // --- bitmappery layer data (Blob from DocumentFactory.toBlob()) ---
  getLayerData(pageId: string): Promise<Blob | undefined>
  saveLayerData(pageId: string, blob: Blob): Promise<void>
}
