import { openDB, deleteDB, type IDBPDatabase } from 'idb'
import type { PersistedClient, Persister } from '@tanstack/query-persist-client-core'

// User-namespaced TanStack Query persister.
// Stores the serialized query cache snapshot at a single key in a dedicated
// IDB database `towa-query-${userId}`. Switching users opens a different DB,
// so caches stay isolated across logins.

const STORE_NAME = 'query-cache'
const KEY = 'queries'

function dbName(userId: string): string {
  return `towa-query-${userId}`
}

async function openOrReset(userId: string): Promise<IDBPDatabase> {
  try {
    return await openDB(dbName(userId), 1, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME)
        }
      },
    })
  } catch (e) {
    console.warn(`[QueryPersister] open failed, wiping ${dbName(userId)}`, e)
    await deleteDB(dbName(userId))
    return openDB(dbName(userId), 1, {
      upgrade(db) {
        db.createObjectStore(STORE_NAME)
      },
    })
  }
}

export function createIDBPersister(userId: string): Persister {
  const dbPromise = openOrReset(userId)
  return {
    persistClient: async (client: PersistedClient) => {
      const db = await dbPromise
      await db.put(STORE_NAME, client, KEY)
    },
    restoreClient: async () => {
      const db = await dbPromise
      return (await db.get(STORE_NAME, KEY)) as PersistedClient | undefined
    },
    removeClient: async () => {
      const db = await dbPromise
      await db.delete(STORE_NAME, KEY)
    },
  }
}
