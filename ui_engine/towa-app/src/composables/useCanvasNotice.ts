// 캔버스 중앙 안내 토스트의 모듈-스코프 singleton 상태.
// showNotice(msg)를 호출하면 메시지가 표시되고, 같은 호출이 연속되면 페이드아웃 타이머만 리셋.
// 마지막 호출 이후 HOLD_MS 동안 노출, 이후 자동 페이드아웃.
import { ref } from 'vue'

const message = ref<string | null>(null)
let hideTimer: ReturnType<typeof setTimeout> | null = null
const HOLD_MS = 1500

export function useCanvasNotice() {
  function showNotice(msg: string) {
    message.value = msg
    if (hideTimer) clearTimeout(hideTimer)
    hideTimer = setTimeout(() => {
      message.value = null
      hideTimer = null
    }, HOLD_MS)
  }

  function dismissNotice() {
    if (hideTimer) {
      clearTimeout(hideTimer)
      hideTimer = null
    }
    message.value = null
  }

  return { message, showNotice, dismissNotice }
}
