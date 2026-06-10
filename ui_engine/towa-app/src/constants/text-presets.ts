// 텍스트 편집 UI(③ 편집·④ 상세 편집)에서 공유하는 크기·줄간격 프리셋.
// 값은 모두 px 절댓값. 줄간격 0은 "자동"(폰트 메트릭 기반 간격)을 의미.

interface Preset { label: string; value: number }

const toPresets = (values: number[]): Preset[] =>
  values.map((v) => ({ label: String(v), value: v }))

export const SIZE_PRESETS: Preset[] = toPresets([12, 16, 20, 24, 32, 40, 48, 64, 72])

export const LINE_HEIGHT_PRESETS: Preset[] = [
  { label: '자동', value: 0 },
  ...toPresets([20, 24, 28, 32, 40, 48, 60, 72]),
]
