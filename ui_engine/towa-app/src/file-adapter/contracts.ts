import type { ProjectRecord } from './db'
import type { PageStatus } from '@/types/page'

export type ExportFormat = 'png' | 'jpeg' | 'webp' | 'psd'

// --- Snapshot-oriented types (aligned with service_engine page snapshot spec) ---

/** Lightweight page entry for project view lists. */
export interface PageSummary {
  id: string
  projectId: string
  index: number
  status: PageStatus
  /** Private service URL (bearer required) for cloud; undefined for local. */
  thumbnailUrl?: string | null
  updatedAt: string
}

/** Page metadata part of a snapshot (mirrors service `metadata.page`). */
export interface PageSnapshotMeta {
  id: string
  projectId: string
  index: number
  status: PageStatus
}

/**
 * Full page snapshot: metadata + three binary blobs.
 * This is the authoritative unit of edit/save for both local and cloud.
 */
export interface PageSnapshot {
  page: PageSnapshotMeta
  originalImage: Blob
  layerBlob: Blob
  thumbnail: Blob
}

/**
 * Snapshot-oriented FileAdapter interface.
 * Page writes are full-replace multipart snapshots matching the service_engine spec.
 */
export interface FileAdapter {
  // Project CRUD
  listProjects(): Promise<ProjectRecord[]>
  getProject(id: string): Promise<ProjectRecord | undefined>
  createProject(project: ProjectRecord): Promise<ProjectRecord>
  updateProject(id: string, patch: Partial<ProjectRecord>): Promise<ProjectRecord>
  deleteProject(id: string): Promise<void>

  // Pages (summary list)
  listPageSummaries(projectId: string): Promise<PageSummary[]>

  // Pages (full snapshot, append-only create + full replace save)
  getPageSnapshot(pageId: string): Promise<PageSnapshot | undefined>
  createPage(projectId: string, snapshot: PageSnapshot): Promise<PageSummary>
  savePageSnapshot(snapshot: PageSnapshot): Promise<PageSummary>
  deletePage(pageId: string): Promise<void>

  // Thumbnail blob (bearer-aware path in cloud)
  getThumbnailBlob(pageId: string): Promise<Blob | undefined>
}
