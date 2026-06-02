# Changelog

작업 단위 완료 시 기록. KST 기준.

---

## 2026-06-02

### 20:18 — PageTransitionOverlay thumbnail이 캔버스 영역을 채우지 못함
- 증상: 페이지 로딩 시 overlay 안의 thumbnail 미리보기가 캔버스 영역 가운데에 *작은 박스*로만 표시. 사용자가 서버에 올려서 확인한 케이스
- Root cause: thumbnail blob의 natural pixel size가 `captureThumbnail`의 상한(200×300)으로 작은데, `<img>` 클래스가 `max-h-full max-w-full object-contain`만 갖고 있었음. `max-w-full`은 "부모를 초과 X" 제약일 뿐 "부모를 채워" 제약은 아니라 natural size 그대로 표시됨
- 수정: img 클래스를 `w-full h-full object-contain`으로. object-contain이 doc 비율을 유지하며 캔버스 영역을 가득 채움

### 19:17 — AI 입력으로 doc 합성이 아닌 원본 이미지 사용 (detect/translate OCR 품질 차이 fix)
- 증상: 사용자 보고 "검출(detect) OCR이 번역(translate) OCR보다 명백히 좋다". 검출/번역이 서로 다른 텍스트박스를 만들고 번역은 자체적으로 OCR을 다시 돌리는 동작
- Root cause 분석:
  - model_engine `OPERATION_STAGE_NAMES[translate] = ["text_detection", "ocr", "translation"]` — translate는 매번 처음부터 detect+OCR을 수행. ui_engine이 보낸 `document.text_blocks`는 ocr stage의 `replace_text_blocks` patch가 덮어쓰므로 재활용 경로 없음 (의도된 파이프라인)
  - detect/translate의 text_detection/ocr config는 동일 (`CRAFT_TEXT_DETECTION_MODEL_ID` + `MANGA_OCR_MODEL_ID`). 즉 모델 자체 차이 X
  - 차이의 원인은 입력 이미지: `useAiActions.buildInput`이 `createSyncSnapshot(activeDocument)`로 visible 레이어 합성을 보냈음. detect 후 페이지에는 OCR 원문이 그려진 텍스트 레이어가 누적되고 (`render-service.ts` line 90: text.value 비었을 때 `meta.original` fallback 렌더링), 그 다음 translate를 돌리면 "원본 + 렌더된 OCR 원문 텍스트"가 합성된 노이즈 큰 이미지가 다시 입력으로 들어가서 두 번째 OCR이 망가짐
- 수정 (`useAiActions.ts`, `usePageLoader.ts`):
  - 모든 AI operation이 `originalImage` Blob을 그대로 입력으로 사용. `createSyncSnapshot` + `resizeImage` + `canvasToBlob` 합성 경로 제거
  - inpaint도 일단 원본 입력 — 부분 inpaint(AI 지우개)처럼 편집 상태를 보내야 하는 도구는 별도 스콥에서 추가
  - `usePageLoader`에 `getOriginalImage(pageId, fileAdapter)` helper export (세션 캐시 + snapshot fallback). `savePage` 안의 중복 로직도 이걸 사용
- 검증:
  - typecheck PASS, unit test 3 spec/37 tests PASS (`result-applier.spec.ts`의 `@tanstack/vue-query` import 에러는 stash 후에도 동일 — 기존 환경 문제)
  - API 직접 비교(UI 우회): 동일 원본 이미지(`samples/dlsite/sample.jpg`)로 `POST /v1/jobs` 두 번 호출. detect와 translate의 ocr stage 출력(`document_patch.patches[op=replace_text_blocks]`) **12/12 블록 bbox·텍스트 완전 일치** → 가설 확정. (translate job 자체는 translation provider unavailable로 failed지만 그 앞의 ocr 단계까지는 succeeded라 비교 가능)
  - Playwright e2e 12 tests: 11 PASS / 1 flaky(01-entry-flow의 helper navigation race, 단독 재실행 시 PASS, 변경 범위 외). savePage 회귀 범위 03/04/07 전부 PASS
- 잔여: 사용자 manual 검증으로 실제 UI 경로에서 detect → translate 시 OCR 결과가 같아지는지 최종 확인 필요

### 13:21 — PR #59 self-review 후속 fix (Critical #1/#3, Important #5; #2는 후속 이슈 #60)
- **#1 savePage silent return → throw** (`usePageLoader.ts`): `!doc`/`!thumbnail`/`!originalImage`/`!page` 4 경로가 silent return이었음. `doSave`는 예외 없이 정상 완료로 인지하고 `dirty.value=false`로 리셋 → 새 페이지의 originalImage가 캐시에 없는 상태에서 편집 + 페이지 전환 시 변경분 영구 손실 가능. throw로 바꿔 `doSave` catch가 dirty 유지하도록
- **#3 사전 조건 실패 시 사용자 toast** (`usePageLoader.ts`): 4 throw는 fileAdapter try-catch 밖이라 `showError`가 호출되지 않음. AI active path에서 false success 토스트가 뜨는 케이스. `failSave` helper로 사용자 메시지 + throw 묶음
- **#5 ProjectView `onBeforeUnmount`에도 `resetPageLoaderState()`** (`ProjectView.vue`): `onBeforeRouteLeave`는 둘 다 호출, `onBeforeUnmount` 안전망은 cleanup 루프만 호출했음. 비-router unmount(테스트 등) 시 `currentLoadedPageId` stale 가능
- **#2 follow-up 이슈 발행** ([#60](https://github.com/trit-ajou/TOWA/issues/60)): `useAutoSave` singleton 결합. 다중 인스턴스 window listener 이중 등록 문제. 큰 리팩토링이라 별도 처리
- 검증: typecheck PASS, e2e 6/6 PASS

### 08:24 — ProjectView unmount cascade fix (먹통 재발 케이스)
- 증상: 라이브러리로 돌아갈 때 간헐적으로 `insertBefore NotFoundError` + `parentNode null` 콘솔 에러. 트레이스는 `at <RouterView> at <ProjectView onVnodeUnmounted=...> at <RouterView> at <App>`. KeepAlive 제거(07:45 freeze fix) 이후에도 *별도 트리거*로 같은 증상이 남아 있었음
- Root cause: `ProjectView.onBeforeUnmount`의 `while (activeDocument) closeActiveDocument` 루프가 unmount 진행 중에 실행. `bmp/closeActiveDocument`는 `state.documents`를 splice + `flushLayerRenderers` + resource-manager의 blob URL dispose cascade를 발사하는데, 이게 inner router-view가 자식(EditorTab/DetailEditorTab) DOM을 정리하려는 시점과 race
- 수정: cleanup을 `onBeforeRouteLeave`로 옮김. route를 떠나는 시점엔 ProjectView/자식이 아직 mount 상태라 cascade가 정상 처리. child route 전환(편집 ↔ 상세편집)에서는 호출되지 않으므로 docs가 잘못 닫히지 않음. `onBeforeUnmount`는 비-router 경로(테스트 등) 안전망으로 idempotent 유지
- 검증: typecheck PASS, e2e 6/6 PASS, 사용자 manual 검증 OK (잔여 케이스는 재현 시 핫픽스)

### 07:53 — Thumbnail 비율 깨짐 fix (viewport → doc snapshot)
- 증상: 페이지 저장 후 일부 페이지의 썸네일이 원본 doc 비율을 따르지 않고 가로/세로가 달라짐. `PageThumbnail`의 `aspect-[2/3]` 컨테이너 + `object-cover`와 결합되어 만화 가운데 영역만 잘려 보임. 사용자 스크린샷에서 작업/저장된 페이지(4p~7p)만 비율이 깨져 보임 (저장 trigger된 페이지만 잘못 갱신)
- Root cause: `usePageLoader.captureThumbnail`이 `zCanvas.getElement()`의 *viewport* 캔버스를 그대로 캡처. viewport는 캔버스 영역 div 크기에 맞춰진 가로 박스라 세로 만화 doc과 비율이 다름
- 수정: `result-applier.ts` background 경로가 이미 쓰던 패턴 그대로 `createSyncSnapshot(doc)`으로 교체. `doc.width × doc.height`의 offscreen canvas에 모든 layer를 렌더하므로 doc 원본 비율 정확 유지. 미사용된 `getCanvasInstance` import 정리
- 기존에 잘못 저장된 thumbnail은 다음 저장 시점에 자동 갱신됨

