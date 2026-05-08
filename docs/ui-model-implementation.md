# UI / Model Implementation Guide v1

이 문서는 현재 저장소 기준 `UI engine <-> model engine` 구현 가이드다.

중요:

- 이 문서는 **현재 구현 기준 guide**다.
- 추상 경계와 canonical responsibility는 여전히 [ui-model-abstract-boundary.md](ui-model-abstract-boundary.md), [http-contract.md](http-contract.md)를 따른다.
- 즉 이 문서는 abstract boundary를 대체하지 않는다.
- 대신 UI 팀과 model 팀이 **지금 바로 맞춰야 하는 실제 payload, migration path, 주의사항**을 정리한다.

관련 문서:

- [http-contract.md](http-contract.md)
- [ui-model-abstract-boundary.md](ui-model-abstract-boundary.md)
- [boundary-open-questions.md](boundary-open-questions.md)
- [service-engine-boundary.md](service-engine-boundary.md)

## 1. 이 문서가 필요한 이유

현재 루트 문서는 의도적으로 `UI <-> model` 상세 wire shape를 canonical contract로 고정하지 않는다.

하지만 실제 구현은 이미 진행되었고, 다음 두 사실이 동시에 존재한다.

1. `UI engine` backend 계층에는 `/v1/jobs` 기준 de facto contract가 이미 있다.
2. `model_engine`은 새 multipart 입력과 `document_patch` 응답을 이미 구현했다.
3. `UI engine`은 현재 visible Bitmappery document를 `primary_bitmap`으로 캡처하고,
   `document_patch + artifacts` 결과를 현재 page state와 Bitmappery layer stack에 적용한다.

따라서 지금 단계에서는 아래를 분리해서 이해해야 한다.

- **Abstract boundary**
  - 누가 무엇을 책임지는가
- **Current implementation guide**
  - 지금 UI가 무엇을 보내고 무엇을 받아야 하는가

이 문서는 두 번째를 다룬다.

## 2. 고정된 책임 경계

이 구현 가이드는 아래 고정 전제를 바꾸지 않는다.

- `UI engine`이 현재 메모리의 page state를 기준으로 AI 입력을 구성한다.
- `UI engine`이 `model engine`에 직접 AI job을 요청한다.
- `model engine`은 AI job 실행만 담당한다.
- `model engine -> service engine` 직접 통신 범위는 auth/usage다.
- AI 결과를 최종적으로 현재 page state에 병합하고 저장하는 주체는 `UI engine`이다.
- cloud에서 최종 snapshot 저장 authority는 `service engine`이다.

즉, `model engine`은 full page authority가 아니다.

## 3. 현재 구현 상태 요약

현재 `model_engine` 구현은 아래를 지원한다.

### 3.1 Create Path

`POST /v1/jobs`

- 새 경로:
  - `multipart/form-data`
  - `metadata + primary_bitmap`
- 임시 compatibility 경로:
  - `application/json`

즉, **UI는 앞으로 multipart create path로 이동해야 한다.**
다만 migration 전환을 위해 현재 model은 legacy JSON create를 잠시 함께 받는다.

### 3.2 Poll Path

`GET /v1/jobs/{job_id}`

- 응답은 `application/json`
- 현재 응답에는 둘 다 들어 있다.
  - `document_patch`
  - `document`

중요:

- 장기적으로 UI가 merge에 사용해야 하는 것은 `document_patch`다.
- `document`는 migration/debug compatibility 용도다.
- `document` 전체를 authoritative result로 간주하면 안 된다.

### 3.3 Artifact Download Path

`GET /v1/jobs/{job_id}/artifacts?artifact_ref=<urlencoded>`

- job detail과 같은 owner/auth 규칙을 적용한다.
- 해당 job의 `artifacts` map에 존재하는 descriptor만 다운로드할 수 있다.
- v1에서는 `file://` artifact만 binary response로 내려준다.
- response `Content-Type`은 artifact descriptor의 `media_type`을 사용한다.
- job/artifact 없음, owner 불일치, 지원하지 않는 URI는 기존 error envelope로 반환한다.

## 4. Auth / Mode 규칙

### 4.1 Cloud

UI는 `service_engine`에서 받은 `session_key`를 그대로 `model_engine`에도 보낸다.

헤더:

```http
Authorization: Bearer <session_key>
```

이 bearer는 다음 용도로 쓰인다.

- `model_engine`의 SaaS auth gate
- job owner scope 식별
- `model -> service` usage hold/capture/release pass-through

### 4.2 Standalone

- `Authorization`은 필수가 아니다.
- `runtime_context.mode=local`

## 5. Job Create Request

