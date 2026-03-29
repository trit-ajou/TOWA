import { MODEL_ENGINE_URL, SERVICE_ENGINE_URL } from '@/config/engines'

import type { AppBackend, AppBackendConfig, BackendAdapterMode } from './contracts'
import { createEmulatedAppBackend } from './emulated'
import { createRealAiJobsBackend, createRealAuthBackend } from './real'

const DEFAULT_AUTH_MODE = toBackendMode(import.meta.env.VITE_UI_AUTH_BACKEND)
const DEFAULT_AI_MODE = toBackendMode(import.meta.env.VITE_UI_AI_BACKEND)

export function defaultAppBackendConfig(): AppBackendConfig {
  return {
    authMode: DEFAULT_AUTH_MODE,
    aiMode: DEFAULT_AI_MODE,
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
  }
}

function toBackendMode(value: string | undefined): BackendAdapterMode {
  return value === 'real' ? 'real' : 'emulated'
}

export * from './contracts'
export * from './emulated'
export * from './errors'
export * from './real'
