import { BlobCache } from './blob-cache'

// Per #39 spec.
//   page-cache table:      maxMemory=3, maxIDB=10
//   page-cache prefetch:   L1 = active ±3 sliding window (7 entries)
//                          L2 = whole project, hard-capped at 1GB
// The two views conflict in raw numbers; we resolve by sizing L1 to fit
// the sliding window (7) and giving L2 enough headroom (1000 entries) so
// that the 1GB byte cap — enforced at the prefetch layer in
// composables/usePageBinaryPrefetch — is the effective limit.
//
// thumbnail-cache stays as documented (500 / 2000).
export const pageBinaryCache = new BlobCache('page-cache', 7, 1000)
export const thumbnailCache = new BlobCache('thumbnail-cache', 500, 2000)

export function clearAllBlobCacheMemory(): void {
  pageBinaryCache.clearMemory()
  thumbnailCache.clearMemory()
}
