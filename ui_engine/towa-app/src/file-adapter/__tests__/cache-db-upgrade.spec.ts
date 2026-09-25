import 'fake-indexeddb/auto'
import { openDB } from 'idb'
import { describe, expect, it } from 'vitest'

import { BlobCache } from '@/file-adapter/blob-cache'
import { setCacheUser } from '@/file-adapter/cache-db'

// Clients that ran the pre-2026-09-25 code may hold poisoned entries (blank
// thumbnails, pre-AI documents) in a v2 cache DB. Opening it at v3 must wipe
// them so the next read goes to the server.
async function seedV2(userId: string) {
  const db = await openDB(`towa-cache-${userId}`, 2, {
    upgrade(d) {
      d.createObjectStore('page-cache', { keyPath: 'pageId' }).createIndex('by-accessed', 'accessedAt')
      d.createObjectStore('thumbnail-cache', { keyPath: 'pageId' }).createIndex('by-accessed', 'accessedAt')
    },
  })
  await db.put('page-cache', { pageId: 'p1', blob: new Blob(['stale-doc']), accessedAt: 1 })
  await db.put('thumbnail-cache', { pageId: 'p1', blob: new Blob(['blank-thumb']), accessedAt: 1 })
  db.close()
}

describe('cache-db v3 upgrade', () => {
  it('wipes entries left by a v2 client', async () => {
    await seedV2('upgrade-user')
    setCacheUser('upgrade-user')
    const pages = new BlobCache('page-cache', 7, 1000)
    const thumbs = new BlobCache('thumbnail-cache', 500, 2000)
    expect(await pages.get('p1')).toBeUndefined()
    expect(await thumbs.get('p1')).toBeUndefined()

    // The upgraded DB is fully usable afterwards.
    await thumbs.set('p1', new Blob(['fresh']))
    thumbs.clearMemory()
    expect(await (await thumbs.get('p1'))?.text()).toBe('fresh')
  })
})
