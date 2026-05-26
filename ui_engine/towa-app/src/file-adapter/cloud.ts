import type {
  AppBackend,
  FolderDto,
  PageSnapshotPayload,
  PageSummaryDto,
  ProjectCreateInput,
  ProjectDto,
  ProjectPatchInput,
  TrashEntryDto,
} from '@/backend/contracts'
import { BackendError } from '@/backend/errors'
import type { PageStatus } from '@/types/page'
import type { ProjectConfig, ProjectStatus } from '@/types/project'

import type { DeleteFolderMode, FileAdapter, PageSnapshot, PageSummary, TrashEntry } from './contracts'
import type { FolderRecord, ProjectRecord } from './db'

export type SessionKeyProvider = () => string | null

/**
 * Cloud-backed FileAdapter. Delegates all persistence to `backend.files.*`
 * (service_engine REST API). Session key is resolved on each call via the
 * injected provider (typically reading from the Vuex auth module).
 *
 * Errors from the SDK (e.g. `session_key_required`, `project_not_found`) are
 * propagated as-is (`BackendError`). Call sites decide whether to trigger a
 * re-login flow, show a toast, etc.
 */
export class CloudFileAdapter implements FileAdapter {
  constructor(
    private backend: AppBackend,
    private getSessionKey: SessionKeyProvider,
  ) {}

  // --- helpers ---

  private authOpts() {
    return { sessionKey: this.getSessionKey() ?? undefined }
  }

  // --- Project CRUD ---

  async listProjects(): Promise<ProjectRecord[]> {
    const items = await this.backend.files.listProjects(this.authOpts())
    return items.map(toProjectRecord)
  }

  async getProject(id: string): Promise<ProjectRecord | undefined> {
    try {
      const dto = await this.backend.files.getProject(id, this.authOpts())
      return toProjectRecord(dto)
    } catch (e) {
      if (isNotFound(e)) return undefined
      throw e
    }
  }

  async createProject(project: ProjectRecord): Promise<ProjectRecord> {
    const input: ProjectCreateInput = {
      id: project.id,
      name: project.name,
      sourceLang: project.sourceLang,
      targetLang: project.targetLang,
      status: project.status,
      folderId: project.folderId,
      config: project.config as unknown as Record<string, unknown>,
      thumbnailUrl: project.thumbnailUrl ?? null,
    }
    const dto = await this.backend.files.createProject(input, this.authOpts())
    return toProjectRecord(dto)
  }

  async updateProject(id: string, patch: Partial<ProjectRecord>): Promise<ProjectRecord> {
    const body: ProjectPatchInput = {}
    if (patch.name !== undefined) body.name = patch.name
    if (patch.thumbnailUrl !== undefined) body.thumbnailUrl = patch.thumbnailUrl
    if (patch.sourceLang !== undefined) body.sourceLang = patch.sourceLang
    if (patch.targetLang !== undefined) body.targetLang = patch.targetLang
    if (patch.status !== undefined) body.status = patch.status
    if (patch.folderId !== undefined) body.folderId = patch.folderId
    if (patch.config !== undefined) body.config = patch.config as unknown as Record<string, unknown>
    const dto = await this.backend.files.updateProject(id, body, this.authOpts())
    return toProjectRecord(dto)
  }

  async deleteProject(id: string): Promise<void> {
    await this.backend.files.deleteProject(id, this.authOpts())
  }

  async restoreProject(id: string): Promise<ProjectRecord> {
    const dto = await this.backend.files.restoreProject(id, this.authOpts())
    return toProjectRecord(dto)
  }

  async permanentlyDeleteProject(id: string): Promise<void> {
    await this.backend.files.permanentlyDeleteProject(id, this.authOpts())
  }

  // --- Folder CRUD ---

  async listFolders(params?: { search?: string }): Promise<FolderRecord[]> {
    const items = await this.backend.files.listFolders(this.authOpts(), params)
    return items.map(toFolderRecord)
  }

  async createFolder(input: { name: string; parentId: string | null }): Promise<FolderRecord> {
    const dto = await this.backend.files.createFolder(input, this.authOpts())
    return toFolderRecord(dto)
  }

  async updateFolder(id: string, patch: { name?: string; parentId?: string | null }): Promise<FolderRecord> {
    const dto = await this.backend.files.updateFolder(id, patch, this.authOpts())
    return toFolderRecord(dto)
  }

  async deleteFolder(id: string, mode: DeleteFolderMode): Promise<void> {
    await this.backend.files.deleteFolder(id, { mode }, this.authOpts())
  }

