import type { ProjectRecord, FolderRecord } from './db'
import type { PageStatus } from '@/types/page'

/** Delete mode for a folder. Aligned with service_engine query params. */
export type DeleteFolderMode = 'empty' | 'cascade-trash' | 'reparent'

/** Trash entry (mirrors service_engine TrashItemResponse). */
export type TrashEntry =
  | { type: 'folder'; item: FolderRecord }
  | { type: 'project'; item: ProjectRecord }

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
  // --- Project CRUD (active items only; deleted_at IS NULL) ---
  listProjects(): Promise<ProjectRecord[]>
  getProject(id: string): Promise<ProjectRecord | undefined>
  createProject(project: ProjectRecord): Promise<ProjectRecord>
  updateProject(id: string, patch: Partial<ProjectRecord>): Promise<ProjectRecord>
  /** Soft delete (move to trash). */
  deleteProject(id: string): Promise<void>
  /** Restore from trash. */
  restoreProject(id: string): Promise<ProjectRecord>
  /** Permanently delete a trashed project (irreversible). */
  permanentlyDeleteProject(id: string): Promise<void>

  // --- Folder CRUD (active items only) ---
  listFolders(params?: { search?: string }): Promise<FolderRecord[]>
  createFolder(input: { name: string; parentId: string | null }): Promise<FolderRecord>
  /** Rename or move. */
  updateFolder(id: string, patch: { name?: string; parentId?: string | null }): Promise<FolderRecord>
  /** Soft delete. Mode controls behavior when folder is non-empty. */
  deleteFolder(id: string, mode: DeleteFolderMode): Promise<void>
  restoreFolder(id: string): Promise<FolderRecord>
  permanentlyDeleteFolder(id: string): Promise<void>

  // --- Trash ---
  listTrash(): Promise<TrashEntry[]>

  // --- Pages (summary list) ---
  listPageSummaries(projectId: string): Promise<PageSummary[]>

  // --- Pages (full snapshot) ---
  getPageSnapshot(pageId: string): Promise<PageSnapshot | undefined>
  createPage(projectId: string, snapshot: PageSnapshot): Promise<PageSummary>
  savePageSnapshot(snapshot: PageSnapshot): Promise<PageSummary>
  deletePage(pageId: string): Promise<void>

  // --- Thumbnail blob ---
  getThumbnailBlob(pageId: string): Promise<Blob | undefined>
}
