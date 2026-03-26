import { computed } from 'vue'
import { DEPLOYMENT_MODE, type DeploymentMode } from '@/config/deployment'

export type ModeTag = 'all' | 'cloud' | 'standalone'

export function useDeploymentMode() {
  const mode = computed<DeploymentMode>(() => DEPLOYMENT_MODE.value)
  const isCloud = computed(() => DEPLOYMENT_MODE.value === 'cloud')
  const isStandalone = computed(() => DEPLOYMENT_MODE.value === 'standalone')

  function isVisible(tag: ModeTag): boolean {
    if (tag === 'all') return true
    return tag === DEPLOYMENT_MODE.value
  }

  function filterByMode<T extends { mode: ModeTag }>(items: T[]): T[] {
    return items.filter((item) => isVisible(item.mode))
  }

  return { mode, isCloud, isStandalone, isVisible, filterByMode }
}