### 07:45 — 편집 ↔ 상세편집 탭 swap freeze fix (vuejs/core#8509)
- 증상: 편집 탭에서 텍스트 추가/삭제 작업 후 상세편집 ↔ 편집 탭을 왕복하면 UI가 먹통(이전 탭이 안 사라지고 새 탭도 안 mount). 콘솔에 `Failed to execute 'insertBefore' on 'Node'` NotFoundError + `parentNode null` / `subTree null` Vue warn이 `usePageLoader.ts:193` (invalidateQueries) 트레이스에서 발생
- Root cause: `ProjectView`의 `<keep-alive :include="['ProjectHomeTab']">` wrapper. EditorTab/DetailEditorTab은 cache 대상이 아니지만 KeepAlive wrapper *안에* 있다는 사실만으로 [vuejs/core#8509](https://github.com/vuejs/core/issues/8509) 증상(KeepAlive 안 자식이 외부로 Teleport한 DOM이 swap 시 stale하게 남아 다음 mount에서 insertBefore mismatch)이 발생. include 여부와 무관하게 wrapper 자체가 자식 lifecycle을 통제하기 때문
- 잘못된 시도(되돌림): `<Teleport defer>` 제거. defer는 ProjectView template에서 `#towa-right-panel`이 router-view 뒤에 있어 EditorTab setup 시점엔 target이 DOM에 없는 문제를 해결하던 필수 prop이라 e2e 5건 회귀
- 수정: `ProjectView`의 KeepAlive 제거 → `<router-view />` 단순 사용. ProjectHomeTab 캐시 효과는 TanStack Query 캐시가 즉시 hit하므로 비용 거의 0. `onActivated/onDeactivated` 사용 코드 없음 확인
- 안전망: `useAutoSave`에 `onBeforeRouteLeave`/`onBeforeRouteUpdate`로 save를 await — `onUnmounted`에서 fire-and-forget으로 doSave를 돌리면 invalidateQueries가 unmount 진행 중인 컴포넌트에 reactive update를 흘려 router-view swap DOM race를 악화시킴
- 검증: 전체 e2e 12/12 PASS (07-autosave-regression 6/6 포함), typecheck PASS, 사용자 manual 검증 OK

### 00:50 — AI 결과 적용에 active/background 분기 도입
- 잠재 버그: AI job은 최대 5분 polling. 그 동안 사용자가 다른 페이지로 이동하면 `applyAiJobSnapshotToCurrentPage`의 `bmp/addLayer` mutation이 `state.documents[activeIndex]`(=새 활성 doc)에 layer를 박고, 그 다음 `savePage`가 활성 doc을 직렬화해 **시작 페이지 ID**로 PUT → 다른 페이지의 binary가 시작 페이지 자리에 덮어쓰기 + AI 결과 layer가 엉뚱한 doc에 들어가는 데이터 손실
- 수정: `result-applier.ts` 진입 시 `store.state.editor.selectedPageId === pageId` 확인
  - **active 경로**: 기존 흐름 유지 + `markDirty()` + `saveImmediately(pageId)`로 doSave 경유 (dirty 자동 reset, 실패 시 dirty 유지로 다음 자동저장에서 재시도)
  - **background 경로**: `fileAdapter.getPageSnapshot(pageId)` → `DocumentFactory.fromBlob` → 임시 doc.layers에 push (store mutation X) → `createSyncSnapshot`으로 offscreen thumbnail 캡처 → `fileAdapter.savePageSnapshot` 직접. activeDocument 비의존
  - 백그라운드 적용 성공 시 `onBackgroundApplied(pageIndex)` 콜백 → bitmappery showNotification으로 "N페이지 AI 결과 적용 완료" 토스트
- `useAiActions` / `AiToolbar`: `useFileAdapter()` + `useAutoSave()`의 markDirty/saveImmediately를 result-applier에 전달. `usePageLoader.savePage` 의존 제거
- result-applier.ts 시그니처 변경 (`savePage` → `markDirty + saveImmediately + fileAdapter + onBackgroundApplied`). spec도 stub 함께 업데이트
- AI dirty marking 누락 부수 fix: `bmp/addLayer` 등은 history에 들어가지 않아 useAutoSave의 saveState subscriber가 fire 안 함. AI 적용 직후 markDirty 명시로 dirty=true → saveImmediately로 정상 reset. 실패 시 dirty 유지 → autosave timer가 재시도
- 별도 이슈로 발행: 프로젝트 생성 시 일괄 AI 적용 (#57) — 이 인프라 위에 얹는 후속 작업
- 검증: typecheck PASS, vitest 42/42 PASS, Playwright e2e 10/10 PASS

---

## 2026-06-01

### 23:55 — #39 cross-document layer-id 충돌 fix
- 증상: 다중 페이지 프로젝트에서 페이지 N에 텍스트박스를 추가하고 저장 없이 페이지 N+1로 넘어가면, N+1의 캔버스에 N의 텍스트박스가 잔여로 그려진 채로 보임. 우측 패널은 "텍스트 블록이 없습니다"(=`activeDocument.layers`에는 없음) 라 데이터·렌더 mismatch
- Root cause: `LayerFactory.deserialize`가 stored `layer.i`를 그대로 사용해 LayerFactory.create로 전달. 그런데 bitmappery의 UID_COUNTER는 page session 단위 module-level — 여러 페이지를 같은 세션에서 deserialize하면 두 doc이 동일한 layer.id (e.g. `"layer_2"`)를 갖게 됨. `renderer-factory.ts`의 rendererCache와 `document-canvas.vue`의 layerPool 모두 layer.id 단일 key라 두 doc이 같은 sprite를 공유 → 새 doc의 layer를 그릴 자리에 이전 doc의 sprite가 박혀 잔여 paint가 살아남음. document-canvas.vue:195의 "Atomic swap: don't pre-flush" 주석이 이 가정을 명시 (bitmappery 단일 doc 사용에서는 ID 충돌이 발생 안 함)
- 수정:
  - `bitmappery/src/factories/layer-factory.ts`: `deserialize`에서 `id: layer.i` 인자 제거 → LayerFactory.create가 UID_COUNTER로 새 unique ID 할당. 외부 reference는 `layer.meta.blockId`를 쓰니 영향 없음
  - `ui_engine/towa-app/src/composables/usePageLoader.ts switchPage`: splice 전 outgoing doc의 layer마다 `flushLayerRenderers(layer)` 명시 호출 — bitmappery의 `closeActiveDocument` (document-module.ts:114) 와 동일 패턴. ID 충돌이 없어도 cache 정리 안전망
- 검증: Playwright e2e 신규 4번째 회귀 시나리오로 "두 페이지의 layer.id 집합이 disjoint"인지 자동 검증 + 사용자 manual 재현 절차 정리. 전체 e2e 10/10 PASS

### 23:17 — #39 사용자 검증 라운드 fix 4건
- **thumbnail 404 race**: `usePageLoader.savePage`에서 invalidate→refetch 대신 새 thumbnail Blob을 `thumbnailCache.set` + `qc.setQueryData`로 직접 cache에 주입. service-engine이 저장 직후 thumbnail endpoint에 짧게 404를 주면 query data가 null로 collapse돼 영구적으로 빈 상태가 되던 버그 제거
- **brush race**: `useAutoSave.doSave` 진입 시 active layer renderer의 `storePaintState()`를 `await` 으로 flush. bitmappery의 brush stroke 완료는 `canvasToBlob × 2` async + 1초 batch debounce가 끼어 historyIndex 증가가 지연됨. 그 사이 페이지 이동/Ctrl+S가 떨어지면 `dirty.value=false`로 bail되어 자동저장 누락이 발생. bitmappery의 `undo` action이 이미 쓰는 패턴(`history-module.ts:119-122`)을 그대로 차용
- **action-based dirty trigger**: `useAutoSave`가 `historyIndex` 값 변화 watch 대신 `bmp/saveState` mutation을 `store.subscribe`로 listen. 페이지 진입 시 bitmappery의 `activeDocument` watch가 호출하는 `resetHistory()`가 historyIndex를 -1로 강제 reset해 거짓 dirty가 트리거되던 문제 제거. + bitmappery `layer-renderer.storePaintState` 끝에서 `forceProcess()` (=enqueueState queue flush) 호출 — brush/eraser/fill 같은 mouseup-based action은 즉시 commit해 Photoshop/Krita식 행동 단위 history로 맞춤 (텍스트/slider 같은 keystroke 기반 입력의 1초 batching은 유지)
- **per-page "저장 안 됨" 뱃지**: `useAutoSave`의 `dirty` + `dirtyPageId`를 module-scope ref로 끌어올려 `useDirtyState()`로 export. PageSidePanelItem + PageThumbnail 좌상단에 노란 뱃지(`bg-towa-warning`). `document.title`의 `* ` prefix는 시인성이 낮아 제거
- 관련 파일: ui_engine/towa-app/src/composables/useAutoSave.ts, usePageLoader.ts, components/editor/PageSidePanelItem.vue, components/project/PageThumbnail.vue, bitmappery/src/rendering/actors/layer-renderer.ts

### 14:22 — FileAdapter sync 레이어 재구성 (#39)
- 배경: `projects` / `folders` / `pages` / `trash` 같은 서버 상태를 TanStack Query 기반 캐시 레이어로 이관하고, 페이지 binary·thumbnail에 prefetch + 영속 캐시 도입. PoC 단계의 단일 사용자/세션 가정으로 LWW 운영
- **Phase 1 — 캐시 인프라**: `@tanstack/vue-query` + `@tanstack/query-persist-client-core` 설치. user-namespaced cache DB (`towa-cache-${userId}`) + 일반화된 `BlobCache(storeName, maxMemory, maxIDB)` + thumbnail-cache store. `QueryClient` (staleTime: Infinity, retry 3회 1s/2s/4s, 401 bail) + IDB persister
- **Phase 2 — composable 신규 + Vuex 4개 모듈 제거**: `useProjects/useFolders/usePages/useTrash` + 공유 `queryKeys`. 모든 사용처(view·component·composable·result-applier) 마이그레이션. `result-applier`는 store가 아닌 `queryClient` prop으로 `pages` cache update
- **Phase 3 — Thumbnail + prefetch + 점진적 표시**: `useThumbnailUrl(pageId)` (Object URL 라이프사이클 컴포넌트 단). `usePageBinaryPrefetch` (활성 ±3 sliding window + 프로젝트 전체 1GB hard cap). `PageTransitionOverlay`가 입장 페이지 thumbnail을 spinner 아래 깔아 점진적 표시
- **Phase 4 — Auth & Sync**: `BackendError.statusCode` 추가 + 모든 throw site에 response.status 전달. 글로벌 401 handler가 query/mutation cache 구독 → auth/logout + `/login?expired=1` redirect + 안내. `listPageSummaries`도 404 흡수 → ProjectView가 not-found 시 라이브러리 redirect. 라이브러리/프로젝트 헤더에 새로고침 버튼. window focus 시 active project pages invalidate. 로그인 직후 `invalidateQueries()` 전체
- **Phase 5 — 저장 모델**: `useAutoSave`에 capture-phase Ctrl/Cmd+S → `saveImmediately`. dirty 상태일 때 document.title prefix `* ` 자동 토글. bitmappery `keyboard-service.ts`의 Ctrl+S Save Document 모달 차단. `savePageSnapshot`은 `withPushRetry` (1s/2s/4s, 3회, 401 short-circuit)로 wrap; 최종 실패 시 기존 AI 에러 다이얼로그로 안내
- **Phase 6 — Playwright e2e**: 6개 카테고리(library/cache/save/persist/auth/user-isolation) spec + helpers + README + vite.config의 e2e 제외. unit 42/42 PASS, typecheck PASS. PASS 확인은 service_engine + db docker 구동이 필요해 사용자 환경에서 별도 진행
- 명세 외 작은 결정(사후 보고): @tanstack/query-persist-client-core 패키지명, 자동 저장 debounce 30초 유지(Phase 0 분석), page-cache L1=7/L2=1000 (sliding window 7+byte cap 1GB), 세션 만료 임박 토스트는 expiresAt 데이터 부재로 401 redirect만 구현
- 관련: 후행 #23 bitmappery 1단계 통합 (본 PR 머지 후)

---

## 2026-05-29

### 22:30 — PaintGuard 오발동 핫픽스
- 배경: 사용자 검증 중 두 가지 오동작 발견. (1) brush 활성 상태에서 AI 드롭다운 버튼을 눌러도 "이 레이어에 그림을 그릴 수 없습니다" 토스트가 뜸. (2) 편집(역자) 모드에는 레이어 선택창 자체가 없는데도 보호 토스트가 뜸
- `PaintGuard.vue`: `area.contains(e.target)` 범위가 너무 넓어 캔버스 위에 떠 있는 툴박스/AI 버튼 클릭도 paint 시도로 잡혔음. `target.closest('.canvas-wrapper')` 안 + `button/input/select/textarea/[role=button]` 바깥일 때만 안내 표시하도록 좁힘
- `EditorTab.vue`: 편집 모드는 텍스트 도구 위주이고 레이어 선택 UI가 없으므로 `<PaintGuard />` 및 import 제거. 상세편집(`DetailEditorTab.vue`)에서만 유지
- 검증: 사용자가 실제 브라우저에서 (1) AI 버튼 클릭 시 토스트 없음 (2) 편집 모드 보호 토스트 없음 (3) 상세편집 캔버스 직접 클릭 시 기존 안내 동작 유지 확인

### 00:31 — 편집 화면 UI 개편 후속: 단축키·도구 옵션·레이어 가드 (#22)
- 배경: #22 1차분(35ef6a3 main 머지)에서 toolbox/패널/AI 드롭다운/Zoom 신규 구현까지 끝. 이번 후속에서 사용자 검증 통해 빠진 항목 채움
- **Hand 도구 Space modifier** (`composables/useSpacePanModifier.ts`): 어떤 도구를 쓰고 있든 Space 누른 채 드래그하면 임시로 MOVE 도구로 전환, 떼면 복원. input/textarea focus 시 무시, window blur 시 자동 복원
- **AI 진행 알림 오버레이** (`AiProgressOverlay.vue`): `useAiActions`의 `loading` ref를 module-scope singleton으로 끌어올려 여러 컴포넌트가 같은 상태 구독. 캔버스 영역 우상단에 spinner + 작업명(검출/인페인팅/번역). `pointer-events-none`으로 캔버스 조작 통과
- **FG/BG swap + 도구 단축키** (`store/modules/editor.ts`, `CanvasToolbox.vue`): editor store에 `backgroundColor` state 추가. `X` 키 또는 툴박스 작은 화살표로 `bmp/activeColor` ↔ `editor/backgroundColor` 교체. BG swatch가 실제 색으로 표시. `Z V M W B S E G I T R D` 도구 단축키 일괄 매핑 (e.code 기반이라 IME 한글 무관)
- **우클릭 브러쉬 옵션 팝업** (`BrushOptionsPopover.vue`): brush/clone/eraser 활성 + 캔버스 우클릭 → 크기 slider + 종류 7가지 popover. capture phase로 bitmappery interaction-pane보다 먼저 가로채. Esc / 바깥 클릭 닫힘. Zoom 도구는 우클릭=줌아웃이 우선
- **Alt+클릭 스포이드** (`EyedropperHandler.vue`): 어떤 도구든 Alt+클릭으로 캔버스 픽셀의 색을 `getImageData`로 추출해 `editor/backgroundColor`에 set (포토샵 패턴). CSS 좌표 → internal pixel 좌표 변환으로 HiDPI/zoom 보정
- **페이지 nav 단축키 Q/W → ←/→**: W가 spec(canvas_ui_specs)의 wand 도구 단축키와 충돌 → ArrowLeft/ArrowRight로 옮김. TranslationPanel의 kbd 라벨도 ←/→로 갱신
- **비-커스텀 레이어 paint 가드 토스트** (`PaintGuard.vue`, `CanvasNoticeToast.vue`, `useCanvasNotice.ts`, `utils/layer-classify.ts`): `classifyLayer`/`isPaintableLayer`를 utils로 추출. brush/eraser/clone/fill + active layer가 텍스트/인페인트/원본 그룹일 때 capture mousedown으로 안내 메시지 push. 캔버스 중앙에 200ms fade로 표시, 마지막 호출 이후 1.5초 hold → fade out. 그림 동작 자체는 막지 않음 (bitmappery 무시 동작에 맡김)
- `TODO.md` / `Project_Plan.md`: U6(백그라운드 단축키 가드)는 라우터 가드(`router/index.ts:67`)로 이미 처리되어 있어 완료 표시. `Ctrl+T` 레이어 transform은 Project_Plan.md U7로 분리 후속 작업
- 검증: Playwright로 AI overlay 시각 확인 + 사용자 손 테스트로 swap/popover/eyedropper/paint guard 동작 확인. dev 서버 HMR 에러 없음

## 2026-05-28

### 00:13 — backend mode 단일 master switch + AND-gate (#28)
- 배경: `VITE_UI_AUTH_BACKEND` / `VITE_UI_AI_BACKEND` / `VITE_UI_FILES_BACKEND`가 root `.env`·`.env.local`·`towa-app/.env`에 분산. 배포 .env가 emulated로 남아 있어 production이 mock에 머무는 silent drift 발생
- `ui_engine/towa-app/src/backend/index.ts`: master switch `VITE_UI_BACKEND_MODE` 도입. AND-gate semantics — master=real이면 어떤 per-domain `emulated` override도 startup throw. master=emulated일 때만 per-domain override 유효 (`real`로 일부 도메인만 실제 엔진과 붙여보기 가능). `real`/`emulated` 외 값은 strict parse로 throw
- `docker-compose.yml` ui-engine: `VITE_UI_BACKEND_MODE` 추가, per-domain 변수는 빈 default로 passthrough만
- `.env.deploy` 부활 (root, tracked): `VITE_UI_BACKEND_MODE=real`로 production default 명시. `deploy.sh` fallback 다시 동작
- `scripts/set-backend-mode.sh real|emulated`: root `.env`/`.env.local`/`.env.deploy`/`towa-app/.env` 일괄 갱신
- `DEPLOY.md`, `towa-app/src/backend/README.md`, `towa-app/.env.example`, `smoke/rest/README.md` 갱신
- `deploy.sh`: 같은 SHA에서 build 후 service down이면 `.deploy-stuck-at-sha` marker 남기고 다음 cron부터 rebuild skip — silent 5분 rebuild loop 방지. SHA 진행되면 marker 자동 해제. 실패 서비스 로그를 자동 dump
- `set-backend-mode.sh real` 실행 시 per-domain `=emulated` 잔존 line이 있으면 warning + 위치 출력 (자동 수정은 안 함; throw 의도는 유지)
- `parseBackendMode`/`resolveDomainMode`를 pure function으로 export, `backend-mode.spec.ts` 15 케이스 추가 (master×per-domain 8 조합 + invalid 케이스)
- 검증: dev 서버 + docker container 양쪽 — (1) master=real → boot OK (2) master=real + AI=emulated → throw 메시지 정확히 출력 (3) master=emulated + AI=real → boot OK. `.env.deploy → .env` fallback도 별도 clone 환경에서 확인. vitest 15/15 통과

## 2026-05-26

### 00:36 — 홈 라우팅 개편: 로그인 시 라이브러리 직행 (#20)
- `router/index.ts` `beforeEach`에 landing 가드 추가. `to.name === 'landing'` 이고 `!isCloud || isLoggedIn` 이면 `library`로 redirect. Landing은 cloud + 미로그인 전용
- `components/common/AppNavbar.vue` `goHome` / `goToLibraryPath`: cloud + 미로그인일 때만 `/`, 그 외 모두 `/library`로 push
- 검증: Playwright로 (1) standalone `/` → `/library`, (2) cloud + 로그인 `/` → `/library`, (3) cloud + 미로그인 `/` → landing 유지 확인

## 2026-05-14

### 10:27 — 페이지 전환 시 캔버스 가로 비율 깨짐 fix
- 증상: 첫 진입 후 페이지 전환하면 canvas dimension이 fit-to-window 비율을 잃고 가로로 늘어남 (예: 583×875 → 1010×875). 페이지 placeholder가 화면 중앙에 작게 보이고 나머지가 빈 공간
- 원인: `usePageLoader.loadPage`가 `store.commit('bmp/addNewDocument')` 직후 `window.dispatchEvent(new Event('resize'))`를 호출 → `bitmappery.vue` handleResize 트리거 → `setToolOptionValue(ZOOM, level=1)`으로 zoom 강제 reset → activeDocument watcher의 `calcIdealDimensions(true)`가 fit-to-window 값으로 재설정하기 직전에 캔버스가 비율 깨진 상태로 commit됨
- `composables/usePageLoader.ts`: dispatchEvent 한 줄 제거. v-show false→true 토글 시점의 layout 재계산은 `views/ProjectView.vue:40-44`의 별도 watcher가 이미 같은 dispatchEvent를 호출하므로 잉여
- 검증: Playwright로 5회 연속 페이지 전환 (2p→4p→6p→1p→7p) 시 canvas attr 583×875 유지 확인

### 09:47 — 페이지 전환 시 캔버스 깜빡임 제거
- 증상: 페이지 전환 시 1~2 프레임 동안 캔버스가 cleared 상태로 노출되어 CSS transparency 체커보드(흑백 격자)가 비치는 깜빡임
- 진짜 원인 (Playwright element.width setter trap으로 확정): zCanvas의 `Canvas.setViewport`가 내부 `updateCanvasSize`에서 `element.width`를 재할당 → Canvas API spec상 ctx 자동 reset. `scaleCanvas`는 `zCanvas.setViewport(...)`를 먼저 호출하고 그 다음 `setDocumentScale → setDimensions`를 호출하므로 setViewport에서 이미 ctx가 cleared된 후 setDimensions wrap이 호출되면 backup이 비어있는 element를 복사하는 흐름
- `bitmappery/src/rendering/actors/zoomable-canvas.ts`:
  - `setViewport`와 `setDimensions`를 `_snapshotAndCall` 헬퍼로 wrap. element.width 변경 직전 픽셀을 임시 canvas에 백업 → super 호출 → identity transform으로 새 ctx에 복원. **setViewport도 wrap한 게 결정타**
  - `render()` 가드: children 중 LayerRenderer(`.layer` 속성으로 식별)의 `_bitmap=null` 또는 `_bitmapReady=false`인 게 있으면 render skip. cacheEffects→setBitmap 비동기 파이프라인 동안 이전 frame 유지. GuideRenderer/InteractionPane 등은 가드에서 제외
- `bitmappery/src/components/document-canvas/document-canvas.vue`:
  - activeDocument watcher: 새 document swap 시 `flushRendererCache/flushBitmapCache/flushBlendedLayerCache/layerPool.clear` 4줄 제거. `createLayerRenderers`(line 498-507)가 이미 layer별 diff 처리를 갖춰 무차별 청소가 오히려 atomic swap을 깸. `renderState.reset()`만 유지
  - `createLayerRenderers`: orphan layer cleanup을 `requestAnimationFrame×3` 뒤로 미룸. `renderer.dispose()` 호출 → `Sprite.dispose` → 부모 zCanvas의 `removeChild` 자동
- towa-app 통합 레이어 (cloud 모드 큰 이미지 load 100ms+ 케이스 안전망):
  - `components/common/PageTransitionOverlay.vue` 신규: Teleport + 100ms delay + lucide Loader2 spinner
  - `composables/usePageLoader.ts`: 모듈 수준 `isPageSwitching` ref + `switchPage` try/finally + `loadPage` 직후 `nextTick + rAF×2` yield
  - `views/ProjectView.vue`: overlay mount
- 검증: Playwright로 5회 연속 페이지 전환 (3p→7p→1p→5p→2p) 시 canvas center pixel alpha 변화 0건, cleared frame 0개. `npx vue-tsc --noEmit` 통과

### 09:21 — F5 후속 1단계: 텍스트 박스 보존 + 폰트 fresh 재렌더 + CJK 위 잘림 fix
- bitmappery `Layer.meta.boxMode='fixed'` 분기 도입(`render-service.ts`). fixed 모드면 `replaceLayerSource` 우회 → `layer.left/top/width/height` 보존. native bitmappery 동작은 boxMode 미지정 시 그대로.
- `font-service.loadGoogleFontDetailed` 신규: `document.fonts.load` API로 실제 폰트 로드 완료 보장 + `freshlyLoaded` flag 반환. 기존 `loadGoogleFont`는 호환 시그니처(`Promise<boolean>`) 유지.
- `render-service.renderText` 반환을 `{ bitmap, fontFreshlyLoaded }`로 확장. `freshlyLoaded=true`이면 텍스트 캐시 무효화 + `requestAnimationFrame`으로 `cacheEffects` 한 번 더 트리거 → fallback 폰트 measure로 인한 잘림 회피.
- `rendering/operations/text.ts:measureLines`에 위 안전 패딩(font size × 0.2) 추가. 한국어/일본어/이모지 글리프가 `actualBoundingBoxAscent`를 초과해 canvas top으로 잘리는 문제 fix. `lineHeight`는 그대로 두고 `topOffset`과 `height`에만 패딩 반영.
- TOWA: `types/text-block.ts`에 `TextBoxMode` 타입 + `LayerTextMeta.boxMode`. `result-applier`/`dummy`/`EditorTab.addEmptyTextLayer` 모두 `boxMode: 'fixed'`. spec에 `meta.boxMode === 'fixed'` 검증.
- 검증: `npx vue-tsc --noEmit` 통과, `npm test` 25 tests pass, 사용자 Chrome에서 박스 보존·CJK 위 잘림 해소 확인.
- 후속: 텍스트박스 UX 개편(box-content 분리, 가로/세로 정렬, text-tool 통합 drag-resize·이동)은 별도 plan으로. 본 작업을 ui_engine으로 통합한 뒤 거기 베이스로 새 worktree에서 진행 예정.

### 01:34 — TranslationPanel ↔ bitmappery 텍스트 layer 통합 (F5)
- 데이터 중복 해소: bitmappery 텍스트 layer를 단일 source로. TOWA 측 TextBlock 메타 객체 제거.
- bitmappery 코어 최소 침습:
  - `Layer.meta?: Record<string, unknown>` 자유 metadata 필드 추가
  - `LayerFactory.create`의 외부 `id` 주입 허용 + `serialize/deserialize`의 `id`·`meta` 포함 (id 영속화)
  - `tool-options-text.vue`의 mutation commit을 namespace 자동 감지(`${ns}updateLayer`)로 변경 — standalone bitmappery와 towa-app embed 양쪽 지원. 미수정 시 embed 환경에서 unknown mutation 에러로 캔버스→panel sync 실패.
- TOWA 측: `types/text-block.ts`를 `LayerTextMeta` 인터페이스로 대체(`blockId/original/status`). `Page.textBlocks` 필드 제거. `utils/text-layer.ts` 신규 (helper: `isTextLayer`, `getTextMeta`, `mergeTextMeta`).
- UI: TranslationPanel/TextBlockItem이 layer를 직접 reactive 렌더링. Vue reactivity로 panel↔canvas 동기화 자동. 무한 루프 가드/source 플래그 불필요. `+` 버튼/휴지통 버튼으로 추가·삭제. EditorTab.selectLayer는 `bmp/setActiveLayerIndex` + 텍스트 layer일 때 `bmp/setActiveTool TEXT`까지 commit → tool-options-text 자동 활성화.
- AI 적용: result-applier가 textBlock 객체를 만들지 않고 layer 직접 생성, `meta: { blockId, original, status }` 채움. replace_text_blocks 시 기존 텍스트 layer 인덱스 역순 제거. text layer width/height는 document 전체로 지정 (텍스트 잘림 회피 시도).
- 백엔드 호환: service_engine `text_blocks: list[dict[str, Any]]` 자유 dict이므로 contract 코드 변경 없음. `towa-app/backend/real.ts`에서 textBlocks 직렬화 제거, `[]` 전송으로 호환.
- 더미 데이터: text layer를 document에 함께 시드, width/height = doc 크기, layer name `텍스트 #NN` (prefix 잔재 제거).
- 기존 저장 페이지 마이그레이션 없음 (프로토타이핑 단계).
- 검증: `npx vue-tsc --noEmit` 통과, `npm test` 25 tests pass, `npm run build` 성공, Playwright로 panel↔canvas 텍스트 양방향 sync + 추가/삭제 + 활성화 동작 확인.
- 한계: bitmappery 텍스트 layer 자체가 `replaceLayerSource`로 텍스트 bbox 크기로 layer 영역을 줄이고 left/top을 중앙 보정하는 모델이라, AI 검출 bbox 좌표가 렌더 후 무시되고 layer가 캔버스 중앙으로 이동함. 또한 텍스트가 측정 bbox보다 클 때 잘림 가능 (fallback 폰트 측정 등). F5 양방향 sync 본질 외 작업으로 별도 분리 필요.

### 00:37 — bitmappery 키보드 단축키 가드 2종 (U6/B1, B2)
- **U6/B1**: `towa-app/src/router/index.ts`에 `beforeEach` 가드 추가. `editor`·`detail-editor` 외 라우트 진입 시 `KeyboardService.setSuspended(true)` 호출해 캔버스가 안 보이는 라우트에서 C/V/Z 등 단축키 발사 차단
- **B2**: `bitmappery/src/services/keyboard-service.ts` `handleKeyDown` 진입부에 `INPUT/TEXTAREA/SELECT/contentEditable` target 가드 블록 추가. 입력란에서 타이핑 시 단축키로 발사되던 버그 수정

---

## 2026-05-07

### 15:52 — Landing/Login 풀페이지 + 라우터 가드 (manga panel 디자인)
- 14:23에 박았던 LibraryView 인라인 미로그인 가드를 라우트/가드 구조로 정식화
- 디자인 방향: "Manga panel × Editorial Brutalism" — 두꺼운 panel border + offset 그림자, halftone dot grid + 필름 그레인, marker highlight, 비대칭 grid + staggered 진입 애니메이션. 기존 dark/purple/pink 팔레트 유지
- 폰트: Bricolage Grotesque (display, 영문) + Pretendard Variable (한글). `index.html`에 `<link>` 로딩(@import 순서 경고 회피, preconnect 포함)
- `views/LandingView.vue` 신규 (`/`): Hero + 4단계 워크플로우(검출/지움/번역/식자 manga 패널) + AI/픽셀 split feature + Demo placeholder + CTA + Footer. 로그인 상태별 CTA 분기
- `views/LoginView.vue` 신규 (`/login`): 좌측 브랜딩+미니 워크플로우 / 우측 form 스플릿. devLogin 후 `?redirect=` 또는 `/library`. 회원가입 placeholder
- `router/index.ts`: 라우트 4개(`/`, `/login`, `/library`, `/project/:id`). `meta.requiresAuth` + `beforeEach` 가드로 cloud + 미로그인 시 `/login?redirect=...`으로 redirect
- `app.css`: halftone/halftone-dense/grain/hatch/marker/panel-border 유틸 + 진입 애니메이션 4종(rise/fade/slide/pop) + delay-1~6 stagger + `prefers-reduced-motion` 존중
- `views/LibraryView.vue`: 14:23의 인라인 미로그인 가드 제거 (라우터 가드로 대체)
- `components/common/AppNavbar.vue`: 미로그인 메뉴 "로그인" 버튼 → `router.push('/login')`. LoginModal 자체는 SettingsModal `@open-login` 트리거 + 추후 세션 만료 overlay 용도로 보존

### 14:23 — 라이브러리 미로그인 가드 + 새 프로젝트 추론모드 노출 제거
- 증상 1: cloud 모드에서 로그인 안 한 상태인데 라이브러리 폴더 트리/UI가 노출됨. 폴더 클릭 시 인증 에러
- 증상 2: 새 프로젝트 모달에 "추론 모드 (클라우드/로컬)" 라디오 노출. 모드 선택은 설정 메뉴(SettingsModal)에서만 다루는 게 맞음
- `views/LibraryView.vue`: cloud 모드 + 미로그인 분기 추가. 화면 전체를 "로그인 필요" 안내 + 로그인 버튼 + LoginModal 트리거로 대체
- `views/LibraryView.vue`: `isLoggedIn` watch 추가. 세션 중 로그인 성공 시 `projects/loadAll` 자동 호출 (main.ts 부팅 시 미로그인이라 로드 안 됐던 경우 보완)
- `components/home/CreateProjectModal.vue`: 추론모드 라디오 UI 제거. `formData.inferenceMode`는 항상 'cloud' default로 유지 (type 호환)
- 폴더 트리는 `library` store의 하드코드(주간연재/웹툰/단행본)라 미로그인 화면에서도 보이고 있었음 — 가드로 회피. 장기적으로 서버 source로 가야 함 (별도 작업)

### 02:30 — ui-engine 컨테이너 빌드 에러 통합 fix
- 증상: 서버에서 ui-engine 컨테이너가 빌드 통과 후 시작 직후 종료 또는 빌드 자체 실패. 결과 cloudflare 502
- 시도 흐름 (3단계):
  1차) `npm ci`가 lock sync 에러로 실패 → host(npm 11)에서 만든 lock이 incomplete. `npm ci --legacy-peer-deps` + lock 재생성으로 우회 시도 → 빌드는 통과했지만 컨테이너 시작 시 rollup 에러
  2차) lock의 platform 매핑이 누락된 게 원인이라 판단. `npm ci` → `npm install --legacy-peer-deps` 변경 → 같은 rollup 에러 지속 (npm install도 lock을 일부 존중해서 platform 누락 보완 못 함)
  3차) lock 파일 자체를 컨테이너에 안 가져가게 변경 → 빌드 시점 platform에 맞춘 fresh resolution → 모든 native binary 자동 설치. 해결.
