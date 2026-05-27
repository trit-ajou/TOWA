import { getDB, type ProjectRecord, type PageRecord, type FolderRecord } from './db'
import type { DeleteFolderMode, FileAdapter, PageSummary, PageSnapshot, TrashEntry } from './contracts'

function notImplementedInLocal(name: string): Error {
  return new Error(
    `LocalFileAdapter does not implement ${name}. ` +
    'Standalone mode is disabled until LocalFileManager lands with Electron (see #37). ' +
    'Use VITE_DEPLOYMENT_MODE=cloud.',
  )
}

/**
 * Vue reactive Proxy는 IndexedDB의 structuredClone이 복제하지 못함
 * (`DataCloneError: [object Array] could not be cloned`).
 * IDB에 쓰기 직전에 JSON을 통해 plain 객체로 변환한다.
 * Blob/File은 JSON으로 직렬화 불가하므로 별도 처리(이 함수 사용 금지).
 */
function sanitize<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export class LocalFileAdapter implements FileAdapter {

  // --- Project CRUD ---

  async listProjects(): Promise<ProjectRecord[]> {
    const db = await getDB()
    return db.getAll('projects')
  }

  async getProject(id: string): Promise<ProjectRecord | undefined> {
    const db = await getDB()
    return db.get('projects', id)
  }

  async createProject(project: ProjectRecord): Promise<ProjectRecord> {
    const db = await getDB()
    const existing = await db.get('projects', project.id)
    if (existing) {
      throw new Error(`Project already exists: ${project.id}`)
    }
    const now = new Date().toISOString()
    const record: ProjectRecord = sanitize({
      ...project,
      pageCount: project.pageCount ?? 0,
      createdAt: project.createdAt || now,
      updatedAt: project.updatedAt || now,
    })
    await db.put('projects', record)
    return record
  }

  async updateProject(id: string, patch: Partial<ProjectRecord>): Promise<ProjectRecord> {
    const db = await getDB()
    const existing = await db.get('projects', id)
    if (!existing) {
      throw new Error(`Project not found: ${id}`)
    }
    const updated: ProjectRecord = sanitize({
      ...existing,
      ...patch,
      id, // id는 절대 변경 불가
      updatedAt: new Date().toISOString(),
    })
    await db.put('projects', updated)
    return updated
  }

  async deleteProject(id: string): Promise<void> {
    const db = await getDB()
    // 프로젝트의 모든 페이지 삭제
    const pages = await db.getAllFromIndex('pages', 'by-project', id)
    for (const page of pages) {
      await this.deletePageBinaries(page.id)
    }
    // pages 레코드 삭제
    const tx = db.transaction('pages', 'readwrite')
    for (const page of pages) {
      await tx.store.delete(page.id)
    }
    await tx.done
    // 프로젝트 삭제
    await db.delete('projects', id)
  }

  async restoreProject(_id: string): Promise<ProjectRecord> {
    throw notImplementedInLocal('restoreProject')
  }
  async permanentlyDeleteProject(_id: string): Promise<void> {
    throw notImplementedInLocal('permanentlyDeleteProject')
  }
  async listFolders(_params?: { search?: string }): Promise<FolderRecord[]> {
    throw notImplementedInLocal('listFolders')
  }
  async createFolder(_input: { name: string; parentId: string | null }): Promise<FolderRecord> {
    throw notImplementedInLocal('createFolder')
  }
  async updateFolder(_id: string, _patch: { name?: string; parentId?: string | null }): Promise<FolderRecord> {
    throw notImplementedInLocal('updateFolder')
  }
  async deleteFolder(_id: string, _mode: DeleteFolderMode): Promise<void> {
    throw notImplementedInLocal('deleteFolder')
  }
  async restoreFolder(_id: string): Promise<FolderRecord> {
    throw notImplementedInLocal('restoreFolder')
  }
  async permanentlyDeleteFolder(_id: string): Promise<void> {
    throw notImplementedInLocal('permanentlyDeleteFolder')
  }
  async listTrash(): Promise<TrashEntry[]> {
    throw notImplementedInLocal('listTrash')
  }

  // --- Pages (summary list) ---

  async listPageSummaries(projectId: string): Promise<PageSummary[]> {
    const db = await getDB()
    const pages = await db.getAllFromIndex('pages', 'by-project', projectId)
    return pages
      .sort((a, b) => a.index - b.index)
      .map((p) => ({
        id: p.id,
        projectId: p.projectId,
        index: p.index,
        status: p.status,
        thumbnailUrl: undefined,
        updatedAt: new Date().toISOString(),
      }))
  }

  // --- Pages (full snapshot) ---

  async getPageSnapshot(pageId: string): Promise<PageSnapshot | undefined> {
    const db = await getDB()
    const page = await db.get('pages', pageId)
    if (!page) return undefined

    const [imgRecord, layerRecord, thumbRecord] = await Promise.all([
      db.get('page-images', pageId),
      db.get('page-layers', pageId),
      db.get('thumbnails', pageId),
    ])

    // 3개 binary 중 하나라도 없으면 undefined
    if (!imgRecord || !layerRecord || !thumbRecord) return undefined

    return {
      page: {
        id: page.id,
        projectId: page.projectId,
        index: page.index,
        status: page.status,
      },
      originalImage: imgRecord.blob,
      layerBlob: layerRecord.blob,
      thumbnail: thumbRecord.blob,
    }
  }

  async createPage(projectId: string, snapshot: PageSnapshot): Promise<PageSummary> {
    if (snapshot.page.projectId !== projectId) {
      throw new Error(`Snapshot projectId mismatch: expected ${projectId}, got ${snapshot.page.projectId}`)
    }

    const db = await getDB()
    // 현재 프로젝트의 page 수를 계산하여 index 결정
    const existingPages = await db.getAllFromIndex('pages', 'by-project', projectId)
    const newIndex = existingPages.length + 1

    const pageRecord: PageRecord = {
      id: snapshot.page.id,
      projectId,
      index: newIndex,
      status: snapshot.page.status,
    }

    // Atomic transaction: pages + 3 binary stores
    const tx = db.transaction(
      ['pages', 'page-images', 'page-layers', 'thumbnails'],
      'readwrite',
    )
    await Promise.all([
      tx.objectStore('pages').put(pageRecord),
      tx.objectStore('page-images').put({ pageId: snapshot.page.id, blob: snapshot.originalImage }),
      tx.objectStore('page-layers').put({ pageId: snapshot.page.id, blob: snapshot.layerBlob, savedAt: new Date().toISOString() }),
      tx.objectStore('thumbnails').put({ pageId: snapshot.page.id, blob: snapshot.thumbnail }),
      tx.done,
    ])

    // project pageCount 갱신
    const project = await db.get('projects', projectId)
    if (project) {
      project.pageCount = newIndex
      project.updatedAt = new Date().toISOString()
      await db.put('projects', project)
    }

    return {
      id: snapshot.page.id,
      projectId,
      index: newIndex,
      status: snapshot.page.status,
      thumbnailUrl: undefined,
      updatedAt: new Date().toISOString(),
    }
  }

  async savePageSnapshot(snapshot: PageSnapshot): Promise<PageSummary> {
    const db = await getDB()
    const pageId = snapshot.page.id

    // 기존 page 확인
    const existing = await db.get('pages', pageId)
    if (!existing) {
      throw new Error(`Page not found: ${pageId}`)
    }

    const pageRecord: PageRecord = {
      id: pageId,
      projectId: snapshot.page.projectId,
      index: existing.index, // index는 기존 값 유지
      status: snapshot.page.status,
    }

    // Atomic transaction: 4개 store에 put
    const tx = db.transaction(
      ['pages', 'page-images', 'page-layers', 'thumbnails'],
      'readwrite',
    )
    await Promise.all([
      tx.objectStore('pages').put(pageRecord),
      tx.objectStore('page-images').put({ pageId, blob: snapshot.originalImage }),
      tx.objectStore('page-layers').put({ pageId, blob: snapshot.layerBlob, savedAt: new Date().toISOString() }),
      tx.objectStore('thumbnails').put({ pageId, blob: snapshot.thumbnail }),
      tx.done,
    ])

    // project updatedAt 갱신
    const project = await db.get('projects', snapshot.page.projectId)
    if (project) {
      project.updatedAt = new Date().toISOString()
      await db.put('projects', project)
    }

    const now = new Date().toISOString()
    return {
      id: pageId,
      projectId: snapshot.page.projectId,
      index: existing.index,
      status: snapshot.page.status,
      thumbnailUrl: undefined,
      updatedAt: now,
    }
  }

  async deletePage(pageId: string): Promise<void> {
    const db = await getDB()
    const page = await db.get('pages', pageId)
    if (!page) return

    const projectId = page.projectId

    // page 레코드 + 3개 binary + cache 삭제
    await this.deletePageBinaries(pageId)
    const tx = db.transaction('pages', 'readwrite')
    await tx.store.delete(pageId)
    await tx.done

    // 나머지 pages를 index 순으로 재조회 → 1..N 재배치
    const remaining = await db.getAllFromIndex('pages', 'by-project', projectId)
    remaining.sort((a, b) => a.index - b.index)
    if (remaining.length > 0) {
      const reindexTx = db.transaction('pages', 'readwrite')
      for (let i = 0; i < remaining.length; i++) {
        remaining[i].index = i + 1
        await reindexTx.store.put(remaining[i])
      }
      await reindexTx.done
    }

    // project pageCount 갱신
    const project = await db.get('projects', projectId)
    if (project) {
      project.pageCount = remaining.length
      project.updatedAt = new Date().toISOString()
      await db.put('projects', project)
    }
  }

  // --- Thumbnail blob ---

  async getThumbnailBlob(pageId: string): Promise<Blob | undefined> {
    const db = await getDB()
    const record = await db.get('thumbnails', pageId)
    return record?.blob
  }

  // --- Internal helpers ---

  private async deletePageBinaries(pageId: string): Promise<void> {
    const db = await getDB()
    const tx = db.transaction(
      ['page-images', 'page-layers', 'thumbnails', 'page-cache'],
      'readwrite',
    )
    await Promise.all([
      tx.objectStore('page-images').delete(pageId),
      tx.objectStore('page-layers').delete(pageId),
      tx.objectStore('thumbnails').delete(pageId),
      tx.objectStore('page-cache').delete(pageId),
      tx.done,
    ])
  }
}
