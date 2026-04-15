import { getDB } from './db'

const MAX_MEMORY_ENTRIES = 3
const MAX_IDB_CACHE_ENTRIES = 10

/**
 * 페이지 전환 시 bitmappery 편집 상태를 캐시하는 2계층 캐시.
 * - L1: 메모리 (Map<pageId, Blob>) — 즉시 복원, 탭 종료 시 소멸
 * - L2: IndexedDB page-cache store — ~100ms 복원, 탭 종료 후에도 유지
 */
export class PageCache {
  private memory = new Map<string, Blob>()
  private accessOrder: string[] = []  // LRU 순서 (최신이 끝)

  // --- L1: 메모리 캐시 ---

  getFromMemory(pageId: string): Blob | undefined {
    const blob = this.memory.get(pageId)
    if (blob) this.touchAccessOrder(pageId)
    return blob
  }

  setToMemory(pageId: string, blob: Blob): void {
    this.memory.set(pageId, blob)
    this.touchAccessOrder(pageId)
    // LRU eviction
    while (this.memory.size > MAX_MEMORY_ENTRIES) {
      const oldest = this.accessOrder.shift()
      if (oldest) this.memory.delete(oldest)
    }
  }

  // --- L2: IndexedDB 캐시 ---

  async getFromIDB(pageId: string): Promise<Blob | undefined> {
    const db = await getDB()
    const record = await db.get('page-cache', pageId)
    if (record) {
      // 접근 시간 갱신
      await db.put('page-cache', { ...record, accessedAt: Date.now() })
      // L1에도 승격
      this.setToMemory(pageId, record.blob)
    }
    return record?.blob
  }

  async setToIDB(pageId: string, blob: Blob): Promise<void> {
    const db = await getDB()
    await db.put('page-cache', { pageId, blob, accessedAt: Date.now() })
    await this.evictOldIDB()
  }

  // --- 통합 조회: L1 → L2 ---

  async get(pageId: string): Promise<Blob | undefined> {
    return this.getFromMemory(pageId) ?? await this.getFromIDB(pageId)
  }

  // --- 양쪽에 동시 캐시 ---

  async set(pageId: string, blob: Blob): Promise<void> {
    this.setToMemory(pageId, blob)
    await this.setToIDB(pageId, blob)
  }

  // --- LRU helpers ---

  private touchAccessOrder(pageId: string): void {
    const idx = this.accessOrder.indexOf(pageId)
    if (idx !== -1) this.accessOrder.splice(idx, 1)
    this.accessOrder.push(pageId)
  }

  private async evictOldIDB(): Promise<void> {
    const db = await getDB()
    const tx = db.transaction('page-cache', 'readwrite')
    const store = tx.objectStore('page-cache')
    const count = await store.count()
    if (count <= MAX_IDB_CACHE_ENTRIES) return

    // 가장 오래된 것부터 삭제
    const index = store.index('by-accessed')
    let cursor = await index.openCursor()
    let toDelete = count - MAX_IDB_CACHE_ENTRIES
    while (cursor && toDelete > 0) {
      await cursor.delete()
      toDelete--
      cursor = await cursor.continue()
    }
  }
}
