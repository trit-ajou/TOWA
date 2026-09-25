import 'fake-indexeddb/auto'
import { openDB } from 'idb'
import { describe, expect, it } from 'vitest'

import { BlobCache } from '@/file-adapter/blob-cache'
import { setCacheUser } from '@/file-adapter/cache-db'

// An old-bundle tab keeps the cache DB open at a lower version and never
// closes it, which blocks our version upgrade. Reads must not hang on that:
// the app falls back to the server until the other tab lets go.
const within = <T>(p: Promise<T>, ms = 1500) =>
  Promise.race([p, new Promise<never>((_, rej) => setTimeout(() => rej(new Error(`hung > ${ms}ms`)), ms))])

async function holdOldConnection(userId: string) {
  return openDB(`towa-cache-${userId}`, 2, {
    upgrade(d) {
      d.createObjectStore('page-cache', { keyPath: 'pageId' }).createIndex('by-accessed', 'accessedAt')
      d.createObjectStore('thumbnail-cache', { keyPath: 'pageId' }).createIndex('by-accessed', 'accessedAt')
    },
    // deliberately no blocking() handler — that is what the old bundle does
  })
}

describe('cache-db upgrade blocked by another tab', () => {
  it('reads and writes settle instead of hanging while blocked', async () => {
    const held = await holdOldConnection('blocked-user')
    setCacheUser('blocked-user')
    const thumbs = new BlobCache('thumbnail-cache', 500, 2000)
    await expect(within(thumbs.get('p1'))).resolves.toBeUndefined()
    await expect(within(thumbs.set('p1', new Blob(['x'])))).resolves.toBeUndefined()

    // Once the old tab lets go, the upgrade completes and the cache works.
    held.close()
    await new Promise((r) => setTimeout(r, 50))
    await within(thumbs.set('p2', new Blob(['after'])))
    thumbs.clearMemory()
    expect(await (await within(thumbs.get('p2')))?.text()).toBe('after')
  })

  it('steps aside when a newer version wants to upgrade', async () => {
    setCacheUser('blocking-user')
    const thumbs = new BlobCache('thumbnail-cache', 500, 2000)
    await thumbs.set('p1', new Blob(['v']))
    // A future bundle opening a higher version must not be blocked by us.
    const newer = await within(openDB('towa-cache-blocking-user', 99))
    newer.close()
  })
})
