import { ref, watch, onBeforeUnmount, unref, type MaybeRef } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { useFileAdapter } from './useFileAdapter'
import { queryKeys } from './queryKeys'
import { thumbnailCache } from '@/file-adapter/cache-instances'

/**
 * Per #39, thumbnail blobs are cached in the user-namespaced BlobCache and
 * the Object URL that the DOM consumes is owned by *the component that
 * displays it*. This composable wraps the read-side: it returns a reactive
 * ref<string | null> URL that auto-tracks the given pageId and is revoked
 * on unmount or pageId change.
 *
 * Blob fetch flow:
 *   memory → IDB → fileAdapter.getThumbnailBlob() → write back to cache
 *
 * Errors and 404s come back as `undefined` from the file adapter and surface
 * here as `null` URLs (no thumbnail visible). The list-level query already
 * handles 404 redirect logic for the page itself.
 */
export function useThumbnailUrl(pageId: MaybeRef<string | null | undefined>) {
  const fileAdapter = useFileAdapter()
  const qc = useQueryClient()

  const blobQuery = useQuery({
    queryKey: computeKey(pageId),
    queryFn: async () => {
      const pid = unref(pageId)
      if (!pid) return null
      const cached = await thumbnailCache.get(pid)
      if (cached) return cached
      const blob = await fileAdapter.getThumbnailBlob(pid)
      if (blob) await thumbnailCache.set(pid, blob)
      return blob ?? null
    },
    enabled: computeEnabled(pageId),
  })

  const url = ref<string | null>(null)
  let activeUrl: string | null = null
  function setUrl(next: string | null) {
    if (activeUrl) URL.revokeObjectURL(activeUrl)
    activeUrl = next
    url.value = next
  }

  // Whenever the underlying blob changes (pageId switch or invalidation),
  // rotate the Object URL so DOM consumers stay in sync without leaking.
  watch(
    () => blobQuery.data.value,
    (blob) => {
      if (blob instanceof Blob) {
        setUrl(URL.createObjectURL(blob))
      } else {
        setUrl(null)
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    setUrl(null)
  })

  // imperative refresh — for callers that want to force a re-fetch
  function refresh() {
    const pid = unref(pageId)
    if (!pid) return
    qc.invalidateQueries({ queryKey: queryKeys.binary.thumbnail(pid) })
  }

  return { url, isLoading: blobQuery.isLoading, refresh }
}

// queryKey + enabled need to react to the source ref. Wrap in computed-style
// helpers so the useQuery overload picks the reactive variant.
import { computed } from 'vue'
function computeKey(pageId: MaybeRef<string | null | undefined>) {
  return computed(() => queryKeys.binary.thumbnail(unref(pageId) ?? ''))
}
function computeEnabled(pageId: MaybeRef<string | null | undefined>) {
  return computed(() => Boolean(unref(pageId)))
}
