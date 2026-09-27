import { beforeEach, describe, expect, it } from 'vitest'

import { clearByokKey, loadByokKey, maskByokKey, saveByokKey, sessionProviderSecrets } from '@/ai/byok'

// Minimal in-memory localStorage (vitest runs in node here).
function installLocalStorage() {
  const data = new Map<string, string>()
  ;(globalThis as { localStorage?: Storage }).localStorage = {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, String(v)),
    removeItem: (k: string) => void data.delete(k),
    clear: () => data.clear(),
    key: (i: number) => [...data.keys()][i] ?? null,
    get length() { return data.size },
  } as Storage
}

describe('BYOK key storage', () => {
  beforeEach(installLocalStorage)

  it('stores keys per user and trims whitespace', () => {
    saveByokKey('u1', '  sk-abc123  ')
    expect(loadByokKey('u1')).toBe('sk-abc123')
    expect(loadByokKey('u2')).toBeNull()
  })

  it('treats an empty key as clearing it', () => {
    saveByokKey('u1', 'sk-abc')
    saveByokKey('u1', '   ')
    expect(loadByokKey('u1')).toBeNull()
  })

  it('clears a stored key', () => {
    saveByokKey('u1', 'sk-abc')
    clearByokKey('u1')
    expect(loadByokKey('u1')).toBeNull()
  })

  it('returns null without a user', () => {
    expect(loadByokKey(null)).toBeNull()
  })

  it('masks all but the last 4 characters', () => {
    expect(maskByokKey('sk-abcdef1234')).toBe('••••1234')
    expect(maskByokKey('abc')).toBe('••••')
  })
})

describe('sessionProviderSecrets', () => {
  it('maps one key to both the translation and inpaint providers', () => {
    expect(sessionProviderSecrets('sk-1')).toEqual({ openai_compatible: 'sk-1', mindlogic: 'sk-1' })
  })

  it('is undefined without a key so the platform key is used', () => {
    expect(sessionProviderSecrets(null)).toBeUndefined()
    expect(sessionProviderSecrets('')).toBeUndefined()
  })
})
