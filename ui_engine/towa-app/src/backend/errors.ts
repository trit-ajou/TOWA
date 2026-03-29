import type { EngineError } from './contracts'

export class BackendError extends Error {
  readonly payload: EngineError

  constructor(payload: EngineError) {
    super(payload.message)
    this.name = 'BackendError'
    this.payload = payload
  }
}

export function ensureSessionKey(sessionKey?: string): string {
  if (sessionKey && sessionKey.trim()) {
    return sessionKey
  }
  throw new BackendError({
    code: 'session_key_required',
    message: 'sessionKey is required for this request',
    retryable: false,
    details: null,
  })
}
