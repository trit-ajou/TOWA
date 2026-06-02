import { watch, unref, type MaybeRef } from 'vue'
import { useFileAdapter } from './useFileAdapter'
import { pageBinaryCache } from '@/file-adapter/cache-instances'

const L1_RADIUS = 3 // active ±3 = sliding window of 7
const L2_BYTE_CAP = 1024 * 1024 * 1024 // 1GB

/**
 * Prefetch page-binary blobs (#39 §page-binary-prefetch).
 *
 * Two prefetch tiers run off the active page:
 *  L1 — active ±{@link L1_RADIUS} pages, no byte cap, prioritized by proximity.
 *  L2 — the rest of the project, walked in distance order from the active
 *       page until the running total reaches {@link L2_BYTE_CAP}.
 *
 * Re-runs whenever activePageId or the project's page list changes; the
 * underlying BlobCache de-duplicates so repeats are cheap.
 */
export function usePageBinaryPrefetch(opts: {
  pageIds: MaybeRef<string[]>
  activePageId: MaybeRef<string | null | undefined>
}) {
  const fileAdapter = useFileAdapter()

  let runId = 0
  async function prefetch(activePid: string, allIds: string[]) {
    const myRun = ++runId
    const idx = allIds.indexOf(activePid)
    if (idx === -1) return

    const ordered = orderByDistance(allIds, idx)

    let bytesUsed = 0
    for (let i = 0; i < ordered.length; i++) {
      // Bail out if a newer prefetch run kicked in (page changed mid-walk).
      if (myRun !== runId) return

      const pid = ordered[i]
      const distance = Math.abs(allIds.indexOf(pid) - idx)
      const inL1 = distance <= L1_RADIUS

      const cached = await pageBinaryCache.get(pid)
      if (cached) {
        bytesUsed += cached.size
        if (!inL1 && bytesUsed > L2_BYTE_CAP) return
        continue
      }

      try {
        const snapshot = await fileAdapter.getPageSnapshot(pid)
        if (!snapshot) continue
        const blob = snapshot.layerBlob
        await pageBinaryCache.set(pid, blob)
        bytesUsed += blob.size
        if (!inL1 && bytesUsed > L2_BYTE_CAP) return
      } catch (e) {
        // Swallow per-page errors — prefetch is best-effort.
        console.warn(`[prefetch] page ${pid} skipped`, e)
      }
    }
  }

  watch(
    () => [unref(opts.activePageId), unref(opts.pageIds)] as const,
    ([active, all]) => {
      if (!active || !all?.length) return
      void prefetch(active, all)
    },
    { immediate: true },
  )
}

// Page ids ordered by closeness to `pivot`, then forward. e.g. for pivot=2:
//   [2, 3, 1, 4, 0, 5, ...]
function orderByDistance(ids: string[], pivot: number): string[] {
  const out: string[] = [ids[pivot]]
  for (let off = 1; off < ids.length; off++) {
    if (pivot + off < ids.length) out.push(ids[pivot + off])
    if (pivot - off >= 0) out.push(ids[pivot - off])
  }
  return out
}
