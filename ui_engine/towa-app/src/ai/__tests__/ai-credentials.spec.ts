import { beforeEach, describe, expect, it } from 'vitest'

import {
  DEFAULT_AI_CREDENTIALS,
  jobCredentialContext,
  loadAiCredentials,
  maskKey,
  saveAiCredentials,
  withPersonalKey,
} from '@/ai/ai-credentials'

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

describe('AI credential settings storage', () => {
  beforeEach(installLocalStorage)

  it('defaults to cloud (platform key) with no personal keys', () => {
    expect(loadAiCredentials('u1')).toEqual(DEFAULT_AI_CREDENTIALS)
    expect(loadAiCredentials(null)).toEqual(DEFAULT_AI_CREDENTIALS)
  })

  it('round-trips per user', () => {
    saveAiCredentials('u1', withPersonalKey({ ...DEFAULT_AI_CREDENTIALS, mode: 'personal', provider: 'gemini' }, 'gemini', ' g-key '))
    expect(loadAiCredentials('u1')).toEqual({ mode: 'personal', provider: 'gemini', keys: { gemini: 'g-key' } })
    expect(loadAiCredentials('u2')).toEqual(DEFAULT_AI_CREDENTIALS)
  })

  it('an empty key removes it', () => {
    const s = withPersonalKey(withPersonalKey(DEFAULT_AI_CREDENTIALS, 'factchat', 'f'), 'factchat', '  ')
    expect(s.keys.factchat).toBeUndefined()
  })

  it('migrates the earlier single BYOK key as a personal FactChat key', () => {
    localStorage.setItem('towa.byok.u1', 'old-key')
    expect(loadAiCredentials('u1')).toEqual({ mode: 'personal', provider: 'factchat', keys: { factchat: 'old-key' } })
    expect(localStorage.getItem('towa.byok.u1')).toBeNull()
  })

  it('ignores corrupted storage', () => {
    localStorage.setItem('towa.ai-credentials.u1', '{not json')
    expect(loadAiCredentials('u1')).toEqual(DEFAULT_AI_CREDENTIALS)
  })

  it('masks all but the last 4 characters', () => {
    expect(maskKey('sk-abcdef1234')).toBe('••••1234')
    expect(maskKey('abc')).toBe('••••')
  })
})

describe('jobCredentialContext', () => {
  it('cloud mode adds nothing (platform key, credits)', () => {
    expect(jobCredentialContext(DEFAULT_AI_CREDENTIALS)).toEqual({})
  })

  it('personal FactChat sends the key for both FactChat gateways', () => {
    const s = withPersonalKey({ ...DEFAULT_AI_CREDENTIALS, mode: 'personal', provider: 'factchat' }, 'factchat', 'k')
    expect(jobCredentialContext(s)).toEqual({
      metadata: { credential_mode: 'personal', personal_provider: 'factchat' },
      session_provider_secrets: { openai_compatible: 'k', mindlogic: 'k' },
    })
  })

  it('personal Gemini sends the key for the Gemini translation and image providers', () => {
    const s = withPersonalKey({ ...DEFAULT_AI_CREDENTIALS, mode: 'personal', provider: 'gemini' }, 'gemini', 'g')
    expect(jobCredentialContext(s)).toEqual({
      metadata: { credential_mode: 'personal', personal_provider: 'gemini' },
      session_provider_secrets: { translation_provider: 'g', nanobanana: 'g' },
    })
  })

  it('personal mode without a key for the chosen provider is reported as missing', () => {
    const s = withPersonalKey({ ...DEFAULT_AI_CREDENTIALS, mode: 'personal', provider: 'gemini' }, 'factchat', 'f')
    expect(jobCredentialContext(s)).toBeNull()
  })
})