- `towa-app/Dockerfile`: `COPY towa-app/package.json ./` + `RUN npm install --legacy-peer-deps`. lock 미포함, --legacy-peer-deps는 프로젝트 npm convention
- `towa-app/package-lock.json`: alpine x64 환경 기준으로 재생성 (호스트 dev 재현성 위해 유지)
- `DEPLOY.md`: cron 등록 절차 명확화 (절대경로 사용 필수, `crontab -l`/log tail 확인법 추가)
- 검증: 서버에서 `bash deploy.sh` 결과 ui-engine `Up`, `https://towa.live` 정상 접속

## 2026-05-06

### 17:55 — Cloudflare tunnel 기반 서버 배포 구성
- 배포 모델 확정: 서버는 main 브랜치만 따라가는 인스턴스. cron 5분 폴링으로 자동 pull + rebuild
- `deploy.sh` (monorepo 루트): `.env` 부트스트랩(없으면 `.env.deploy`에서 복사) + origin/main 변경 시 git pull + `docker compose up -d --build`. 1회 세팅도 같은 스크립트로 처리
- `.env.deploy` (monorepo 루트, commit됨): cloud-mode 운영 프리셋. clone 후 별도 편집 불필요
- `DEPLOY.md` (monorepo 루트): 서버 세팅(`git clone` + `deploy.sh` 한 번) + cloudflared ingress + 운영 가이드
- `vite.config.ts`: `VITE_PUBLIC_HOST` 환경변수 있을 때만 cloudflare 모드(allowedHosts + wss HMR clientPort 443) 적용. 없으면 로컬 모드 (기존 동작 유지)
- `.env.example`, `docker-compose.yml`: `VITE_PUBLIC_HOST` 슬롯 추가
- 단일 도메인 분기 구조: `towa.live` → 5173, `api.towa.live` → 8000, `model.towa.live` → 8100. 모두 호스트 cloudflared가 ingress 처리
- 도커 자체 구조 변경 없음 (코드 COPY 방식 유지: main push 시 이미지 재빌드로 반영)

