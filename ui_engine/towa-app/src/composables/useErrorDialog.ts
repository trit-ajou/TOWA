// 사용자가 X 버튼을 눌러야 닫히는 dismissible 에러 dialog.
// AI 작업 실패 같이 메시지를 카피하거나 천천히 읽어야 하는 경우용.
// bitmappery의 showNotification(5초 자동 닫힘 + truncate)이 적합하지 않은 케이스에 사용.
import { ref } from 'vue'

export interface ErrorDialogEntry {
  id: number
  title: string
  message: string
}

const queue = ref<ErrorDialogEntry[]>([])
let nextId = 1

export function useErrorDialog() {
  function showError(title: string, message: string): void {
    queue.value = [...queue.value, { id: nextId++, title, message }]
  }

  function dismiss(id: number): void {
    queue.value = queue.value.filter((e) => e.id !== id)
  }

  function clear(): void {
    queue.value = []
  }

  return { queue, showError, dismiss, clear }
}
