import { getDB, type ProjectRecord, type PageRecord } from './db'
import type { FileAdapter } from './contracts'

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

  async saveProject(project: ProjectRecord): Promise<void> {
    const db = await getDB()
    await db.put('projects', project)
  }

  async deleteProject(id: string): Promise<void> {
    const db = await getDB()
    await db.delete('projects', id)
    await this.deletePagesByProject(id)
  }

  // --- Page CRUD ---

  async listPages(projectId: string): Promise<PageRecord[]> {
    const db = await getDB()
    const pages = await db.getAllFromIndex('pages', 'by-project', projectId)
    return pages.sort((a, b) => a.index - b.index)
  }

  async getPage(pageId: string): Promise<PageRecord | undefined> {
    const db = await getDB()
    return db.get('pages', pageId)
  }

  async savePage(page: PageRecord): Promise<void> {
    const db = await getDB()
    await db.put('pages', page)
  }

  async deletePage(pageId: string): Promise<void> {
    const db = await getDB()
    const tx = db.transaction(
      ['pages', 'page-images', 'page-layers', 'thumbnails', 'page-cache'],
      'readwrite',
    )
    await Promise.all([
      tx.objectStore('pages').delete(pageId),
      tx.objectStore('page-images').delete(pageId),
      tx.objectStore('page-layers').delete(pageId),
      tx.objectStore('thumbnails').delete(pageId),
      tx.objectStore('page-cache').delete(pageId),
      tx.done,
    ])
  }

  async deletePagesByProject(projectId: string): Promise<void> {
    const pages = await this.listPages(projectId)
    for (const page of pages) {
      await this.deletePage(page.id)
    }
  }

  // --- Original images ---

  async getOriginalImage(pageId: string): Promise<Blob | undefined> {
    const db = await getDB()
    const record = await db.get('page-images', pageId)
    return record?.blob
  }

  async saveOriginalImage(pageId: string, blob: Blob): Promise<void> {
    const db = await getDB()
    await db.put('page-images', { pageId, blob })
  }

  // --- Thumbnails ---

  async getThumbnail(pageId: string): Promise<Blob | undefined> {
    const db = await getDB()
    const record = await db.get('thumbnails', pageId)
    return record?.blob
  }

  async saveThumbnail(pageId: string, blob: Blob): Promise<void> {
    const db = await getDB()
    await db.put('thumbnails', { pageId, blob })
  }

  // --- Layer data (bitmappery serialized Blob) ---

  async getLayerData(pageId: string): Promise<Blob | undefined> {
    const db = await getDB()
    const record = await db.get('page-layers', pageId)
    return record?.blob
  }

  async saveLayerData(pageId: string, blob: Blob): Promise<void> {
    const db = await getDB()
    await db.put('page-layers', {
      pageId,
      blob,
      savedAt: new Date().toISOString(),
    })
  }
}