## 5.1 Canonical 방향

UI가 맞춰야 하는 현재 구현 기준 create request는 아래다.

- method: `POST /v1/jobs`
- `Content-Type: multipart/form-data`
- required parts:
  - `metadata`
  - `primary_bitmap`

현재는 아래 generic field를 허용하지 않는다.

- `files`
- 임의 이름의 blob part

향후 확장 후보:

- `mask_bitmap`
- `aux_bitmap_1`
- `aux_bitmap_2`

하지만 지금 구현에서 실제로 받는 것은 `metadata`, `primary_bitmap`만이다.

## 5.2 metadata JSON shape

`metadata`는 JSON object 하나다.

예:

```json
{
  "schema_version": "v1",
  "idempotency_key": "project:proj-1:page:001:op:translate:v:1",
  "operation_kind": "translate",
  "request_ref": "project/proj-1/page/001",
  "document": {
    "id": "page_001",
    "width": 1200,
    "height": 1600,
    "text_blocks": [],
    "stage_meta": {}
  },
  "artifacts": {
    "artifact://input/primary_bitmap": {
      "artifact_ref": "artifact://input/primary_bitmap",
      "kind": "bitmap",
      "media_type": "image/png",
      "uri": "upload://primary_bitmap"
    }
  },
  "runtime_context": {
    "mode": "saas",
    "workspace_uri": "workspace://project/proj-1/page/001",
    "selected_layer_ids": ["layer_bg"],
    "target_regions": []
  }
}
```

## 5.3 Field 의미

### `schema_version`

- 현재 허용값은 `"v1"`만 사용한다.

### `operation_kind`

현재 구현 허용값:

- `detect`
- `translate`
- `inpaint`

주의:

- `detect_and_translate` 같은 composite op는 현재 구현 대상이 아니다.
- UI가 composite op를 원하면 별도 합의 후 enum과 pipeline selection을 함께 늘려야 한다.

### `document`

`document`는 저장용 full page snapshot이 아니다.

의미:

- AI 실행에 필요한 최소 projection
- 현재 page의 구조적 문맥
- 필요한 text block
- 필요한 최소 stage meta

의도적으로 넣지 않는 것:

- thumbnail
- UI viewport state
- 저장용 전체 snapshot 메타데이터
- service save용 blob structure

즉 `document`는 **AI Input Projection**이다.

### `artifacts`

`artifacts`는 blob 자체가 아니라 descriptor map이다.

원칙:

- 실제 binary는 multipart part로 전달한다.
- `artifacts`는 pipeline 내부 artifact ref를 선언한다.
- UI는 `primary_bitmap` blob을 보내는 동시에,
  `artifacts["artifact://input/primary_bitmap"].uri = "upload://primary_bitmap"` 를 함께 넣어야 한다.

### `runtime_context`

`runtime_context`는 실행 문맥이다.

현재 의미 있는 필드:

- `mode`
- `workspace_uri`
- `selected_layer_ids`
- `target_regions`
- cloud일 경우 session/auth 문맥

`target_regions`는 `document` 내부가 아니라 `runtime_context`에 둔다.

## 5.4 `upload://primary_bitmap` 의미

이건 UI 쪽에서 꼭 이해해야 하는 부분이다.

UI가 보내는 metadata 안에는 아래 descriptor가 들어간다.

```json
{
  "artifact_ref": "artifact://input/primary_bitmap",
  "kind": "bitmap",
  "media_type": "image/png",
  "uri": "upload://primary_bitmap"
}
```

그리고 multipart part에는 실제 `primary_bitmap` binary가 들어간다.

model 쪽에서는 이 둘을 묶어서 다음을 수행한다.

1. uploaded binary를 읽는다
2. 임시 local file로 materialize 한다
3. metadata의 `upload://primary_bitmap`를 `file://...` artifact uri로 치환한다
4. 이후 pipeline은 이 local artifact를 기준으로 실행한다

즉 UI는:

- blob은 multipart로 보내고
- metadata에는 `upload://primary_bitmap` placeholder를 넣는다

이 조합을 맞춰야 한다.

## 5.5 Idempotency 주의사항

현재 `model_engine`은 단순 metadata만 보지 않는다.

multipart create에서는 request fingerprint에 아래가 같이 들어간다.

- metadata JSON
- uploaded `primary_bitmap`의 sha256

의미:

- 같은 `idempotency_key`라도 이미지가 달라지면 다른 요청으로 간주된다
- 같은 key로 다른 bitmap을 재사용하면 conflict 판정이 날 수 있다

즉 UI는 idempotency key를 아래 의미로 써야 한다.

