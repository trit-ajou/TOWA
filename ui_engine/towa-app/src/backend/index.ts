import { MODEL_ENGINE_URL, SERVICE_ENGINE_URL } from '@/config/engines'

import type { AppBackend, AppBackendConfig, BackendAdapterMode } from './contracts'
import { createEmulatedAppBackend } from './emulated'
import { createRealAiJobsBackend, createRealAuthBackend, createRealFilesBackend } from './real'

// Master switch. Domain-level vars (VITE_UI_AUTH_BACKEND, etc.) act as overrides,
// but only when master is 'emulated' — see resolveDomainMode below.
const MASTER_MODE = parseBackendMode('VITE_UI_BACKEND_MODE', import.meta.env.VITE_UI_BACKEND_MODE)

const AUTH_MODE = resolveDomainMode(
  'VITE_UI_AUTH_BACKEND',
  import.meta.env.VITE_UI_AUTH_BACKEND,
  MASTER_MODE,
)
const AI_MODE = resolveDomainMode(
  'VITE_UI_AI_BACKEND',
  import.meta.env.VITE_UI_AI_BACKEND,
  MASTER_MODE,
)
const FILES_MODE = resolveDomainMode(
  'VITE_UI_FILES_BACKEND',
  import.meta.env.VITE_UI_FILES_BACKEND,
  MASTER_MODE,
)

export function defaultAppBackendConfig(): AppBackendConfig {
  return {
    authMode: AUTH_MODE,
    aiMode: AI_MODE,
    filesMode: FILES_MODE,
    serviceEngineUrl: SERVICE_ENGINE_URL,
    modelEngineUrl: MODEL_ENGINE_URL,
  }
}

export function createAppBackend(
  overrides: Partial<AppBackendConfig> = {},
): AppBackend {
  const config = {
    ...defaultAppBackendConfig(),
    ...overrides,
  }

  const emulatedBackend = createEmulatedAppBackend()
  return {
    auth: config.authMode === 'real'
      ? createRealAuthBackend(config)
      : emulatedBackend.auth,
    aiJobs: config.aiMode === 'real'
      ? createRealAiJobsBackend(config)
      : emulatedBackend.aiJobs,
    files: config.filesMode === 'real'
      ? createRealFilesBackend(config)
      : emulatedBackend.files,
  }
}

// Strict parse: only 'real' | 'emulated'. Anything else (typo, leftover value) throws at startup.
// Default for unset master is 'real' — production safety.
export function parseBackendMode(name: string, value: string | undefined): BackendAdapterMode {
  if (value === undefined || value === '') return 'real'
  if (value === 'real' || value === 'emulated') return value
  throw new Error(
    `[backend] invalid ${name}=${JSON.stringify(value)}. Expected 'real' or 'emulated'.`,
  )
}

// AND-gate: a domain runs 'real' unless master is 'emulated' AND the domain explicitly opts to 'emulated'.
// Rationale: in production (master=real) no leftover per-domain 'emulated' can silently mock traffic.
// In dev (master=emulated) you can pick which domains stay 'real' against live engines.
export function resolveDomainMode(
  name: string,
  raw: string | undefined,
  masterMode: BackendAdapterMode,
): BackendAdapterMode {
  if (raw === undefined || raw === '') {
    return masterMode
  }
  if (raw !== 'real' && raw !== 'emulated') {
    throw new Error(
      `[backend] invalid ${name}=${JSON.stringify(raw)}. Expected 'real' or 'emulated'.`,
    )
  }
  if (masterMode === 'real') {
    if (raw === 'emulated') {
      throw new Error(
        `[backend] ${name}=emulated is rejected because VITE_UI_BACKEND_MODE=real. ` +
        `Flip the master to 'emulated' to allow per-domain emulation.`,
      )
    }
    return 'real'
  }
  return raw
}

export * from './contracts'
export * from './emulated'
export * from './errors'
export * from './real'
