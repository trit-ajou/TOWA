import { inject, type InjectionKey } from 'vue'
import type { FileAdapter } from '@/file-adapter'

const FILE_ADAPTER_KEY: InjectionKey<FileAdapter> = Symbol('FileAdapter')

export { FILE_ADAPTER_KEY }

export function useFileAdapter(): FileAdapter {
  const adapter = inject(FILE_ADAPTER_KEY)
  if (!adapter) {
    throw new Error('FileAdapter not provided. Call app.provide(FILE_ADAPTER_KEY, adapter) in main.ts.')
  }
  return adapter
}
