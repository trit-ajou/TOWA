import { ref, computed } from 'vue'

export type DeploymentMode = 'cloud' | 'standalone'

const _mode = ref<DeploymentMode>(
  (import.meta.env.VITE_DEPLOYMENT_MODE as DeploymentMode) ?? 'standalone'
)

export const DEPLOYMENT_MODE = computed(() => _mode.value)

/** For debug UI only — switch deployment mode at runtime */
export function setDeploymentMode(mode: DeploymentMode) {
  _mode.value = mode
}