### 10:30 — 프로젝트 생성 시 페이지 업로드 누락 버그 수정
- 증상: 프로젝트 생성 모달에서 파일을 첨부해 만들면 `project.pageCount`만 파일 수로 기록되고 실제 페이지는 업로드되지 않음. dashboard에 "Np"로 표시되지만 PageGrid는 비어있음
- `utils/page-from-file.ts` 신규: `buildPageSnapshotFromFile(file, projectId, pageIndex)` — 썸네일 생성 + bitmappery DocumentFactory layerBlob 빌드 + PageSnapshot 반환
- `views/LibraryView.vue`: `createProject`에 페이지 업로드 루프 추가, `pageCount`는 0으로 시작 후 업로드 완료 시점에 update
- `views/ProjectHomeTab.vue`: 중복 로직(generateThumbnail/blobToCanvas/inline snapshot 빌드) 제거하고 `buildPageSnapshotFromFile` 재사용

### 10:05 — Credit 잔액 UI 표시 + AI 호출 후 자동 갱신
- `store/modules/auth.ts`: `refreshCredit` 액션 추가 — `getCurrentUser` 호출 후 `creditBalance` 갱신, localStorage도 동기화
- `components/common/AppNavbar.vue`: 우상단에 크레딧 잔액 chip 추가 (cloud + 로그인 시), Coins 아이콘 + 잔액 + (예약 단위) 표시
- `components/editor/AiToolbar.vue`: AI job 종료(성공/실패)마다 `auth/refreshCredit` dispatch

