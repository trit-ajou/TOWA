# UI / Model Contract Draft

이 문서는 `model_engine` 브랜치에서 제안하는 `UI engine <-> model engine` concrete contract 초안이다.

중요:

- 이 문서는 현재 root `docs/`의 abstract boundary를 구현 가능한 형태로 좁힌 draft다.
- 아직 cross-engine canonical contract로 확정된 문서는 아니다.
- root 기준 authoritative boundary는 여전히 `../docs/http-contract.md`, `../docs/ui-model-abstract-boundary.md`, `../docs/boundary-open-questions.md`다.

관련 문서:

- `../docs/http-contract.md`
- `../docs/ui-model-abstract-boundary.md`
- `../docs/boundary-open-questions.md`
- `SESSION_AND_CREDENTIAL_IMPLEMENTATION.md`

## 1. 목적

현재 root 문서는 `UI -> model` 상세 wire shape를 의도적으로 미뤄 두고 있다.

하지만 실제 구현을 진행하려면 아래를 먼저 좁혀야 한다.

1. 입력은 어떤 형태로 model에 전달되는가
2. 큰 비트맵은 어떤 방식으로 전달되는가
3. 결과는 full document replacement인가, patch/artifact set인가

이 문서는 그 최소 합의안을 `model_engine` 관점에서 제안한다.

## 2. 설계 원칙

이 draft는 아래 원칙을 따른다.

- `UI engine`이 현재 메모리의 page state를 기준으로 AI 입력을 구성한다.
- `model engine`은 AI 작업 실행만 담당한다.
- AI 결과를 최종 merge하고 cloud/local 저장소에 반영하는 주체는 `UI engine`이다.
- 큰 비트맵은 inter-engine JSON 본문에 base64로 넣지 않는다.
- `UI -> model` 입력은 저장용 full snapshot이 아니라 `AI Input Projection`이다.
- `model -> UI` 출력은 full replacement가 아니라 `document_patch + artifacts`다.

## 3. 전송 방식

### 3.1 Job Create

`POST /v1/jobs`

- `Content-Type: multipart/form-data`
- 인증:
  - cloud: `Authorization: Bearer <session_key>`
  - standalone: optional

multipart part는 아래 이름만 허용한다.

- `metadata`
- `primary_bitmap`

향후 확장 가능 part:

- `mask_bitmap`
- `aux_bitmap_1`
- `aux_bitmap_2`

주의:

- `files` 같은 generic part 이름은 쓰지 않는다.
- `primary_bitmap`은 "현재 AI가 읽어야 하는 핵심 bitmap"을 의미한다.
- 항상 `original_image`만 의미하는 것은 아니다.

현재 구현 메모:

- 최종 목표는 multipart를 canonical create path로 두는 것이다.
- 다만 UI migration 전환을 위해 현재 `model_engine` 구현은 legacy JSON create도 함께 허용한다.
- strict canonical contract가 cross-engine으로 확정되면 JSON create compatibility path는 제거 대상이다.

### 3.2 Job Poll

`GET /v1/jobs/{job_id}`

- `Content-Type: application/json`
- 응답은 JSON job snapshot이다.

## 4. Request Contract

### 4.1 metadata JSON

`metadata` part는 JSON object 하나를 담는다.

shape:

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

### 4.2 Field 의미

#### `schema_version`

- 현재 허용값은 `"v1"`만 사용한다.

#### `operation_kind`

현재 허용값:

- `detect`
- `translate`
- `inpaint`

주의:

- `detect_and_translate` 같은 composite op는 이 draft에 포함하지 않는다.
- 복합 오퍼레이션이 필요하면 별도 enum과 stage composition contract를 추가로 정의한다.

#### `document`

`document`는 저장용 full page snapshot이 아니다.

의미:

- AI 실행에 필요한 최소 문서 projection
- page 크기
- 관련 text block
- 최소 stage meta
- 선택적으로 필요한 레이어/문맥 정보

의도적으로 포함하지 않는 예:

- thumbnail
- full save metadata
- UI 전용 viewport state
- 저장용 complete layer blob metadata

#### `artifacts`

`artifacts`는 binary 자체가 아니라 descriptor map이다.

원칙:

- 실제 binary는 multipart part로 전달한다.
- `artifacts`는 binary를 파이프라인 내부 ref로 연결하기 위한 metadata다.
- 현재 draft에서는 `primary_bitmap` 대응 descriptor를 최소 요구로 둔다.

#### `runtime_context`

`runtime_context`는 실행 힌트와 auth/runtime 문맥을 담는다.

예:

- `mode`
- `workspace_uri`
- `selected_layer_ids`
- `target_regions`

`target_regions`는 `document` 안이 아니라 `runtime_context`에 둔다.

## 5. Response Contract

### 5.1 Create Response

