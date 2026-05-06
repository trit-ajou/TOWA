import { inject, type InjectionKey } from 'vue'
import type { AppBackend } from '@/backend/contracts'

export const APP_BACKEND_KEY: InjectionKey<AppBackend> = Symbol('AppBackend')

export function useAppBackend(): AppBackend {
  const backend = inject(APP_BACKEND_KEY)
  if (!backend) {
    throw new Error('AppBackend not provided. Call app.provide(APP_BACKEND_KEY, backend) in main.ts.')
  }
  return backend
}