### 09:46 — AI 도구 연동 (model_engine /v1/jobs 호출)
- `composables/useAppBackend.ts` 추가 (AppBackend inject 헬퍼)
- `main.ts`: `app.provide(APP_BACKEND_KEY, backend)` — AI 호출용 backend를 컴포넌트 트리에 노출
- `views/ProjectView.vue`: 중앙 영역에 `#towa-top-toolbar` Teleport target 추가, 캔버스 위에 toolbar 슬롯 확보
- `components/editor/AiToolbar.vue`: placeholder sleep 제거, 실제 `backend.aiJobs.createJob` + polling 연결. cloud/standalone 모드에 따라 `runtime_context.mode=saas|local` 자동 결정. 결과/에러를 toolbar 옆에 작은 status 텍스트로 표시
- `views/EditorTab.vue`(③ 기본 편집), `views/DetailEditorTab.vue`(④ 상세 편집): AiToolbar를 `#towa-top-toolbar`로 Teleport 마운트
- model_engine은 기본 PlaceholderJobExecutor로 동작 → API 호출/polling/auth/idempotency/error envelope 검증 가능, 실제 AI 결과는 후속 작업

### 00:05 — 문서 정리 (Project_Plan, TODO, design docs)
- `Project_Plan.md`: 7~8주차 완료 항목 추가, 남은 구현 사항 갱신 (F1/F2/F6 완료, F8 Electron + F9 cloud 통합 + F10 의존성 정리 추가), 9~12주차 계획 재정의
- `TODO.md`: 다음 할 일을 우선순위 순으로 정리, 보고서/연구노트/main 머지 완료 항목 추가, Electron 추가
- `docs/design-file-system.md`: FileAdapter 인터페이스를 7주차 snapshot 중심으로 갱신, ULID 도입 섹션 추가
- `docs/ui_to_service.md`: 7주차 실 구현 반영 (분리 GET/PUT → snapshot multipart 통합)

