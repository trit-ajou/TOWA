import { QueryClient } from '@tanstack/vue-query'
import { persistQueryClient } from '@tanstack/query-persist-client-core'
import { createIDBPersister } from './idb-persister'
import { setCacheUser, getCacheUserId } from '@/file-adapter/cache-db'
import { clearAllBlobCacheMemory } from '@/file-adapter/cache-instances'

// Shared QueryClient. Per #39:
//   - staleTime: Infinity for all server-state queries
//   - retry 3x with exponential backoff (1s/2s/4s), bail on HTTP 401
//   - query cache persisted to IDB (user-namespaced)
//   - on logout: clear in-memory state only, IDB is preserved
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: Infinity,
      gcTime: 1000 * 60 * 60 * 24, // 24h
      retry: (failureCount, error) => {
        if (isAuthError(error)) return false
        return failureCount < 3
      },
      retryDelay: (attemptIndex) => 1000 * 2 ** attemptIndex,
      refetchOnWindowFocus: false, // window-focus invalidation is handled explicitly
      refetchOnReconnect: false,
    },
    mutations: {
      retry: (failureCount, error) => {
        if (isAuthError(error)) return false
        return failureCount < 3
      },
      retryDelay: (attemptIndex) => 1000 * 2 ** attemptIndex,
    },
  },
})

let detachPersister: (() => void) | null = null

/**
 * Wire (or re-wire) the persister and BlobCache to the active user.
 *  - userId = null → logout: drop in-memory state, keep IDB.
 *  - userId = "..." → login: attach IDB persister, open user cache DB.
 */
export async function setQueryUser(userId: string | null): Promise<void> {
  if (detachPersister) {
    detachPersister()
    detachPersister = null
  }
  if (!userId) {
    queryClient.clear()
    clearAllBlobCacheMemory()
    setCacheUser(null)
    return
  }

  setCacheUser(userId)
  const persister = createIDBPersister(userId)
  // persistQueryClient returns [unsubscribe, restorePromise]
  const [unsubscribe, restored] = persistQueryClient({
    queryClient,
    persister,
    maxAge: 1000 * 60 * 60 * 24 * 7, // 7 days
  })
  // Surface restore errors but don't block the caller.
  restored.catch((e) => console.warn('[QueryPersister] restore failed', e))
  detachPersister = unsubscribe
}

export function getActiveQueryUserId(): string | null {
  return getCacheUserId()
}

function isAuthError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false
  const status = (error as { status?: number }).status
  return status === 401
}