`POST /v1/jobs` 응답은 기존 async create shape를 유지한다.

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

### 5.2 Poll Response

`GET /v1/jobs/{job_id}` 응답은 아래 shape를 제안한다.

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
              "bbox": {
                "x": 105,
                "y": 210,
                "width": 280,
                "height": 130
              },
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

### 5.3 Field 의미

#### `status`

기존 status enum을 그대로 유지한다.

허용값:

- `queued`
- `running`
- `succeeded`
- `failed`
- `partial`

주의:

- `completed` 같은 새 status는 이 draft에 포함하지 않는다.

#### `document_patch`

`document_patch`는 UI가 현재 page state에 merge해야 하는 변경 사항이다.

중요:

- `document`를 patch로 재해석하지 않는다.
- full document replacement를 기본으로 하지 않는다.
- patch는 명시적인 결과 필드로 분리한다.
- patch 내부 shape는 `model_engine`의 canonical `PatchOperation` 목록을 그대로 따른다.

현재 구현 메모:

- 현재 `model_engine` poll 응답은 UI migration 전환을 위해 full `document`도 함께 내려준다.
- 장기 canonical contract에서는 `document_patch` 중심 merge path를 우선한다.

예상 patch op 예:

- `replace_text_blocks`
- `append_text_blocks`
- `replace_source_ref`
- `set_stage_meta`

#### `artifacts`

`artifacts`는 array가 아니라 descriptor map을 유지한다.

이유:

- 현재 UI backend contract가 map shape를 전제로 하고 있다.
- `model_engine` 내부 artifact registry 의미와도 잘 맞는다.
- diff, merge, lookup이 더 단순하다.

#### `stage_reports`

`stage_reports`는 stage별 실행 결과를 그대로 노출한다.

용도:

- UI debug
- partial/failure 진단
- 진행 상태 표시에 활용 가능

## 6. UI merge 규칙

이 draft에서 최종 merge 주체는 항상 `UI engine`이다.

즉:

1. UI는 현재 page state를 기준으로 AI input projection을 만든다.
2. model은 `document_patch + artifacts + stage_reports`를 반환한다.
3. UI는 현재 page state에 patch를 적용한다.
4. UI가 merge된 결과를 최종 snapshot으로 저장한다.

원칙:

- model은 cloud page snapshot을 직접 저장하지 않는다.
- model은 full page authoritative state를 소유하지 않는다.
- service는 AI 결과를 해석/merge하지 않는다.

## 7. 현재 UI 코드와의 호환성

현재 `ui_engine/towa-app/src/backend`에는 de facto contract가 이미 있다.

이 draft는 그 contract를 완전히 부정하지 않고 아래처럼 보정한다.

유지하는 것:

- `schema_version`
- `idempotency_key`
- `operation_kind`
- `request_ref`
- `document`
- `artifacts`
- `runtime_context`
- async create + poll

바꾸는 것:

- create request 전송 방식:
  - 기존 `application/json`
  - 제안 `multipart/form-data`
- poll response:
  - 기존 `document`
  - 제안 `document_patch`

따라서 UI backend layer 수정 포인트는 비교적 명확하다.

## 8. 구현 영향

### 8.1 UI engine

수정 대상:

- `ui_engine/towa-app/src/backend/contracts.ts`
- `ui_engine/towa-app/src/backend/real.ts`
- editor wiring component

필요 변경:

- `AiJobSnapshot`에 `documentPatch` 추가
- `createJob()`을 `FormData` 기반으로 변경
- `metadata`와 `primary_bitmap` part 생성
- polling 결과의 `document_patch`를 현재 page state에 merge

### 8.2 model_engine

수정 대상:

- `api/app.py`
- `api/schemas.py`
- `api/jobs.py`

필요 변경:

- `/v1/jobs`에서 multipart 입력 수신
- `metadata` JSON 파싱
- `primary_bitmap`를 artifact로 정규화
- poll 응답에 `document_patch` 생성

## 9. 아직 열어 둔 항목

이 draft가 닫지 않는 항목:

- `document_patch` 내부 op schema의 최종 shape
- `artifacts.uri`의 최종 transport 규약
- `mask_bitmap`, `aux_bitmap_*`의 구체 사용 규칙
- `pipeline` 같은 composite operation 도입 여부
- result retention TTL, cancel, cleanup 정책

즉 이 문서는 "가장 작은 합의안"이지, 모든 UI/model 세부 계약을 완성한 문서는 아니다.

## 10. 최종 요약

이 draft의 핵심은 다음 세 줄이다.

- 입력은 `multipart/form-data`, part는 `metadata + primary_bitmap`
- `document`는 저장용 snapshot이 아니라 `AI Input Projection`
- 결과는 full document가 아니라 `document_patch + artifacts`
