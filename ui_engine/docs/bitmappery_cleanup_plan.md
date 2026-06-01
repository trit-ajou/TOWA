# bitmappery 2차 정리

## 작업 범위

본 2차 작업은 다음 두 갈래로만 한정한다.

1. **노출 점검 → 이슈 발행**: bitmappery에 이미 구현돼 있는데 TOWA에 노출 안 된 도구·옵션을 식별해 별도 이슈로 발행
2. **관련 없는 코드 삭제**: 위 항목과 무관한 미사용 코드·의존성·UI 컴포넌트 제거

**본 작업 범위 밖** (별도 이슈로 분리):
- bitmappery에 없는 신규 기능 구현 (텍스트 세로쓰기/외곽선/정렬, view 회전 등)
- 노출 후속 구현 (점검 결과로 발행된 이슈들은 본 PR이 아닌 각자의 PR로 진행)
- PDF export 같은 신규 export 기능

**선행/후속**: 본 2차 → #23(bitmappery 디렉토리 통합)

**관련 문서**: [canvas_ui_specs.md](../canvas_ui_specs.md), [TODO.md](../TODO.md) "정리 필요" 섹션

---

## 결정 로그

사용자와 합의된 사항만 시간순으로 기록.

### 2026-06-01

**작업 방식**
- 작업 순서: 본 2차 → #23
- 본 2차 산출물은 두 갈래로 분리: (a) 점검 결과 → 별도 이슈 발행 (b) 관련 없는 코드 삭제 → 본 PR
- 처리 정책: 완전 필요 없는 것 삭제 / 애매한 것 off / 안 노출된 기능은 별도 이슈로 분리해 점검·구현
- bitmappery에 없는 신규 구현은 본 2차 범위 밖

**삭제 확정** (본 PR에서 직접 제거)
- cloud SDK 3종 의존성 및 어댑터: `@aws-sdk/client-s3`, `dropbox`, `google-drive-service.ts`, `tiny-script-loader`
- cloud 관련 UI: `components/cloud-file-selector/`
- gif 관련: `gifshot`, `gif-creation-service.ts`, `compression.worker.ts`
- mirror 도구 (별도 도구로서). `transform.mirrorX/mirrorY` 속성 자체는 layer 데이터에 존속

**보존 확정**
- `psd.js` + `psd-import-service.ts` (만화 원본 포맷 가능성)
- `pdfjs-dist` + `pdf-import-service.ts` (PDF export는 본 작업 범위 밖, 별도 신규)

**노출 점검 → 이슈 발행 대상** (다음 라운드에 점검표 완성 후 이슈 발행)
- 안 노출된 비-도구 영역: layer-effects, selection-menu, layer-panel 액션 (다음 라운드 점검 후 확정)

### 2026-06-02

- **이슈 #56 발행** — "ui_engine: 캔버스 도구 기능 완전 구현 (미노출 + 신규)" 트래커
  - 포함: A. 미노출 도구(LASSO, SCALE, layer ROTATE), B. 미노출 옵션(BRUSH/ERASER/CLONE/FILL/DRAG/ZOOM/SELECTION/WAND), C. 신규 구현(view 회전, Free Transform, 텍스트 세로쓰기/외곽선/정렬)
  - 본 2차 정리(현 docs)는 #56과 별개. 본 2차에서는 "관련 없는 코드 삭제"만 다룸
  - 작업 방침: 본 이슈 전체 완료 후 한 번에 PR. 커밋만 sub-task 단위로 잘게