  async restoreFolder(id: string): Promise<FolderRecord> {
    const dto = await this.backend.files.restoreFolder(id, this.authOpts())
    return toFolderRecord(dto)
  }

  async permanentlyDeleteFolder(id: string): Promise<void> {
    await this.backend.files.deleteFolder(id, { mode: 'permanent' }, this.authOpts())
  }

  // --- Trash ---

  async listTrash(): Promise<TrashEntry[]> {
    const items = await this.backend.files.listTrash(this.authOpts())
    return items.map(toTrashEntry)
  }

  // --- Pages (summary list) ---

  async listPageSummaries(projectId: string): Promise<PageSummary[]> {
    const items = await this.backend.files.listPageSummaries(projectId, this.authOpts())
    return items.map(toPageSummary)
  }

  // --- Pages (full snapshot) ---

  async getPageSnapshot(pageId: string): Promise<PageSnapshot | undefined> {
    try {
      const payload = await this.backend.files.getPageSnapshot(pageId, this.authOpts())
      return fromSnapshotPayload(payload)
    } catch (e) {
      if (isNotFound(e)) return undefined
      throw e
    }
  }

  async createPage(projectId: string, snapshot: PageSnapshot): Promise<PageSummary> {
    const payload = toSnapshotPayload(snapshot)
    const dto = await this.backend.files.createPage(projectId, payload, this.authOpts())
    return toPageSummary(dto)
  }

  async savePageSnapshot(snapshot: PageSnapshot): Promise<PageSummary> {
    const payload = toSnapshotPayload(snapshot)
    const dto = await this.backend.files.savePageSnapshot(snapshot.page.id, payload, this.authOpts())
    return toPageSummary(dto)
  }

  async deletePage(pageId: string): Promise<void> {
    await this.backend.files.deletePage(pageId, this.authOpts())
  }

  // --- Thumbnail (bearer-authed fetch) ---

  async getThumbnailBlob(pageId: string): Promise<Blob | undefined> {
    try {
      return await this.backend.files.getPageThumbnail(pageId, this.authOpts())
    } catch (e) {
      if (isNotFound(e)) return undefined
      throw e
    }
  }
}

// --- DTO ↔ domain conversions ---

function toProjectRecord(dto: ProjectDto): ProjectRecord {
  return {
    id: dto.id,
    name: dto.name,
    sourceLang: dto.sourceLang,
    targetLang: dto.targetLang,
    pageCount: dto.pageCount,
    status: dto.status as ProjectStatus,
    folderId: dto.folderId,
    folderPath: dto.folderPath,
    deletedAt: dto.deletedAt,
    config: dto.config as unknown as ProjectConfig,
    createdAt: dto.createdAt,
    updatedAt: dto.updatedAt,
    thumbnailUrl: dto.thumbnailUrl,
  }
}

function toFolderRecord(dto: FolderDto): FolderRecord {
  return {
    id: dto.id,
    name: dto.name,
    parentId: dto.parentId,
    path: dto.path,
    createdAt: dto.createdAt,
    updatedAt: dto.updatedAt,
    deletedAt: dto.deletedAt,
  }
}

function toTrashEntry(dto: TrashEntryDto): TrashEntry {
  return dto.type === 'folder'
    ? { type: 'folder', item: toFolderRecord(dto.item) }
    : { type: 'project', item: toProjectRecord(dto.item) }
}

function toPageSummary(dto: PageSummaryDto): PageSummary {
  return {
    id: dto.id,
    projectId: dto.projectId,
    index: dto.index,
    status: dto.status as PageStatus,
    thumbnailUrl: dto.thumbnailUrl,
    updatedAt: dto.updatedAt,
  }
}

function toSnapshotPayload(snapshot: PageSnapshot): PageSnapshotPayload {
  return {
    metadata: {
      page: {
        id: snapshot.page.id,
        projectId: snapshot.page.projectId,
        index: snapshot.page.index,
        status: snapshot.page.status,
      },
    },
    originalImage: snapshot.originalImage,
    layerBlob: snapshot.layerBlob,
    thumbnail: snapshot.thumbnail,
  }
}

function fromSnapshotPayload(payload: PageSnapshotPayload): PageSnapshot {
  const metaPage = payload.metadata.page
  return {
    page: {
      id: metaPage.id,
      projectId: metaPage.projectId,
      index: metaPage.index,
      status: metaPage.status as PageStatus,
    },
    originalImage: payload.originalImage,
    layerBlob: payload.layerBlob,
    thumbnail: payload.thumbnail,
  }
}

function isNotFound(err: unknown): boolean {
  if (!(err instanceof BackendError)) return false
  const code = err.payload.code
  return code === 'project_not_found' || code === 'page_not_found'
}
