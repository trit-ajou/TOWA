# ui_engine → main 머지 contract 호환성 노트

대상: `model_engine`, `service_engine` 담당자
작성: 2026-05-14
배경: ui_engine 브랜치에 F5 작업(TranslationPanel ↔ bitmappery 텍스트 layer 통합, PR #10)이 머지됨. TOWA 데이터 모델이 `TextBlock` 객체에서 bitmappery `Layer.meta` 기반으로 전환됨. 이 변경을 main에 올리기 전, 두 엔진과의 contract 호환성을 풀스택 통합 테스트로 검증.

## 결론: 두 엔진 모두 코드 변경 **불필요**

ui_engine 측 변경은 backward compatible하게 설계됐고, 풀스택 도커 환경에서 save/load 사이클로 검증 완료.

---

## ui_engine 측 변경 요약

### 데이터 모델
- **이전**: `Page.textBlocks: TextBlock[]` 필드에 검출 텍스트 정보 별도 보관. `TextBlock`은 `{id, pageId, bbox, original, translated, font, fontSize, color, status}` 객체
- **현재**: bitmappery `Layer.meta?: Record<string, unknown>` 필드에 통합. `LayerTextMeta = {blockId, original, status, boxMode}`. `Layer.text.value`가 번역문, `Layer.left/top`이 좌표. `TextBlock` 객체 자체 제거

### Wire format
- **요청 (페이지 저장 `PUT /api/v1/pages/{id}/snapshot` metadata)**: `text_blocks: []` 빈 배열로 전송. 실제 layer 데이터는 별도 `layer_blob` (multipart)에 통째 직렬화
- **요청 (AI job `POST /v1/jobs` metadata)**: 현재 캔버스의 text layer를 `text_blocks[]`로 매핑해서 전송. 각 항목 `{block_id, source_lang_text, translated_text, bbox: {x,y,width,height}}` ([AiToolbar.vue:65-73](../towa-app/src/components/editor/AiToolbar.vue#L65-L73))
- **응답 (AI job)**: `document_patch.patches[].op = "replace_text_blocks"`, `payload.text_blocks[]` 그대로 사용. ui_engine은 `block_id|id`, `source_lang_text|original`, `translated_text|translated`, `bbox.{x|left, y|top, width|w, height|h}` 모두 fallback 처리 ([result-applier.ts:125-176](../towa-app/src/ai/result-applier.ts#L125-L176))

---

## service_engine 호환성: **변경 불필요**

### 근거
- `service_engine/app/api/schemas/projects.py:72` `text_blocks: list[dict[str, Any]] = Field(default_factory=list)` — Pydantic이 자유 dict 받음. ui_engine이 `[]` 보내도 정상
- DB 저장: `page_snapshots.metadata_json` JSONB 컬럼에 통째 저장. 별도 컬럼/테이블 없음 ([alembic/versions/20260415_000002_add_project_page_storage.py](../../service_engine/alembic/versions/20260415_000002_add_project_page_storage.py))
- `_canonical_metadata` (service.py:183-190)가 `page.id, project_id, index, status`만 덮어쓰고 나머지 보존
- 검증: 저장된 `metadata_json` 실측 — `{page: {id, project_id, index, status, text_blocks: []}}` 4개 필수 필드만, 다른 필드 없음

### 영향
- 기존 페이지는 그대로 로드/저장 가능
- 새 페이지는 layer 데이터가 `layer_blob`에 들어감 (이미 multipart 스펙대로). metadata는 페이지 식별/상태만

### 검증 (이미 통과)
- 도커로 db + service-engine 기동, ui_engine cloud + real backend 모드로 접속
- 신규 프로젝트 생성 → 페이지 업로드 → 텍스트 layer 추가 + `text.value`, `meta`, `left/top` 주입 → 페이지 전환(switchPage)으로 save 트리거 → `PUT /pages/.../snapshot 200 OK` 확인
- 페이지 1 → 2 → 1 round-trip 후 layer 데이터 (`value`, `meta`, 좌표) 모두 복원 확인

---

## model_engine 호환성: **변경 불필요**

### 근거
- `model_engine/contracts/document_ir.py:58-70` `TextBlock` dataclass — **pydantic 아닌 자유 형식**. 필드: `block_id, source_lang_text, translated_text, polygon, bbox: dict[str, float], reading_order, speaker, style_hint, font_hint, writing_mode, source_region_ref`
- bbox 키: model_engine OCR 출력은 `{x, y, width, height}` 키 사용 ([manga_ocr.py:414-417, 430-433, 440-442](../../model_engine/builtin_models/manga_ocr.py)). ui_engine `bboxFromPayload`도 `{x|left, y|top, width|w, height|h}` 모두 받음 → **완전 호환**
- ui_engine이 보내는 `text_blocks[]` 형식이 위 TextBlock 필드와 일치 ([AiToolbar.vue:65-73](../towa-app/src/components/editor/AiToolbar.vue#L65-L73))
- model_engine은 각 stage 완료 시 `REPLACE_TEXT_BLOCKS` 패치로 자체 OCR 결과 보냄 — ui_engine이 보낸 메타는 자연스럽게 덮어써짐. backward compatible

### 영향
- 기존 detect/inpaint/translate flow 변경 없이 작동

---

## ui_engine 측 후속 fix (이 통합 테스트에서 발견)

PR #10에 포함됐어야 했지만 unit test가 toBlob 경로를 안 거쳐서 놓친 회귀를 main-merge-prep 브랜치에서 fix:

1. `usePageLoader.ts` — `page.textBlocks ?? []` 라인 제거. `Page` 타입에 더 이상 없는 필드 참조
2. `TextBlockList.vue` — dead component 삭제. `text-block.ts`의 제거된 `TextBlock` 타입을 import. import graph에서 빠져 있어 vue-tsc가 안 잡음
3. **`bitmappery/src/factories/layer-factory.ts`** — `Layer.meta`를 `serialize`에서 plain object로 복사. Vue 3 reactive proxy 그대로 보내면 worker postMessage의 `structuredClone`이 거부해 `DataCloneError` 발생 → save 전체 실패. JSON 라운드트립으로 해결 (meta는 flat dict of primitives라 안전)

이 셋은 ui_engine 디렉토리 내부에 격리됨. 다른 엔진과 무관.

---

## 통합 테스트 시나리오 (실측)

### (A) service_engine save/load 사이클 — **통과**
1. 도커: `db` + `service-engine` 기동, `dev_admin seed-user` 1회
2. ui_engine dev 서버 (cloud + real backend 모드)
3. 로그인 → 신규 프로젝트 → 페이지 2장 업로드 (`page1`, `page2`)
4. EditorTab의 page1에 `addEmptyTextLayer` (`activeLayerIndex=1` out-of-bounds 회귀 없음 검증)
5. layer에 `text.value`, `meta`, `left/top` 주입
6. page2 → page1 전환으로 switchPage → savePage 트리거
7. 결과: `PUT /pages/.../snapshot 200 OK`, page1 재진입 시 layer 데이터 round-trip 모두 보존

### (B) model_engine AI flow — **wire format 호환 확인**
1. 도커: `model-engine` 추가 기동 (PyTorch + craft 모델 다운로드 포함)
2. EditorTab에서 "텍스트 검출" (`operation_kind: detect`) 호출
3. 결과: `POST /v1/jobs 202 Accepted` → polling → `status: succeeded`
4. 응답 `document.text_blocks[]` schema 실측:
   ```json
   {
     "block_id": "layer_2",
     "source_lang_text": "ORIGINAL_TEXT_テスト",
     "translated_text": "CONTRACT_TEST_NEW",
     "polygon": [],
     "bbox": {"x":50,"y":100,"width":1470,"height":723},
     "reading_order": null, "speaker": null,
     "style_hint": {}, "font_hint": {},
     "writing_mode": "horizontal", "source_region_ref": null
   }
   ```
   → ui_engine이 보낸 `text_blocks[]` 형식 그대로 echo. **wire format 완전 호환**
5. 응답 patches: `[{op: 'set_stage_meta', payload: {key: 'text_detection', value: {engine: 'craft', region_count: 43}}}]`
6. **참고**: 현재 builtin model_engine `operation_kind: detect`는 craft region detection만 수행하고 OCR 텍스트 인식은 미실시. 따라서 `replace_text_blocks` patch는 없음. ui_engine result-applier가 자연스럽게 무시 → layer 미생성. 이는 model_engine OCR stage 미구성 이슈이지 ui_engine contract 문제 아님.

### (C) E2E save/load + AI — **시나리오 A로 커버됨**
시나리오 A에서 layer 데이터 (text.value, meta, 좌표)의 service_engine 저장/복원을 이미 검증. AI flow는 별도 stage가 없어 추가 round-trip 검증 불가하지만, `text_blocks[]` schema 호환은 (B)에서 확인.

---

## 참고 파일

**ui_engine**
- `towa-app/src/backend/contracts.ts:40-49` `TransportDocument`
- `towa-app/src/backend/real.ts:512` 저장 시 `text_blocks: []`
- `towa-app/src/ai/result-applier.ts:125-176` AI 응답 → Layer
- `towa-app/src/types/text-block.ts` `LayerTextMeta`
- `bitmappery/src/factories/layer-factory.ts:103-106` meta plain copy fix

**model_engine** (수정 불필요, 참고용)
- `contracts/document_ir.py:58-70` `TextBlock` dataclass
- `builtin_models/manga_ocr.py:300-304` block_id 생성

**service_engine** (수정 불필요, 참고용)
- `app/api/schemas/projects.py:72` `text_blocks: list[dict[str, Any]]`
- `app/modules/projects/service.py:183-190` `_canonical_metadata`