## 2026-04-28

### (오전) — main 머지: ui_engine 8주차 작업 통합
- `Merge ui_engine: Cloud mode integration and CRUD UI` 머지 커밋 생성 (`--no-ff`)
- 11커밋 / 37파일 / +4955-736 변경 main에 반영
- 포함 작업: FilesBackend SDK + CloudFileAdapter, auth 모듈, snapshot 인터페이스 리팩터링, 프로젝트/페이지 CRUD UI, ULID 도입, Docker 빌드 정비, zcanvas v5 pin, layer_blob MIME 정규화, IDB DataCloneError 수정

## 2026-04-27

### 15:24 — 프로젝트 생성 후 자동 이동 + 프로젝트 삭제 UI
- LibraryView.vue: `createProject` async로 변경, 생성 완료 후 `/project/:id`로 자동 이동
- ProjectCard.vue: hover 시 우측 상단에 삭제 버튼 표시 (Trash2 아이콘, `@click.stop`으로 카드 클릭과 분리), `BaseCard`에 `group` class 전달
- ProjectGrid.vue: `deleteProject` emit 추가, `@delete`를 상위로 전달
- LibraryView.vue: `confirmDeleteProject` / `deleteProject` 핸들러 추가, `BaseModal` + `BaseButton` 삭제 확인 모달 구현

