// Photoshop 표준 ux: 어떤 도구를 쓰고 있든 Space를 누른 채 드래그하면 임시로 Hand(MOVE) 도구로 전환.
// 떼면 이전 도구로 복원. bitmappery의 MOVE 도구가 viewport pan(가장자리 clamp 적용)을 그대로 처리한다.
//
// input/textarea/contentEditable에 포커스가 있을 땐 Space는 일반 글자 입력이므로 무시.
import { onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
// @ts-expect-error bitmappery JS module
import ToolTypes from '@bitmappery/definitions/tool-types'

export function useSpacePanModifier() {
  const store = useStore()
  let previousTool: string | null = null
  let spaceDown = false

  function isTextInputFocused(): boolean {
    const t = document.activeElement as HTMLElement | null
    if (!t) return false
    const tag = t.tagName
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || t.isContentEditable
  }

  function onKeyDown(e: KeyboardEvent) {
    if (e.code !== 'Space') return
    if (isTextInputFocused()) return
    if (spaceDown) { e.preventDefault(); return } // ignore key repeat (브라우저 스크롤 방지 위해 preventDefault는 매번)
    e.preventDefault()
    spaceDown = true
    const current = store.getters['bmp/activeTool']
    if (current === ToolTypes.MOVE) return
    previousTool = current
    const doc = store.getters['bmp/activeDocument']
    store.commit('bmp/setActiveTool', { tool: ToolTypes.MOVE, document: doc })
  }

  function onKeyUp(e: KeyboardEvent) {
    if (e.code !== 'Space') return
    if (!spaceDown) return
    spaceDown = false
    if (previousTool !== null) {
      const doc = store.getters['bmp/activeDocument']
      store.commit('bmp/setActiveTool', { tool: previousTool, document: doc })
      previousTool = null
    }
  }

  function onWindowBlur() {
    // 창 포커스 잃으면 (예: alt-tab) Space keyup 누락 → 복원
    if (spaceDown) {
      spaceDown = false
      if (previousTool !== null) {
        const doc = store.getters['bmp/activeDocument']
        store.commit('bmp/setActiveTool', { tool: previousTool, document: doc })
        previousTool = null
      }
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    window.addEventListener('blur', onWindowBlur)
  })
  onBeforeUnmount(() => {
    window.removeEventListener('keydown', onKeyDown)
    window.removeEventListener('keyup', onKeyUp)
    window.removeEventListener('blur', onWindowBlur)
  })
}
