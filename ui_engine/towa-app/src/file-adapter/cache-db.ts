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

// v3: one-time wipe. Before the 2026-09-25 fixes, background AI applies could
// leave poisoned entries here (blank thumbnails, pre-AI documents) that are
// read cache-first and survive reloads. Bumping the version clears them on
// every existing client's next load; the server copy is always intact.
const CACHE_DB_VERSION = 3

let currentUserId: string | null = null
let dbPromise: Promise<IDBPDatabase<CacheDBSchema>> | null = null

// Version-upgrade coordination across tabs. IndexedDB will not upgrade while
// any other tab still holds the DB open at an older version, and a tab
// running an older bundle never lets go — so a naive open waits forever and
// every cache read with it (thumbnails never even get requested). Instead:
//  - while our upgrade is blocked, the cache is treated as unavailable and
//    callers fall straight through to the server (BlobCache already handles
//    getCacheDB() throwing);
//  - when a newer tab wants to upgrade past us, we close our connection.
let dbReady: IDBPDatabase<CacheDBSchema> | null = null
let upgradeBlocked = false
let closedForUpgrade = false
let blockedWaiters: Array<(e: Error) => void> = []

// Chrome does not deliver `blocked` to an open request that is queued behind
// another pending one (e.g. after a full page reload), so the event alone is
// not enough. If the DB has not opened within this window, treat the upgrade
// as blocked; a normal open finishes in milliseconds.
const OPEN_TIMEOUT_MS = 3000

const unavailable = () => new Error('[CacheDB] unavailable: another TOWA tab is holding an older cache version')

function buildDbName(userId: string): string {
  return `towa-cache-${userId}`
}

function markBlocked(): void {
  if (!upgradeBlocked) {
    console.warn('[CacheDB] upgrade blocked by another open TOWA tab; running without the local cache until it closes')
  }
  upgradeBlocked = true
  const waiters = blockedWaiters
  blockedWaiters = []
  waiters.forEach((reject) => reject(unavailable()))
}

const coordination = {
  blocked: markBlocked,
  // A newer bundle in another tab wants to upgrade: step aside. This tab keeps
  // working against the server until it is reloaded onto the new bundle.
  blocking(_current: number, _blocked: number | null, event: IDBVersionChangeEvent) {
    ;(event.target as IDBDatabase).close()
    closedForUpgrade = true
    dbReady = null
  },
  terminated() {
    closedForUpgrade = true
    dbReady = null
  },
}

async function openCacheDB(userId: string): Promise<IDBPDatabase<CacheDBSchema>> {
  const dbName = buildDbName(userId)
  try {
    return await openDB<CacheDBSchema>(dbName, CACHE_DB_VERSION, {
      upgrade(db, oldVersion, _newVersion, tx) {
        if (oldVersion < 1) {
          const pageStore = db.createObjectStore('page-cache', { keyPath: 'pageId' })
          pageStore.createIndex('by-accessed', 'accessedAt')
        }
        if (oldVersion < 2 && !db.objectStoreNames.contains('thumbnail-cache')) {
          const thumbStore = db.createObjectStore('thumbnail-cache', { keyPath: 'pageId' })
          thumbStore.createIndex('by-accessed', 'accessedAt')
        }
        if (oldVersion >= 1 && oldVersion < 3) {
          void tx.objectStore('page-cache').clear()
          void tx.objectStore('thumbnail-cache').clear()
        }
      },
      ...coordination,
    })
  } catch (e) {
    console.warn(`[CacheDB] migration failed for ${dbName}, wiping and recreating`, e)
    await deleteDB(dbName, { blocked: markBlocked })
    return openDB<CacheDBSchema>(dbName, CACHE_DB_VERSION, {
      upgrade(db) {
        const pageStore = db.createObjectStore('page-cache', { keyPath: 'pageId' })
        pageStore.createIndex('by-accessed', 'accessedAt')
        const thumbStore = db.createObjectStore('thumbnail-cache', { keyPath: 'pageId' })
        thumbStore.createIndex('by-accessed', 'accessedAt')
      },
      ...coordination,
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
  dbReady = null
  upgradeBlocked = false
  closedForUpgrade = false
  blockedWaiters = []
  if (!userId) {
    dbPromise = null
    return
  }
  const opening = openCacheDB(userId)
  dbPromise = opening
  const timer = setTimeout(() => {
    if (dbPromise === opening && !dbReady) markBlocked()
  }, OPEN_TIMEOUT_MS)
  opening.then(
    (db) => {
      clearTimeout(timer)
      if (dbPromise !== opening) return // user switched meanwhile
      dbReady = db
      upgradeBlocked = false
      blockedWaiters = []
    },
    () => clearTimeout(timer),
  )
}

export function getCacheUserId(): string | null {
  return currentUserId
}

export async function getCacheDB(): Promise<IDBPDatabase<CacheDBSchema>> {
  if (!currentUserId || !dbPromise) {
    throw new Error('[CacheDB] no active user — call setCacheUser(userId) before access')
  }
  if (dbReady) return dbReady
  if (upgradeBlocked || closedForUpgrade) throw unavailable()
  // Still opening: wait, but bail out the moment the upgrade turns out blocked.
  const opening = dbPromise
  return new Promise((resolve, reject) => {
    blockedWaiters.push(reject)
    opening.then(resolve, reject)
  })
}

export type { CacheDBSchema }