### 15:23 — 페이지 삭제 UI 구현
- PageThumbnail.vue: hover overlay에 삭제 버튼 추가 (Trash2 아이콘, red-600 스타일), `delete` emit 정의
- PageGrid.vue: `deletePage` emit 추가, PageThumbnail의 `@delete` 이벤트를 상위로 전달
- ProjectHomeTab.vue: `confirmDeletePage` / `deletePage` 핸들러 추가, `useModal` + `BaseModal` + `BaseButton` 활용한 삭제 확인 모달 구현, vertical/horizontal 레이아웃 양쪽 PageGrid에 `@delete-page` 연결

---

## 2026-04-16

### 00:17 — Cloud 모드 연동 (service_engine 파일 저장 API)
- FilesBackend SDK 추가 (real: multipart HTTP + snake_case 변환, emulated: 메모리 stub)
- FileAdapter를 snapshot 중심 인터페이스로 전면 리팩터링 (createPage/savePageSnapshot/getPageSnapshot)
- LocalFileAdapter 재작성 (IDB 스키마 유지, delete 시 dense index reindex)
- Vuex auth 모듈 신규 (sessionKey/user/creditBalance, localStorage 세션 복원)
- 기존 LoginModal/AppNavbar/SettingsModal을 auth 스토어에 연결 (password→nickname)
- CloudFileAdapter 신규 (backend.files.* 위임, ProjectDto↔ProjectRecord 변환)
- main.ts에 deployment mode 분기 (standalone: seed+IDB, cloud: 세션 복원→서버 로드)
- IDB DataCloneError 수정 (Vue reactive proxy → sanitize 헬퍼로 JSON 정규화)
- mock HTTP 서버로 전 endpoint wire 검증 완료 (multipart 4파트, Bearer, snake_case)

---

## 2026-04-09

### 10:03 — 파일 시스템 구현 (IndexedDB 기반)
- IndexedDB 스키마 정의 (towa-db: projects, pages, page-images, page-layers, thumbnails, page-cache)
- FileAdapter 인터페이스 + LocalFileAdapter 구현 (순수 저장소 CRUD)
- usePageLoader composable (bitmappery ↔ FileAdapter 오케스트레이션)
- useAutoSave composable (bitmappery history 감지 → debounce 30초 → 자동 저장)
- PageCache 2계층 캐시 (메모리 LRU + IndexedDB LRU)
- Store 모듈 전환: 더미 데이터 → IndexedDB 기반 (projects.ts, pages.ts)
- 더미 데이터를 DB seed 함수로 전환 (첫 실행 시 자동 삽입)
- 이미지 드래그앤드롭으로 페이지 추가 기능 (PageGrid)
- 썸네일 자동 생성 (Canvas 축소 → Blob → IndexedDB)
- 페이지 전환 시 switchPage (저장 → 해제 → 로드) 구현
- types/page.ts: layers 필드 제거 (bitmappery 관할), thumbnail/originalImage optional
- 신규 파일: file-adapter/ (db.ts, contracts.ts, local.ts, index.ts, page-cache.ts)
- 신규 파일: composables/ (useFileAdapter.ts, usePageLoader.ts, useAutoSave.ts)

### 00:53 — 화면 ③ translator 모드 + bitmappery 인스턴스 공유
- bitmappery를 ProjectView(②③④ 공통 부모)에 배치 — ②에서 백그라운드 초기화, ③④에서 공유
- ③↔④ 전환 시 캔버스 유지, setTowaMode()로 모드만 전환
- EditorTab: DualCanvasView 제거 → bitmappery translator 캔버스 + TranslationPanel
- DetailEditorTab: bitmappery import 제거 (ProjectView가 관리)
- z-index 레이어링: bitmappery(z:0) + tab-layer(z:1, pointer-events passthrough)
- 레이아웃 겹침 이슈 남아있음 (bitmappery UI 리디자인 시 해결)

---

## 2026-04-06

### 09:51 — layer-renderer store proxy 적용
- layer-renderer.ts의 getStore()가 namespace proxy 반환하도록 수정
- getters.activeColor, commit("setActiveColor") 등 non-namespaced 접근 수정
- clone/brush/eraser 도구의 캔버스 상호작용 정상화 확인

### 09:26 — bitmappery 통합 버그 수정 (캔버스 + 아이콘 + 도구 초기화)
- 중복 id="bitmappery-app" 제거 (DetailEditorTab ↔ bitmappery.vue 충돌)
- $refs.app 접근을 created → mounted로 이동 (Vue 3 lifecycle 호환)
- store-proxy.ts 신규: namespace 프록시 (KeyboardService, history-state-factory용)
- Vite server.fs.allow 추가 (bitmappery asset 접근 허용)
- bitmappery public assets → towa-app public symlink
- 도구 아이콘 상대경로 → 절대경로 변경 (toolbox, tool-options-panel, layer-panel)
- 상세 편집 탭 진입 시 자동 빈 문서 생성
- document-canvas mounted에서 초기 document의 레이어 렌더러 + interaction pane 즉시 초기화

### 01:31 — bitmappery → towa-app 통합 (Phase 1~4)
- bitmappery Vuex store를 `bmp` namespace로 통합 (~60개 파일, 140+ mapper 수정)
- feature flag 동적화: `setTowaMode('translator' | 'typesetter')` 런타임 모드 전환
- `towa-mode-presets.ts` 신규 — 역자/식자 모드별 도구 프리셋
- `UI_HEADER_MENU` flag 추가, header-menu v-if 제어
- CSS 격리: `#app` → `#bitmappery-app`, `_global.scss` scope 축소
- `_colors.scss` CSS custom property fallback 패턴 적용 (10개 색상 변수)
- towa-app Vite: smartAliasResolver 플러그인 (bitmappery @/ ↔ towa-app @/ 분리)
- towa-app에 bitmappery 의존성 설치 + i18n/FloatingVue/Buffer polyfill 등록
- DetailEditorTab.vue: placeholder → bitmappery.vue 컴포넌트 삽입
- towa-app 테마 → bitmappery CSS 변수 매핑 (accent, bg, text 등)
- 양쪽 빌드 성공

---

## 2026-03-22

## 2026-03-23

### 17:07 — Deployment Mode cloud/standalone UI 분기
- 설정 추론 탭: standalone 전용으로 변경 (서버 주소, API 키, 동시 요청 등)
- cloud용 모델 선택 탭 추가 (텍스트 검출/번역/인페인팅 모델 + 플랜 표시)
- 상단바 유저 메뉴: cloud 모드에서 로그인/로그아웃 표시
- 로그인 모달 추가 (이메일/비밀번호 + 로그인 상태 유지)

### 16:58 — Deployment Mode 시스템 + 라이트 테마
- config/deployment.ts: DeploymentMode 타입 + reactive 모드 전환
- composables/useDeploymentMode.ts: isCloud/isStandalone/filterByMode 유틸
- 설정 모달 탭에 mode 필드 적용: 계정(cloud), 모델 연결(standalone)
- 디버그 탭 추가: 런타임에서 cloud/standalone 전환 가능
- 라이트 테마 구현: CSS 변수 기반 dark/light 전환, 설정에서 즉시 반영