- 같은 사용자 의도
- 같은 page state 기준
- 같은 bitmap 기준

## 6. Job Create Response

create 응답은 기존 async envelope을 유지한다.

예:

```json
{
  "job_id": "job_123",
  "pipeline_id": "pipe_123",
  "status": "queued",
  "operation_kind": "translate",
  "request_ref": "project/proj-1/page/001",
  "status_url": "/v1/jobs/job_123"
}
```

UI는 이 응답을 받은 뒤 polling으로 넘어간다.

## 7. Job Poll Response

`GET /v1/jobs/{job_id}`

현재 구현 응답 예:

```json
{
  "job_id": "job_123",
  "pipeline_id": "pipe_123",
  "status": "succeeded",
  "operation_kind": "translate",
  "request_ref": "project/proj-1/page/001",
  "document_patch": {
    "patches": [
      {
        "op": "replace_text_blocks",
        "target": {},
        "payload": {
          "text_blocks": [
            {
              "block_id": "tb_001",
              "source_lang_text": "こんにちは",
              "translated_text": "안녕하세요"
            }
          ]
        }
      }
    ]
  },
  "document": {
    "id": "page_001",
    "width": 1200,
    "height": 1600
  },
  "artifacts": {
    "artifact://result/inpaint_layer": {
      "artifact_ref": "artifact://result/inpaint_layer",
      "kind": "bitmap",
      "media_type": "image/png",
      "uri": "temp://job_123/inpaint_layer"
    }
  },
  "stage_reports": [],
  "error": null
}
```

## 7.1 `status`

허용값:

- `queued`
- `running`
- `succeeded`
- `failed`
- `partial`

UI는 `succeeded`, `failed`, `partial`을 terminal로 취급하면 된다.

## 7.2 `document_patch`

이게 현재 구현에서 UI가 최종적으로 따라야 하는 핵심 결과 필드다.

형태:

```json
{
  "patches": [
    {
      "op": "...",
      "target": {},
      "payload": {}
    }
  ]
}
```

즉 `document_patch` 내부 shape는 자유형이 아니라,
`model_engine`의 canonical `PatchOperation` 배열이다.

현재 UI가 우선적으로 준비해야 하는 patch op:

- `replace_text_blocks`
- `append_text_blocks`
- `replace_source_ref`
- `set_stage_meta`

`detect` 작업의 현재 구현:

- model engine은 CRAFT `text_regions` artifact를 계속 생성한다.
- 외부 `detect` job 결과에는 UI merge를 위해 `replace_text_blocks` patch도 포함한다.
- 이때 block의 `source_lang_text`/`translated_text`는 OCR 전이므로 빈 문자열이다.
- `translate`/`inpaint` 내부 선행 검출 단계는 text block patch를 만들지 않는다.

중요:

- `document`를 patch처럼 재해석하면 안 된다.
- merge source of truth는 `document_patch`다.

## 7.3 `document`

현재 poll 응답에는 full `document`도 같이 들어간다.

하지만 이건 **전환기 compatibility/debug 용도**다.

권장:

- 새 UI merge path는 `document_patch`를 사용한다
- `document`는 fallback/debug 참고용으로만 둔다

장기적으로는 이 full `document`가 제거될 가능성을 염두에 둬야 한다.

## 7.4 `artifacts`

`artifacts`는 배열이 아니라 map이다.

이 형태를 유지하는 이유:

- 현재 UI backend adapter가 map 형태를 전제로 하고 있다
- artifact lookup이 단순하다
- patch와 artifact ref를 연결하기 쉽다

UI는 artifact 결과를 받을 때 다음을 하면 된다.

- patch가 가리키는 `artifact_ref`를 찾는다
- 해당 descriptor map에서 실제 artifact descriptor를 resolve한다
- bitmap artifact가 필요하면 `/v1/jobs/{job_id}/artifacts`로 Blob을 다운로드한다

예:

```http
GET /v1/jobs/job_123/artifacts?artifact_ref=artifact%3A%2F%2Fresult%2Finpaint_layer
Authorization: Bearer <session_key>
```

## 7.5 `stage_reports`

`stage_reports`는 stage별 실행 결과다.

UI가 여기서 기대할 수 있는 것:

- stage name
- status
- metrics
- warnings

용도:

- 사용자에게 진행 상태 표시
- 디버그 뷰 표시
- OCR warning / partial result 강조

## 8. UI가 해야 하는 일

현재 UI 팀 관점에서 해야 할 일은 명확하다.

## 8.1 `createJob()` 전송 방식 변경

현재 JSON-only create를 쓰고 있다면 multipart로 이동해야 한다.

