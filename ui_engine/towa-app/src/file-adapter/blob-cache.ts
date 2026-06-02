import { getCacheDB, type CacheDBSchema } from './cache-db'

type CacheStoreName = Extract<keyof CacheDBSchema, string>

/**
 * Two-tier LRU blob cache (memory + IndexedDB) generalized from the original
 * PageCache. One instance per store: see file-adapter-sync issue (#39).
 *
 * Memory is process-local (cleared on logout via clearMemory). IDB is
 * user-namespaced via getCacheDB(); switching users automatically routes
 * subsequent IDB ops to a different DB while leaving prior data intact.
 */
export class BlobCache {
  private memory = new Map<string, Blob>()
  private accessOrder: string[] = []

  constructor(
    private readonly storeName: CacheStoreName,
    private readonly maxMemory: number,
    private readonly maxIDB: number,
  ) {}

  // --- L1: memory ---

  getFromMemory(key: string): Blob | undefined {
    const blob = this.memory.get(key)
    if (blob) this.touchAccessOrder(key)
    return blob
  }

  setToMemory(key: string, blob: Blob): void {
    this.memory.set(key, blob)
    this.touchAccessOrder(key)
    while (this.memory.size > this.maxMemory) {
      const oldest = this.accessOrder.shift()
      if (oldest) this.memory.delete(oldest)
    }
  }

  /** Drop in-memory entries only. IDB is preserved (per logout policy). */
  clearMemory(): void {
    this.memory.clear()
    this.accessOrder = []
  }

  // --- L2: IDB ---

  async getFromIDB(key: string): Promise<Blob | undefined> {
    let db
    try {
      db = await getCacheDB()
    } catch {
      return undefined
    }
    const record = await db.get(this.storeName, key)
    if (record) {
      await db.put(this.storeName, { ...record, accessedAt: Date.now() })
      this.setToMemory(key, record.blob)
    }
    return record?.blob
  }

  async setToIDB(key: string, blob: Blob): Promise<void> {
    let db
    try {
      db = await getCacheDB()
    } catch {
      return
    }
    await db.put(this.storeName, { pageId: key, blob, accessedAt: Date.now() })
    await this.evictOldIDB()
  }

  // --- combined L1 → L2 lookup ---

  async get(key: string): Promise<Blob | undefined> {
    return this.getFromMemory(key) ?? (await this.getFromIDB(key))
  }

  async set(key: string, blob: Blob): Promise<void> {
    this.setToMemory(key, blob)
    await this.setToIDB(key, blob)
  }

  // --- LRU helpers ---

  private touchAccessOrder(key: string): void {
    const idx = this.accessOrder.indexOf(key)
    if (idx !== -1) this.accessOrder.splice(idx, 1)
    this.accessOrder.push(key)
  }

  private async evictOldIDB(): Promise<void> {
    let db
    try {
      db = await getCacheDB()
    } catch {
      return
    }
    const tx = db.transaction(this.storeName, 'readwrite')
    const store = tx.objectStore(this.storeName)
    const count = await store.count()
    if (count <= this.maxIDB) return
    const index = store.index('by-accessed')
    let cursor = await index.openCursor()
    let toDelete = count - this.maxIDB
    while (cursor && toDelete > 0) {
      await cursor.delete()
      toDelete--
      cursor = await cursor.continue()
    }
  }
}
