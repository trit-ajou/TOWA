import { BlobCache } from './blob-cache'

// Per #39 spec:
//   page-cache:      maxMemory=3,   maxIDB=10
//   thumbnail-cache: maxMemory=500, maxIDB=2000

export const pageBinaryCache = new BlobCache('page-cache', 3, 10)
export const thumbnailCache = new BlobCache('thumbnail-cache', 500, 2000)

export function clearAllBlobCacheMemory(): void {
  pageBinaryCache.clearMemory()
  thumbnailCache.clearMemory()
}