해야 할 일:

1. 현재 page state에서 AI Input Projection을 만든다
2. `metadata` JSON을 만든다
3. 현재 AI가 읽어야 하는 bitmap을 `primary_bitmap` Blob/File로 만든다
4. `FormData`로 `metadata`, `primary_bitmap`를 붙여 보낸다

## 8.2 `contracts.ts` 타입 보강

UI 타입에서 아래를 분명히 해야 한다.

- `document`는 full snapshot이 아니라 AI Input Projection
- poll 응답에는 `documentPatch`가 존재
- `document`는 transitional compatibility field

즉 UI 타입 수준에서 “무엇이 authoritative result인가”를 명확히 해야 한다.

## 8.3 Poll 결과 merge

UI는 polling 결과를 받아 아래 순서로 처리하면 된다.

1. `status` 확인
2. `succeeded`만 자동 적용 대상으로 삼는다
3. `partial` 또는 `failed`는 적용하지 않고 page status를 이전 상태로 되돌린다
4. `document_patch`를 현재 page state에 merge한다
5. patch가 참조하는 bitmap artifact가 있으면 `artifacts` map에서 resolve한 뒤 artifact endpoint로 Blob을 다운로드한다
6. merge된 최종 page state를 UI store에 반영한다
7. 적용 직후 `savePage(pageId)`로 snapshot을 즉시 저장한다

현재 UI 적용 정책:

- `primary_bitmap` 입력은 현재 보이는 active Bitmappery document 전체를 PNG로 캡처한다.
- `replace_text_blocks`는 현재 page의 `textBlocks`를 교체한다.
- `append_text_blocks`는 현재 page의 `textBlocks` 뒤에 추가한다.
- text block마다 새 Bitmappery `text` layer를 최상단에 추가한다.
- text layer 이름은 `AI <Operation> <YYYYMMDD HHmm> #NN` 형식이다.
- text layer 내용은 `translated_text`를 우선하고 없으면 `source_lang_text`를 사용한다.
- text style은 `Noto Sans KR`, `24px`, black으로 고정한다.
- `add_layer` 또는 `replace_source_ref`가 bitmap artifact를 참조하면 기존 레이어를 찾거나 교체하지 않고 새 `graphic` layer 후보를 최상단에 추가한다.
- `set_stage_meta`는 UI 내부 result/status 표시용으로만 보관하며 현재 service snapshot metadata에는 별도 저장하지 않는다.

## 8.4 Placeholder 제거

현재 placeholder 경로를 실제 backend 호출로 바꾸려면 최소한 아래가 연결돼야 한다.

- backend adapter `createJob`
- backend adapter `getJob`
- polling lifecycle
- `document_patch` reducer / merge 함수

## 9. UI 구현 체크리스트

UI 팀이 실제로 손대게 될 가능성이 높은 파일:

- `ui_engine/towa-app/src/backend/contracts.ts`
- `ui_engine/towa-app/src/backend/real.ts`
- `ui_engine/towa-app/src/backend/emulated.ts`
- `ui_engine/towa-app/src/backend/__tests__/backend.spec.ts`
- `ui_engine/towa-app/src/components/editor/AiToolbar.vue`
- `ui_engine/towa-app/src/components/editor/DualCanvasView.vue`

권장 순서:

1. `contracts.ts`에 `primaryBitmap`, `documentPatch`, `getArtifact()` 계약 유지
2. `real.ts`는 `multipart(metadata + primary_bitmap)` create와 artifact Blob download를 유지
3. `emulated.ts`도 같은 shape와 fake bitmap artifact를 유지
4. backend tests와 result applier tests로 wire shape와 page 적용 정책을 검증
5. `AiToolbar`는 active document 캡처, polling, `succeeded` 적용, 즉시 snapshot 저장을 담당

## 10. 지금 당장 하지 않는 것

이 문서는 아래를 아직 최종 확정하지 않는다.

- presigned URL 기반 artifact store
- `mask_bitmap`, `aux_bitmap_*`의 실제 semantics
- composite operation enum
- final removal 시점의 legacy JSON create
- full `document` compatibility field 제거 시점

즉 이 문서는 **현재 구현을 맞추기 위한 guide**이고,
장기 canonical contract의 완전한 종료 선언은 아니다.

## 11. 추천 요약

UI 팀이 기억해야 할 핵심은 이 네 줄이다.

1. create는 `multipart(metadata + primary_bitmap)`로 간다
2. metadata의 image descriptor는 `upload://primary_bitmap`를 쓴다
3. poll 결과의 authoritative merge source는 `document_patch`다
4. 최종 merge/save 책임은 UI에 있다
