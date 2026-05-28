import { ref } from 'vue'

// Single shared open state for every AddMenu instance.
// Only one popover should be visible at a time across the whole app.

export type AddMenuOwnerId = symbol

export const openOwner = ref<AddMenuOwnerId | null>(null)
export const popX = ref(0)
export const popY = ref(0)

let docListenerInstalled = false
export function installAddMenuDocListener(): void {
  if (docListenerInstalled) return
  docListenerInstalled = true
  window.addEventListener('click', (ev) => {
    if (openOwner.value == null) return
    const target = ev.target as HTMLElement | null
    if (target?.closest('[data-add-menu-trigger]')) return
    if (target?.closest('[data-add-menu-popover]')) return
    openOwner.value = null
  })
}
