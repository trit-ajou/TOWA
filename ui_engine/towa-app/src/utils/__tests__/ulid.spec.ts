import { describe, expect, it } from 'vitest'

import { createUlid, isCanonicalUlid } from '@/utils/ulid'

describe('ULID utilities', () => {
  it('creates canonical ULIDs', () => {
    const id = createUlid()

    expect(id).toHaveLength(26)
    expect(isCanonicalUlid(id)).toBe(true)
  })

  it('creates unique ULIDs across repeated calls', () => {
    const ids = new Set(Array.from({ length: 64 }, () => createUlid()))

    expect(ids.size).toBe(64)
  })
})
