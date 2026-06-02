import type { EngineError } from './contracts'

export class BackendError extends Error {
  readonly payload: EngineError
  readonly statusCode: number | undefined

  constructor(payload: EngineError, statusCode?: number) {
    super(payload.message)
    this.name = 'BackendError'
    this.payload = payload
    this.statusCode = statusCode
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
