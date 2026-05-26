import { ref, computed } from 'vue'

export type DeploymentMode = 'cloud' | 'standalone'

// Default 'cloud'. Standalone is disabled until LocalFileManager lands with Electron wrapping. See #37.
const _mode = ref<DeploymentMode>(
  (import.meta.env.VITE_DEPLOYMENT_MODE as DeploymentMode) ?? 'cloud'
)

export const DEPLOYMENT_MODE = computed(() => _mode.value)

/** For debug UI only — switch deployment mode at runtime */
export function setDeploymentMode(mode: DeploymentMode) {
  _mode.value = mode
}