### 11:29 — 테마 변경 + 더미 데이터 개선
- 색상 테마 커스텀 (accent #9569B4 보라, pink #e84a8a, green #4ade80)
- 배경/서페이스 톤을 보라빛 다크로 통일 (#0f0d18, #1a1726, #2a2540)
- 더미 프로젝트 8개로 확장: 원피스/주술회전/블루록/나혼렙/킹덤/전독시/요츠바랑/단편
- 현실적 데이터: 제목에 화수+부제, 페이지 수 다양화(8~180p), 폴더 분산
- 폴더 아이콘 색상을 accent(보라)로 통일

### 02:32 — 편집 화면 재설계 + 페이지 상태 단순화
- 페이지 상태: 5단계(pending~reviewed) → 4단계(waiting/ai-processing/in-progress/done)
- 편집 화면(역자 모드): 좌측 PageSidePanel(접기/펼기) + DualCanvasView(한쪽/두쪽 전환) + TranslationPanel(텍스트 전용)
- 한쪽보기: 원본/작업본 좌우 분할 / 두쪽보기: 만화 2페이지 펼침
- 상세 편집(식자 모드): PageSidePanel + bitmappery placeholder
- 프로젝트 홈: 페이지 상태 필터 칩 추가, hover 버튼 크기 통일
- PageStrip/EditorCanvas 삭제, PageSidePanel/DualCanvasView/TranslationPanel 신규
- editor store: pagePanelCollapsed, canvasViewMode 추가

### 00:13 — 프로젝트 홈 대시보드 + 상태 필터 이동 + 상단바 정리
- 프로젝트 홈 탭: 대시보드(이어하기 버튼, 진행률 바, 마지막 작업 페이지) + 페이지 그리드
- 레이아웃 전환: 상/하 또는 좌/우 배치 토글 버튼
- 상태 필터: 사이드바에서 메인 화면 우상단 가로 칩으로 이동
- 상단바: TOWA 로고(홈 버튼) + 홈 > 경로 구조, 구분자 `/` → `>` 변경

### 15:40 — 카드 UI 통일 + 폴더 미리보기 개선
- 새 프로젝트 버튼 크기를 프로젝트/폴더 카드와 동일하게 통일
- 프로젝트 카드: 하단 정보 영역 축소 (이름만 한 줄), 언어/페이지수/상태를 이미지 위 오버레이
- 폴더 카드: 직속 하위 항목(폴더+프로젝트) 미리보기, 2x2 고정 그리드, 하위 폴더는 폴더 아이콘으로 표시
- 폴더 미리보기 로직: 하위 폴더 프로젝트가 아닌 직속 자식만 표시 (파일시스템 원칙)

### 15:33 — 폴더 탐색 로직 수정 + 경로 UI 통일
- 폴더 필터링: 하위 폴더 프로젝트가 상위에서 안 보이도록 exact match로 변경
- 폴더 카드: 프로젝트 카드와 동일 크기, 내부에 하위 항목 썸네일 4개 미리보기
- 경로 표시: 라이브러리/프로젝트 모두 상단바에 통일 (ChevronRight 구분자)
- 더미 데이터: 주간연재 직속 프로젝트(킹덤) 추가하여 폴더 구조 검증

### 15:24 — UI 디테일 개선 (환경설정, 사이드바 정리, 폴더/프로젝트 분리)
- 환경설정 모달 추가 (일반/추론/외관 3탭, placeholder 항목 채움)
- 사이드바 순서 변경: 검색 → 최근 프로젝트 → 폴더 트리 → 상태 필터
- 폴더 트리: 섹션 헤더 제거, "전체"를 루트 노드로 통합, divider로 섹션 구분
- 메인 화면: 폴더 카드를 compact 가로 행으로 분리, 프로젝트 그리드와 크기 불일치 해소
- FolderCard를 가로 pill 스타일로 변경

### 14:30 — 라이브러리 UI 개선 (폴더 탐색, 사이드바, 유저 프로필)
- 메인 화면: Windows 탐색기 스타일 폴더 카드 + 프로젝트 카드 혼합 표시
- 사이드바: 폴더 트리 (2단계, 접기/펼치기 토글) + 상태 필터 + 최근 편집 섹션
- 상단바: 폴더 경로 클릭 시 해당 폴더로 이동, 유저 프로필/환경설정 dropdown 추가
- library store 신규: 폴더 트리, 현재 경로, 상태 필터 관리
- projects store: byFolder getter, recentlyEdited getter 추가
- 더미 데이터: folder를 계층 경로로 변경 (주간연재/점프, 웹툰/네이버 등)
- FolderCard 컴포넌트 신규, folder.ts 타입 신규

---

## 2026-03-20

### 00:31 — bitmappery 기능 분석 + feature flag 시스템 구현
- bitmappery 전체 기능 카탈로그 작성 (8개 카테고리, 46개 기능)
- Notion 설계 문서 DB에 "bitmappery 기능 카탈로그" 추가 (기능 분류, 텍스트 gap 분석, embed 검토)
- `src/config/towa-features.ts` 신규 생성 — 개별 feature flag 46개 (카테고리별 그룹화)
- Cloud Storage 3종 + GIF export 비활성화 (flag false)
- 도구(toolbox), 메뉴(Document), 파일 형식(PSD/PDF) 모두 flag 제어 가능
- 변경 파일: towa-features.ts(신규), cloud-service-loader.ts, export-window.vue, toolbox.vue, header-menu.vue, file-types.ts
- 빌드 검증 통과

---

## 2026-03-19

### 00:00 — 프로젝트 문서 초기 구성
- towa_project_description.md 작성 (프로젝트 전체 설명, 3개 엔진 구조, AI 파이프라인, UI 흐름)
- README.md 작성 (이 디렉토리의 역할과 구조)
- CLAUDE.md 작성 (AI 세션 간 공유 컨텍스트, 기술 스택, 작업 방식)
- TODO.md 작성 (당장 할 일 + Future + 에이전트별 작업 배정)
- 모든 다이어그램을 Mermaid로 통일
- Notion 팀 workspace 연결 확인 및 기존 문서 검토
- Notion 설계 문서 DB에 "UI 화면 구성 및 흐름", "UI 엔진 프로젝트 구조 및 기술 기반" 추가

### 05:00 — UI 구조 개편 (피드백 반영)
- 네비게이션: 계층적 화면 전환 → 탭 기반(`홈 | 편집 | 상세 편집`) + keep-alive
- 상단바: breadcrumb 제거 → 홈 아이콘 + 폴더/프로젝트명 + 탭 + `...` dropdown
- HomeView → LibraryView 리네임, ProjectView를 탭 wrapper로 변경
- 사이드바: 태그 제거, 상태 필터 추가 (전체/진행중/완료/TODO)
- 프로젝트 생성 모달: 파일 드래그앤드롭 일괄 업로드 추가
- 프로젝트 홈: 페이지 hover 시 편집/상세편집 버튼, 선택 페이지 하이라이트
- PageNavigator(세로) → PageStrip(하단 가로) 교체
- Project 타입에 status/folder 추가, tags 제거

### 03:30 — towa-app 프로젝트 초기화 + 화면 ①②③ 구현
- towa-app/ Vue 3 + TypeScript + Vite + Tailwind CSS v4 프로젝트 scaffold
- Vuex 4 namespaced store (projects, pages, editor 모듈)
- 공통 컴포넌트: AppNavbar, BaseModal, BaseButton, BaseCard, SearchBar
- 화면 ① 홈: 프로젝트 라이브러리 (사이드바 + 카드 그리드 + 생성 모달)
- 화면 ② 프로젝트 보기: 페이지 썸네일 그리드 + status badge
- 화면 ③ 기본 편집: 3단 레이아웃 (페이지 네비 / 캔버스 / 텍스트 목록+레이어)
- 화면 ④ 상세 편집: bitmappery 통합 예정 placeholder
- 다크 테마, bitmappery 색상 체계 기반, 라우팅 4개 화면 전환 동작
- 더미 데이터: 4개 프로젝트, 5~8페이지씩, 텍스트 블록 + 레이어

### 01:45 — monorepo 이전 및 Git 초기화
- TOWA monorepo (trit-ajou/TOWA) clone
- towa_project_description.md → TOWA/README.md로 합침 (main push)
- towa_frontend/ 내용을 TOWA/ui_engine/으로 복사 (자주프 관련 파일 제외)
- CLAUDE.md: monorepo 경로 반영, Git 규칙 추가 (feature 브랜치, Co-authored-by 금지)
- feat/ui-engine-init 브랜치에 커밋 및 push
