// BYOK (bring your own key): a cloud user may register their own FactChat key
// so AI jobs spend their provider credit instead of the shared platform key.
//
// The key stays in this browser only (per user) and travels solely inside AI
// job requests as runtime_context.session_provider_secrets — model_engine's
// credential resolver prefers it over the platform key. There is no server-side
// storage for user secrets.

const STORAGE_PREFIX = 'towa.byok.'

// One FactChat key covers both gateways: translation (openai_compatible chat)
// and inpaint (mindlogic images). These are the provider ids model_engine
// looks up for those stages.
const BYOK_PROVIDERS = ['openai_compatible', 'mindlogic'] as const

function storageKey(userId: string): string {
  return `${STORAGE_PREFIX}${userId}`
}

export function loadByokKey(userId: string | null | undefined): string | null {
  if (!userId) return null
  try {
    return localStorage.getItem(storageKey(userId)) || null
  } catch {
    return null // storage blocked (private mode etc.) — behave as unset
  }
}

export function saveByokKey(userId: string, key: string): void {
  const trimmed = key.trim()
  if (!trimmed) {
    clearByokKey(userId)
    return
  }
  localStorage.setItem(storageKey(userId), trimmed)
}

export function clearByokKey(userId: string): void {
  try {
    localStorage.removeItem(storageKey(userId))
  } catch {
    // nothing stored
  }
}

export function maskByokKey(key: string): string {
  return key.length > 4 ? `••••${key.slice(-4)}` : '••••'
}

/** Value for runtime_context.session_provider_secrets, or undefined to use the platform key. */
export function sessionProviderSecrets(key: string | null | undefined): Record<string, string> | undefined {
  if (!key) return undefined
  return Object.fromEntries(BYOK_PROVIDERS.map((provider) => [provider, key]))
}
