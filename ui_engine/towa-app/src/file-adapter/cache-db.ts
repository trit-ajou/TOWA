import { openDB, deleteDB, type IDBPDatabase, type DBSchema } from 'idb'

// User-namespaced cache DB (towa-cache-${userId}).
// Holds blob LRU caches (page binary + thumbnail). Persistent stores
// (projects/pages/page-images/...) remain in the legacy `towa-db`.

export interface CacheRecord {
  pageId: string
  blob: Blob
  accessedAt: number
}

interface CacheDBSchema extends DBSchema {
  'page-cache': {
    key: string
    value: CacheRecord
    indexes: { 'by-accessed': number }
  }
  'thumbnail-cache': {
    key: string
    value: CacheRecord
    indexes: { 'by-accessed': number }
  }
}

const CACHE_DB_VERSION = 2

let currentUserId: string | null = null
let dbPromise: Promise<IDBPDatabase<CacheDBSchema>> | null = null

function buildDbName(userId: string): string {
  return `towa-cache-${userId}`
}

async function openCacheDB(userId: string): Promise<IDBPDatabase<CacheDBSchema>> {
  const dbName = buildDbName(userId)
  try {
    return await openDB<CacheDBSchema>(dbName, CACHE_DB_VERSION, {
      upgrade(db, oldVersion) {
        if (oldVersion < 1) {
          const pageStore = db.createObjectStore('page-cache', { keyPath: 'pageId' })
          pageStore.createIndex('by-accessed', 'accessedAt')
        }
        if (oldVersion < 2 && !db.objectStoreNames.contains('thumbnail-cache')) {
          const thumbStore = db.createObjectStore('thumbnail-cache', { keyPath: 'pageId' })
          thumbStore.createIndex('by-accessed', 'accessedAt')
        }
      },
    })
  } catch (e) {
    console.warn(`[CacheDB] migration failed for ${dbName}, wiping and recreating`, e)
    await deleteDB(dbName)
    return openDB<CacheDBSchema>(dbName, CACHE_DB_VERSION, {
      upgrade(db) {
        const pageStore = db.createObjectStore('page-cache', { keyPath: 'pageId' })
        pageStore.createIndex('by-accessed', 'accessedAt')
        const thumbStore = db.createObjectStore('thumbnail-cache', { keyPath: 'pageId' })
        thumbStore.createIndex('by-accessed', 'accessedAt')
      },
    })
  }
}

export function setCacheUser(userId: string | null): void {
  if (currentUserId === userId) return
  if (dbPromise) {
    const prev = dbPromise
    prev.then((db) => db.close()).catch(() => {})
  }
  currentUserId = userId
  dbPromise = userId ? openCacheDB(userId) : null
}

export function getCacheUserId(): string | null {
  return currentUserId
}

export async function getCacheDB(): Promise<IDBPDatabase<CacheDBSchema>> {
  if (!currentUserId || !dbPromise) {
    throw new Error('[CacheDB] no active user — call setCacheUser(userId) before access')
  }
  return dbPromise
}

export type { CacheDBSchema }
