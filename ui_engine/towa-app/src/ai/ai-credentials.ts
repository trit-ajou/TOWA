// How this user's AI jobs are paid for — interim operating policy (2026-09).
//
//   cloud     the platform key, billed to the account's credits. The admin may
//             require a cloud password (service_engine /auth/cloud-access).
//   personal  the user's own provider key (FactChat or Gemini); no credits.
//
// Settings and keys stay in this browser only (per user). A key travels solely
// inside AI job requests as runtime_context.session_provider_secrets; the
// server decides endpoints and models (model_engine/credentials/policy.py).

export type AiCredentialMode = 'cloud' | 'personal'
export type PersonalProvider = 'factchat' | 'gemini'

export interface AiCredentialSettings {
  mode: AiCredentialMode
  provider: PersonalProvider
  keys: Partial<Record<PersonalProvider, string>>
}

export const PERSONAL_PROVIDERS: { id: PersonalProvider; label: string; hint: string }[] = [
  { id: 'factchat', label: 'FactChat', hint: '번역·인페인팅 모두 FactChat 게이트웨이로 호출합니다.' },
  {
    id: 'gemini',
    label: 'Gemini (Google AI Studio)',
    hint: 'AI Studio에서 발급한 키. 인페인팅(이미지 생성)은 결제가 설정된 키가 필요합니다.',
  },
]

// model_engine provider ids each personal provider's key is used for.
const PROVIDER_SECRET_IDS: Record<PersonalProvider, string[]> = {
  factchat: ['openai_compatible', 'mindlogic'],
  gemini: ['translation_provider', 'nanobanana'],
}

export const DEFAULT_AI_CREDENTIALS: AiCredentialSettings = { mode: 'cloud', provider: 'factchat', keys: {} }

const STORAGE_PREFIX = 'towa.ai-credentials.'
const LEGACY_BYOK_PREFIX = 'towa.byok.' // single FactChat key from the first BYOK cut

function isProvider(value: unknown): value is PersonalProvider {
  return value === 'factchat' || value === 'gemini'
}

export function loadAiCredentials(userId: string | null | undefined): AiCredentialSettings {
  if (!userId) return clone(DEFAULT_AI_CREDENTIALS)
  try {
    const legacy = localStorage.getItem(LEGACY_BYOK_PREFIX + userId)
    if (legacy) {
      const migrated: AiCredentialSettings = { mode: 'personal', provider: 'factchat', keys: { factchat: legacy } }
      localStorage.setItem(STORAGE_PREFIX + userId, JSON.stringify(migrated))
      localStorage.removeItem(LEGACY_BYOK_PREFIX + userId)
      return migrated
    }
    const raw = localStorage.getItem(STORAGE_PREFIX + userId)
    if (!raw) return clone(DEFAULT_AI_CREDENTIALS)
    const parsed = JSON.parse(raw) as Partial<AiCredentialSettings>
    const keys: AiCredentialSettings['keys'] = {}
    for (const p of ['factchat', 'gemini'] as const) {
      const k = parsed.keys?.[p]
      if (typeof k === 'string' && k) keys[p] = k
    }
    return {
      mode: parsed.mode === 'personal' ? 'personal' : 'cloud',
      provider: isProvider(parsed.provider) ? parsed.provider : 'factchat',
      keys,
    }
  } catch {
    return clone(DEFAULT_AI_CREDENTIALS) // blocked or corrupted storage
  }
}

/** Throws if storage is unavailable, so the settings UI can say so. */
export function saveAiCredentials(userId: string, settings: AiCredentialSettings): void {
  localStorage.setItem(STORAGE_PREFIX + userId, JSON.stringify(settings))
}

export function withPersonalKey(
  settings: AiCredentialSettings,
  provider: PersonalProvider,
  key: string,
): AiCredentialSettings {
  const keys = { ...settings.keys }
  const trimmed = key.trim()
  if (trimmed) keys[provider] = trimmed
  else delete keys[provider]
  return { ...settings, keys }
}

export function maskKey(key: string): string {
  return key.length > 4 ? `••••${key.slice(-4)}` : '••••'
}

export interface JobCredentialContext {
  metadata?: { credential_mode: 'personal'; personal_provider: PersonalProvider }
  session_provider_secrets?: Record<string, string>
}

/**
 * runtime_context additions for an AI job. `{}` = cloud (platform key);
 * `null` = personal mode without a key for the chosen provider (don't send).
 */
export function jobCredentialContext(settings: AiCredentialSettings): JobCredentialContext | null {
  if (settings.mode !== 'personal') return {}
  const key = settings.keys[settings.provider]
  if (!key) return null
  return {
    metadata: { credential_mode: 'personal', personal_provider: settings.provider },
    session_provider_secrets: Object.fromEntries(PROVIDER_SECRET_IDS[settings.provider].map((id) => [id, key])),
  }
}

function clone(s: AiCredentialSettings): AiCredentialSettings {
  return { ...s, keys: { ...s.keys } }
}
