import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it } from 'vitest'

import { BlobCache } from '@/file-adapter/blob-cache'
import { setCacheUser } from '@/file-adapter/cache-db'

// Regression for the in-session stale-page bug: a read that goes to IDB used to
// write the record it had just read back in a *separate* transaction (to bump
// accessedAt). A delete()/set() landing between the read and that write-back
// was silently undone, so prefetch resurrected a pre-AI document and the editor
// reopened the page without the background AI result.

let n = 0
function freshCache(): BlobCache {
  // New user namespace per test → isolated IDB database.
  setCacheUser(`blob-cache-spec-${++n}`)
  return new BlobCache('page-cache', 7, 1000)
}

const text = async (b: Blob | undefined) => (b ? await b.text() : undefined)

describe('BlobCache concurrency', () => {
  let cache: BlobCache
  beforeEach(() => {
    cache = freshCache()
  })

  it('a delete during a concurrent IDB read is not undone', async () => {
    await cache.set('p1', new Blob(['stale']))
    cache.clearMemory() // force the next get() down to IDB

    const reading = cache.get('p1')
    await cache.delete('p1')
    await reading

    cache.clearMemory()
    expect(await cache.get('p1')).toBeUndefined()
  })

  it('a set during a concurrent IDB read wins over the value being read', async () => {
    await cache.set('p1', new Blob(['stale']))
    cache.clearMemory()

    const reading = cache.get('p1')
    await cache.set('p1', new Blob(['fresh']))
    await reading

    expect(await text(await cache.get('p1'))).toBe('fresh') // memory
    cache.clearMemory()
    expect(await text(await cache.get('p1'))).toBe('fresh') // IDB
  })

  it('still reads through to IDB and repopulates memory', async () => {
    await cache.set('p1', new Blob(['v1']))
    cache.clearMemory()
    expect(await text(await cache.get('p1'))).toBe('v1')
    expect(await text(cache.getFromMemory('p1'))).toBe('v1')
  })
})