**도구 외 영역 점검 결과** (#56 D 섹션으로 추가됨)

UI 컴포넌트 17개 폴더 전부 towa-app import 0건 확인. 그중 살릴 항목을 다음 5개 그룹으로 구조화:

- **그룹 A. 레이어 패널 하단 통합** (포토샵 패턴): visibility / 이름변경 / 추가·삭제 / mask / duplicateLayer / mergeDown / opacity / blendMode
- **그룹 B. 상단 네비 패널 GUI 버튼**: undo / redo / 저장. 단축키는 이미 KeyboardService에서 동작 중, GUI만 추가
- **그룹 C. 우클릭 정책 (위치별 + 도구별, bitmappery context-menu 삭제)**:
  - 레이어 패널 위 → 우클릭한 레이어 대상 메뉴 (캔버스 도구 무관)
  - 캔버스 위 + 브러쉬 계열 → 기존 BrushOptionsPopover 유지
  - 캔버스 위 + 그 외 도구 → 선택 영역 클립보드 메뉴 (cut/copy/copyMerged/pasteAsNewLayer/clear)
- **그룹 D. layer-effects 선별**: opacity·blendMode 살림(그룹 A 흡수) / brightness·contrast·gamma·vibrance·invert·desaturate·threshold·duotone 삭제
- **그룹 E. 추가 삭제 확정** (만화 번역에 무관): selection save/load, commitEffects, copy/pasteLayerFilters, flattenImage, document-preview, file-import

본 2차 정리에서 삭제할 폴더 = 그룹 D·E의 항목 + 기존 확정 삭제분 (cloud SDK, gif, mirror, 무관 UI 컴포넌트 다수). 그룹 A·B·C의 노출 작업은 #56 D 섹션 후속 PR로 진행.

- **이슈 #58 발행** — "ui_engine: bitmappery 2차 정리 — 미사용 코드·의존성 삭제"
  - A. cloud SDK 3종 + tiny-script-loader + gifshot + google-drive/gif 서비스 + cloud-file-selector
  - B. mirror 도구 (Free Transform에 transform.mirrorX/Y는 보존)
  - C. towa-app import 0건이면서 #56 미활용 UI 컴포넌트 (file-menu, menus, notifications, dialog-window, modal, preferences, loader, resize-* 윈도우 4종, stroke-selection-window, selection-menu, document-preview, file-import)
  - D. commitEffects, flattenImage 진입점, layer-effects 미사용 필터(opacity·blendMode 외 전체) — UI·rendering·store 일관 삭제
  - **보존**: layer-effects/, layer-panel/ (#56 D-1이 활용), psd.js + psd-import-service, pdfjs-dist + pdf-import-service

**보강** (구현 단계에서 확인된 분류 정정)

- `services/aws-s3-service.ts`, `services/dropbox-service.ts` — A-1 의존성 짝(`@aws-sdk/client-s3`, `dropbox`)과 함께 삭제 (이슈 본문 미명시). cloud-file-selector·file-menu·file-import에서만 사용되어 dead.
- `workers/compression.worker.ts` + `services/compression-service.ts` — **gif와 무관, 보존**. 이슈 본문 A-4는 gif 카테고리로 잘못 묶었으나 실제로는 `factories/document-factory.ts`가 호출하는 `.bpy` 프로젝트 파일 JSON 압축 워커. gif 코드 0줄. 삭제 대상은 `services/gif-creation-service.ts` + `config/towa-features.ts`의 `FILE_GIF_EXPORT` flag만.
- cloud 정리 부수 효과 — `utils/cloud-service-loader.ts`, `mixins/cloud-service-connector.ts`, `definitions/storage-types.ts`(STORAGE_TYPES enum + FileNode type) 모두 cloud 전용이라 같이 삭제 (이슈 본문 미명시).
- **D-2 `flattenImage` 진입점은 자동 완료** — file-menu/header-menu 통째 삭제 시 진입점도 함께 사라짐. src 전체에 `flatten` 호출 0건 확인. 별도 commit 불필요.
- **D-3 layer-effects 미사용 필터 정리는 본 PR 범위 밖으로 보류** — `Filters` 타입·factory·rendering·worker·UI·wasm까지 도메인 일관 변경이 필요하고, 보존 대상인 `layer-effects/`를 #56 D-1이 어떻게 활용할지 확정된 뒤에 정리해야 충돌 위험 없음. `.bpy` 파일 호환성도 영향 — follow-up 이슈로 분리.

---

## 점검 자료 (raw data — 결정 아님)

이 섹션은 다음 라운드 논의를 위한 데이터. 항목 자체는 "이슈 발행 대상 후보"일 뿐이며, 결정은 위 결정 로그에서만 확정.

### 도구별 옵션 (bitmappery 제공)

#### BRUSH `[B]`
brushType(line/paintBrush/pen/calligraphic/connected/spray), brushSize, thickness(paintBrush), strokeAmount+smoothing(pen), opacity

#### CLONE (도장) `[S]`
sourceLayer 선택, brushSize, opacity, sourceCoordinate 리셋(Alt+Click)

#### ERASER `[E]`
eraserSize, thickness, opacity

#### FILL (페인트통) `[G]`
smartFill 토글

#### DRAG (객체 이동) `[V]`
left/top 직접 입력, reset, center, 마스크 드래그 모드

#### ZOOM `[Z]`
zoomLevel slider, bestFit / fitWindow / original 버튼

#### SCALE (도구 자체 미노출)
scale slider, reset, save(스케일을 source에 commit)

#### layer ROTATE (도구 자체 미노출, bitmappery ROTATE)
rotation slider(0~360), reset, 90도 좌/우 quick, 180도 flip

#### SELECTION (사각 선택) `[M]`
lockRatio + xRatio/yRatio, existing selection x/y/width/height 직접 편집

#### LASSO (자유 선택, 도구 자체 미노출)
자유곡선 선택. bitmappery에 ToolTypes.LASSO 존재

#### WAND (마법사) `[W]`
sampleMerged 토글, threshold 1-100

#### TEXT `[T]` — bitmappery 제공 옵션
text 본문, font, size+unit, lineHeight, letterSpacing, color

#### EYEDROPPER `[Alt+Click]`
TOWA `EyedropperHandler.vue`로 자체 구현 — 별도 점검 불필요

#### MOVE `[Space]`
TOWA `useSpacePanModifier`로 자체 구현 — 별도 점검 불필요

### UI 컴포넌트 (`bitmappery/src/components/`) — towa-app import 추적 필요

다음 라운드에 import grep으로 0건 확정되는 폴더는 삭제 후보:
- `file-menu/`, `menus/`, `notifications/`, `dialog-window/`, `modal/`, `preferences/`, `loader/`
- `resize-canvas-window/`, `resize-document-window/`, `new-layer-window/`, `grid-to-layers-window/`, `stroke-selection-window/`
- `selection-menu/`, `document-preview/`, `file-import/`, `layer-effects/`, `layer-panel/`

유지 확정:
- `document-canvas/`, `third-party/`, `ui/`

#22로 가린 상태 (#23 통합 시점에 삭제 예정):
- `toolbox/`, `tool-options-panel/`

### 도구 외 영역 (다음 라운드 점검 대상)

- `layer-effects/` + `rendering/operations/filters/`: blur, brightness, contrast, hue, saturation 등
- `selection-menu/`: feather, invert, expand, contract
- `layer-panel/` 액션: duplicate, merge down, group, blend mode, opacity, mask
- bitmappery 자체 history(undo/redo) — TOWA 페이지 단위 autosave와 충돌 가능성

---

## 미확정 (사용자 검토 필요)

현재 비어있음. 새 항목 생기면 여기에 추가 → 사용자 OK 후 결정 로그로 이관.
