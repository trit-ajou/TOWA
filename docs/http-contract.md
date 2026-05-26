# HTTP Contract v1

현재 `service_engine` 브랜치의 canonical HTTP contract 문서다.
목표는 `UI engine`, `service engine`, `model engine` 개발자가 같은 wire contract와 책임 경계를 보고 구현을 맞출 수 있게 하는 것이다.

관련 문서:

- [service-engine-boundary.md](service-engine-boundary.md)
- [project-page-storage-boundary.md](project-page-storage-boundary.md)
- [ui-model-abstract-boundary.md](ui-model-abstract-boundary.md)

주의:

- `auth`, `usage`, `project/page snapshot`은 현재 구현된 contract다.
- `UI -> model`, `model -> UI`의 상세 payload/result shape는 이번 단계에서 canonical wire contract로 고정하지 않는다.

## Scope

- 전송 방식: `HTTP REST`
- 기본 payload:
  - 작은 메타데이터: `application/json; charset=utf-8`
  - page snapshot: `multipart/form-data`
- 공통 actor:
  - `UI engine`: 사용자 진입점, project/page snapshot save/load 주체
  - `service engine`: 세션, credit, usage, cloud project/page snapshot authority
  - `model engine`: AI 작업 실행 주체
- 제외:
  - websocket, SSE streaming
  - cloud launch, exchange, heartbeat
  - export 포맷 상세
  - provider API 세부 프로토콜
  - `UI <-> model` 상세 payload/result shape

## Deployment Modes

### Cloud

- `UI -> service`: 로그인, 세션 확인, project/page summary 조회, page snapshot 저장/로드
- `UI -> model`: AI 작업 요청
- `model -> service`: hold, capture, release

UI의 `deployment mode=cloud`는 model의 `runtime_context.mode=saas`에 대응한다.

### Standalone

- `UI -> model`만 필수다
- `service engine`은 없어도 된다
- project/page snapshot 저장은 UI 내부 IndexedDB가 담당한다
- 개인 API 키 또는 로컬 모델 경로는 `model engine` 내부 정책으로 처리한다

UI의 `deployment mode=standalone`은 model의 `runtime_context.mode=local`에 대응한다.

## Caller Matrix

| Caller | Target | Endpoints |
| --- | --- | --- |
| `UI engine` | `service engine` | `POST /auth/dev/login`, `GET /auth/me` |
| `UI engine` | `service engine` | `GET /api/v1/folders`, `POST /api/v1/folders`, `PATCH /api/v1/folders/{folder_id}`, `DELETE /api/v1/folders/{folder_id}`, `POST /api/v1/folders/{folder_id}/restore`, `GET /api/v1/trash` |
| `UI engine` | `service engine` | `POST /api/v1/projects`, `GET /api/v1/projects`, `GET /api/v1/projects/{project_id}`, `PATCH /api/v1/projects/{project_id}`, `DELETE /api/v1/projects/{project_id}`, `POST /api/v1/projects/{project_id}/restore` |
| `UI engine` | `service engine` | `GET /api/v1/projects/{project_id}/pages`, `POST /api/v1/projects/{project_id}/pages`, `GET /api/v1/pages/{page_id}/snapshot`, `PUT /api/v1/pages/{page_id}/snapshot`, `DELETE /api/v1/pages/{page_id}`, `GET /api/v1/pages/{page_id}/thumbnail` |
| `model engine` | `service engine` | `POST /usage/jobs`, `POST /usage/jobs/{job_id}/capture`, `POST /usage/jobs/{job_id}/release`, `GET /usage/jobs/{job_id}` |
| `UI engine` | `model engine` | `GET /healthz`, `POST /v1/jobs`, `GET /v1/jobs/{job_id}` |
| smoke/debug caller | `model engine` bridge | `GET /bridge/service/healthz`, `GET /bridge/service/auth/me`, `POST /bridge/service/usage/jobs`, `POST /bridge/service/usage/jobs/{job_id}/capture`, `POST /bridge/service/usage/jobs/{job_id}/release`, `GET /bridge/service/usage/jobs/{job_id}` |

## Base URLs

### Browser-facing

- `UI`: `http://localhost:5173`
- `service`: `http://localhost:8000`
- `model`: `http://localhost:8100`

### Docker Internal

- `service-engine`: `http://service-engine:8000`
- `model-engine`: `http://model-engine:8100`
- `db`: `postgresql://db:5432`

브라우저와 컨테이너 내부 주소는 다르다.
UI env는 `localhost` 기준, 컨테이너 간 호출은 compose service name 기준으로 맞춘다.

## Shared Rules

### Auth

cloud 모드에서는 세 엔진 간 사용자 식별 토큰으로 현재 `session_key` 하나만 사용한다.

전달 방식:

```http
Authorization: Bearer <session_key>
```

- `UI engine`이 `service engine`에서 받은 `session_key`를 `model engine`에도 그대로 보낸다
- `model engine`은 billing, usage 관련 `service engine` 호출에 같은 헤더를 그대로 전달한다
- standalone 모드에서는 `service engine` 호출이 없고, `UI -> model` auth도 필수가 아니다

### Request Correlation

가능하면 아래 헤더를 추가한다.

```http
X-Towa-Request-Id: <client-generated-request-id>
```

- UI가 생성한다
- model이 service 호출 시 그대로 전달한다
- 로그와 트레이싱 용도다

현재 구현 필수는 아니지만 inter-engine 디버깅 기준으로 권장한다.

### Time Format

- 모든 timestamp는 UTC ISO-8601 문자열을 사용한다
- 예: `2026-03-29T06:15:00Z`

### Idempotency

- `service engine`의 usage create는 body의 `idempotency_key`를 authoritative key로 사용한다
- `model engine`의 job create도 body의 `idempotency_key`를 사용한다
- UI는 "한 번의 사용자 의도"마다 stable key를 생성해야 한다
- replay는 같은 caller와 같은 payload에만 허용된다
- 같은 key를 다른 payload로 재사용하면 `409 conflict`로 처리한다

권장 형식:

```text
project:{project_id}:page:{page_id}:op:{operation_kind}:v:{attempt_or_revision}
```

### Error Envelope

기본 JSON 오류 형식은 아래를 사용한다.

```json
{
  "error": {
    "code": "string",
    "message": "human readable message",
    "retryable": false,
    "details": null
  }
}
```

원칙:

- `service engine`은 이 형식을 기준으로 한다
- `model engine`도 가능하면 같은 envelope을 사용한다
- `502`가 필요할 때 model은 `service_engine_unreachable` 같은 code를 쓴다

현재 주요 `error.code`:

- service 공통:
  - `session_key_required`
  - `session_invalid`
  - `session_expired`
  - `validation_error`
  - `insufficient_credits`
  - `usage_job_not_found`
  - `usage_conflict`
  - `missing_credit_account`
  - `concurrent_update_conflict`
  - `bad_request`
  - `folder_not_found`
  - `folder_conflict`
  - `project_not_found`
  - `page_not_found`
  - `project_conflict`
  - `page_conflict`
- model 공통:
  - `model_validation_error`
  - `model_job_not_found`
  - `model_job_conflict`
  - `model_stage_failed`
  - `service_engine_unreachable`

### Large Payload Rules

- 큰 비트맵을 inter-engine JSON 본문에 base64로 직접 넣는 것은 채택하지 않는다.
- service의 page snapshot save/load는 예외적으로 `multipart`를 사용한다.
- model 관련 큰 결과물 전달 방식은 [ui-model-abstract-boundary.md](ui-model-abstract-boundary.md)에 적은 추상 규칙만 고정하고, 구체 wire shape는 미룬다.

## Service Engine Endpoints

### Auth

#### `POST /auth/dev/login`

요청:

```json
{
  "email": "user@example.com",
  "nickname": "tester"
}
```

응답:

```json
{
  "session_key": "opaque-token",
  "expires_in": 86400,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "nickname": "tester",
    "status": "active",
    "created_at": "2026-03-25T00:00:00Z"
  },
  "credit_balance": 1000,
  "reserved_units": 0
}
```

규칙:

- `email`은 trim, lowercase 처리한다
- 기존 유저면 새 `session_key`를 다시 발급한다
- `nickname`이 들어오면 기존 유저 닉네임도 갱신한다

#### `GET /auth/me`

헤더:

```http
Authorization: Bearer <session_key>
```

응답:

```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "nickname": "tester",
    "status": "active",
    "created_at": "2026-03-25T00:00:00Z"
  },
  "credit_balance": 1000,
  "reserved_units": 0
}
```

### Usage

#### `POST /usage/jobs`

호출자:

- `model engine`

요청:

```json
{
  "idempotency_key": "project:proj-1:page:001:op:detect:v:1",
  "operation_kind": "mask",
  "request_ref": "project/proj-1/page/001",
  "estimated_units": 5
}
```

응답:

```json
{
  "job_id": "uuid",
  "status": "authorized",
  "reserved_units": 5,
  "hold_expires_at": "2026-03-29T07:00:00Z"
}
```

규칙:

- `estimated_units`는 0보다 커야 한다
- `estimated_units`는 `model engine`이 계산해서 보낸다
- 같은 유저가 같은 `idempotency_key`로 다시 호출하면 같은 `job_id`를 돌려준다
- 같은 유저가 같은 `idempotency_key`를 다른 payload로 재사용하면 `409 usage_conflict`와 `details.reason=idempotency_payload_mismatch`를 반환한다
- 사용 가능한 credit이 부족하면 `409 insufficient_credits`다
- stale hold 정리는 authenticated user 범위에서만 수행한다

#### `POST /usage/jobs/{job_id}/capture`

요청 본문은 빈 JSON 객체 `{}` 를 사용한다.

응답은 usage job detail이며, 성공 시 상태는 `succeeded`다.

규칙:

- 실제 차감량은 현재 `estimated_units`와 동일하다
- 이미 `succeeded`인 job에 다시 capture하면 같은 성공 상태를 반환한다
- 이미 `failed`인 job에 capture하면 `409 usage_conflict`다
- hold가 만료된 뒤 capture하면 먼저 release 처리되고 `409 usage_conflict`를 반환한다

#### `POST /usage/jobs/{job_id}/release`

요청:

```json
{
  "error_code": "model_stage_failed",
  "reason": "placeholder executor failed"
}
```

응답은 usage job detail이며, 성공 시 상태는 `failed`다.

규칙:

- `error_code`, `reason`은 optional이다
- 둘 다 없으면 `error_code`는 `job_released`로 저장된다
- 이미 `failed`인 job에 다시 release하면 같은 실패 상태를 반환한다
- 이미 `succeeded`인 job에 release하면 `409 usage_conflict`다

#### `GET /usage/jobs/{job_id}`

응답은 usage job detail이며 현재 세션 유저 소유 job만 조회 가능하다.

규칙:

- 다른 유저 job이면 `404 usage_job_not_found`다

### Folder And Project Metadata

서비스는 library folder를 entity로 저장한다.
project는 `folder_id`로 folder를 참조하고, `folder_path`는 표시용 derived field다.

#### Folder Object

```json
{
  "id": "uuid",
  "name": "점프",
  "parent_id": "uuid-or-null",
  "path": "주간연재/점프",
  "created_at": "2026-05-26T00:00:00Z",
  "updated_at": "2026-05-26T00:00:00Z",
  "deleted_at": null
}
```

규칙:

- folder id는 service가 생성한 UUID다
- 같은 부모 아래 같은 이름의 live folder는 `409 folder_conflict`다
- folder name은 1~100자이며 빈 문자열, `/`, `\`, 제어문자를 거부한다
- backend는 tree depth 제한을 두지 않는다

#### Folder Endpoints

- `GET /api/v1/folders`: live folder flat list. `search` query가 있으면 name 부분일치 검색
- `POST /api/v1/folders`: `{ "name": "점프", "parent_id": null }`
- `PATCH /api/v1/folders/{folder_id}`: `{ "name"?: string, "parent_id"?: string | null }`
- `DELETE /api/v1/folders/{folder_id}`: 빈 live folder만 trash 이동
- `DELETE /api/v1/folders/{folder_id}?cascade=trash`: subtree folder/project를 같은 `deleted_at`으로 trash 이동
- `DELETE /api/v1/folders/{folder_id}?reparent=true`: 자식을 부모 folder로 승격 후 대상 folder만 trash 이동
- `POST /api/v1/folders/{folder_id}/restore`: trashed subtree restore
- `DELETE /api/v1/folders/{folder_id}?permanent=true`: trashed subtree hard delete

`cascade`, `reparent`, `permanent`는 상호 배타다.
cycle move와 live item permanent delete는 `400 bad_request`다.

#### Project Object

```json
{
  "id": "proj_001",
  "name": "원피스 1122화",
  "thumbnail_url": "http://localhost:8000/api/v1/pages/page_001/thumbnail",
  "source_lang": "ja",
  "target_lang": "ko",
  "page_count": 19,
  "status": "in-progress",
  "folder_id": "uuid-or-null",
  "folder_path": "주간연재/점프",
  "config": {
    "auto_detect": true,
    "auto_inpaint": true,
    "auto_translate": false,
    "inference_mode": "cloud"
  },
  "created_at": "2026-04-15T00:00:00Z",
  "updated_at": "2026-04-15T00:00:00Z",
  "deleted_at": null
}
```

#### `POST /api/v1/projects`

요청:

```json
{
  "id": "proj_001",
  "name": "원피스 1122화",
  "source_lang": "ja",
  "target_lang": "ko",
  "status": "todo",
  "folder_id": "uuid-or-null",
  "config": {
    "auto_detect": true,
    "auto_inpaint": true,
    "auto_translate": false,
    "inference_mode": "cloud"
  }
}
```

응답은 Project Object다.

규칙:

- client-generated `id`를 사용한다
- 같은 유저가 같은 `id`를 다시 만들면 `409 project_conflict`다
- `page_count`는 요청에 받지 않는다
- `thumbnail_url`은 nullable이다
- `thumbnail_url`은 UI가 선택한 대표 cover 값이며 service는 opaque string으로 저장/반환한다
- root project는 `folder_id=null`, `folder_path=null`이다

#### Project Endpoints

- `GET /api/v1/projects`: live project list
- `GET /api/v1/projects/{project_id}`: live project detail
- `PATCH /api/v1/projects/{project_id}`: `name`, `thumbnail_url`, `source_lang`, `target_lang`, `status`, `folder_id`, `config` 부분 갱신
- `DELETE /api/v1/projects/{project_id}`: live project trash 이동, 응답은 deleted Project Object
- `POST /api/v1/projects/{project_id}/restore`: trashed project restore. parent folder가 deleted 상태면 root로 복구
- `DELETE /api/v1/projects/{project_id}?permanent=true`: trashed project hard delete

#### `GET /api/v1/trash`

응답:

```json
{
  "items": [
    {
      "type": "folder",
      "item": Folder Object
    },
    {
      "type": "project",
      "item": Project Object
    }
  ]
}
```

기본 folder/project/page 조회 API는 `deleted_at IS NULL` 항목만 반환한다.
휴지통 metadata는 `GET /api/v1/trash`가 제공한다.

### Page Summary

프로젝트 화면용 page 목록은 full page snapshot이 아니라 summary만 제공한다.

#### Page Summary Object

```json
{
  "id": "page_001",
  "project_id": "proj_001",
  "index": 1,
  "status": "waiting",
  "thumbnail_url": "http://localhost:8000/api/v1/pages/page_001/thumbnail",
  "updated_at": "2026-04-15T00:00:00Z"
}
```

#### `GET /api/v1/projects/{project_id}/pages`

응답:

```json
{
  "items": [Page Summary Object...]
}
```

규칙:

- project view는 이 API만 사용한다
- full snapshot과 `text_blocks` 전체 목록은 포함하지 않는다
- `thumbnail_url`은 bearer 인증이 필요한 private service URL이다

### Page Snapshot

page save/load의 authoritative transport는 `page snapshot`이다.

request part names:

- `metadata`: `application/json`
- `original_image`: `image/*`
- `layer_blob`: `application/octet-stream`
- `thumbnail`: `image/*`

full replace 규칙:

- `POST`와 `PUT` 모두 complete snapshot을 요구한다
- partial update는 지원하지 않는다
- 저장 정책은 `last-write-wins`다
- 첫 저장도 `layer_blob`을 포함한 complete snapshot이어야 한다
- page create는 append-only다

media validation:

- `original_image`, `thumbnail`: `image/jpeg | image/png | image/webp`
- `layer_blob`: `application/octet-stream`
- 최대 크기:
  - `original_image`: `50MB`
  - `thumbnail`: `5MB`
  - `layer_blob`: `100MB`

#### TextBlock Object

```json
{
  "id": "tb_001",
  "page_id": "page_001",
  "bbox": {
    "x": 12,
    "y": 24,
    "width": 180,
    "height": 56
  },
  "original": "おはようございます！",
  "translated": "좋은 아침이에요!",
  "font": "Noto Sans KR",
  "font_size": 14,
  "color": "#000000",
  "status": "translated"
}
```

#### Page Snapshot Metadata Object

```json
{
  "page": {
    "id": "page_001",
    "project_id": "proj_001",
    "index": 1,
    "status": "in-progress",
    "text_blocks": [TextBlock Object...]
  }
}
```

규칙:

- `original_image`는 mutable current page asset이다
- `layer_blob`은 bitmappery `DocumentFactory.toBlob()` 결과를 그대로 저장하는 opaque binary다
- service는 `layer_blob` 내부를 해석하지 않는다
- `thumbnail`은 project/page list 최적화를 위한 current preview다
- `metadata.page.id`, `metadata.page.project_id`는 canonical ULID string이다

#### `POST /api/v1/projects/{project_id}/pages`

요청:

- `Content-Type: multipart/form-data`
- 위의 네 part를 모두 포함한다

응답:

```json
{
  "page": Page Summary Object
}
```

규칙:

- `metadata.page.project_id`는 path의 `project_id`와 같아야 한다
- 같은 page `id`가 이미 존재하면 `409 page_conflict`다
- `metadata.page.index`는 현재 마지막 page의 다음 번호와 같아야 한다
- 중간 삽입은 v1에서 지원하지 않는다

#### `GET /api/v1/pages/{page_id}/snapshot`

응답:

- `Content-Type: multipart/mixed`
- part names는 요청과 동일하다:
  - `metadata`
  - `original_image`
  - `layer_blob`
  - `thumbnail`

#### `GET /api/v1/pages/{page_id}/thumbnail`

응답:

- `Content-Type: image/jpeg | image/png | image/webp`

규칙:

- 현재 유저가 소유한 page만 fetch 가능하다
- 이 endpoint의 absolute URL이 `Page Summary.thumbnail_url`의 기본 구현이다

#### `PUT /api/v1/pages/{page_id}/snapshot`

요청:

- `Content-Type: multipart/form-data`
- `POST /api/v1/projects/{project_id}/pages`와 같은 complete snapshot

응답:

```json
{
  "page": Page Summary Object
}
```

규칙:

- `metadata.page.id`는 path의 `page_id`와 같아야 한다
- `metadata.page.project_id`, `metadata.page.index`는 저장된 page identity와 같아야 한다
- 순서 변경은 지원하지 않는다

#### `DELETE /api/v1/pages/{page_id}`

응답:

```json
{
  "deleted": true,
  "page_id": "page_001"
}
```

규칙:

- hard delete다
- 뒤 page들의 `index`를 당겨 dense `1..N`을 유지한다

## Service Engine State Rules

### Usage Job

- `authorized`
- `succeeded`
- `failed`

전이:

- `POST /usage/jobs` -> `authorized`
- `POST /usage/jobs/{job_id}/capture` -> `succeeded`
- `POST /usage/jobs/{job_id}/release` -> `failed`

### Credit Hold

- `held`
- `captured`
- `released`

전이:

- job 생성 시 `held`
- capture 시 `captured`
- release 시 `released`

## Service Engine Invariants

- `service engine`은 cloud 모드에서 project metadata와 page snapshot binary를 저장할 수 있다
- `service engine`은 bitmappery `layer_blob`, OCR 의미, 생성 결과 의미를 해석하지 않는다
- `service engine`은 provider secret을 저장하거나 소유하지 않는다
- `service engine`은 `estimated_units`의 business authority가 아니라 세션, 잔액, 상태 authority다
- capture, release는 같은 `job_id`에 대해 idempotent 하게 동작해야 한다
- `credit_ledger`는 capture 때만 증가한다
- release는 ledger entry를 만들지 않는다

## UI -> Model Boundary

이번 단계에서 canonical하게 고정하는 것은 아래뿐이다.

- UI는 model에 직접 AI 작업을 요청한다
- 모든 AI 작업은 비동기 job contract를 사용한다
- UI는 현재 메모리 상태를 기준으로 AI 입력을 구성한다
- AI 결과를 받은 뒤 최종 page snapshot 저장은 UI가 담당한다
- model이 service와 직접 통신하는 범위는 auth/usage로 제한한다

세부 payload/result shape, binary handoff, artifact transport는
[ui-model-abstract-boundary.md](ui-model-abstract-boundary.md)에서 deferred decision으로 관리한다.

## Model Engine Endpoints

### Current Implemented Endpoints

현재 코드에 실제로 있는 endpoint:

- `GET /healthz`
- `POST /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `GET /bridge/service/healthz`
- `GET /bridge/service/auth/me`
- `POST /bridge/service/usage/jobs`
- `POST /bridge/service/usage/jobs/{job_id}/capture`
- `POST /bridge/service/usage/jobs/{job_id}/release`
- `GET /bridge/service/usage/jobs/{job_id}`

의미:

- `healthz`: model 컨테이너 헬스체크
- `/v1/jobs`: placeholder async job create, status API
- `bridge/service/*`: service contract pass-through smoke test

주의:

- `/v1/jobs`의 상세 request/response body shape는 현재 repo reference implementation이다
- 이 shape 자체를 이번 단계의 canonical cross-engine contract로 고정하지 않는다

### `GET /healthz`

응답:

```json
{
  "status": "ok"
}
```

### `POST /v1/jobs`

주의:

- 아래 JSON 예시는 현재 reference implementation이다
- `UI <-> model` canonical boundary로 고정하는 것은 endpoint 존재가 아니라 async job invariant와 auth/usage 책임 분리다

```http
POST /v1/jobs
Authorization: Bearer <session_key>   # cloud only
Content-Type: application/json
```

요청 예시:

```json
{
  "schema_version": "v1",
  "idempotency_key": "project:p1:page:001:op:translate:v:1",
  "operation_kind": "translate",
  "request_ref": "project/p1/page/001",
  "document": {
    "id": "doc_page_001",
    "name": "page-001",
    "width": 1600,
    "height": 2400,
    "layers": [
      {
        "id": "layer_original",
        "name": "Original",
        "type": "graphic",
        "left": 0,
        "top": 0,
        "width": 1600,
        "height": 2400,
        "source_ref": "artifact://page-original"
      }
    ],
    "text_blocks": [],
    "stage_meta": {}
  },
  "artifacts": {
    "artifact://page-original": {
      "artifact_ref": "artifact://page-original",
      "kind": "bitmap",
      "media_type": "image/png",
      "uri": "https://storage.example.test/page-001.png"
    }
  },
  "runtime_context": {
    "mode": "saas",
    "workspace_uri": "workspace://project/p1/page/001",
    "requested_by": "user@example.com",
    "target_regions": [],
    "selected_layer_ids": []
  }
}
```

필드 규칙:

- `operation_kind`
  - `detect`
  - `inpaint`
  - `translate`
  - `pipeline`
- `request_ref`
  - service usage 정산의 `request_ref`와 같은 의미를 갖는다
- `document`
  - Bitmappery 의미론 기반 `DocumentIR`
- `artifacts`
  - 큰 payload는 반드시 여기의 ref, uri로 전달한다
- `runtime_context.mode`
  - `saas` 또는 `local`

응답 예시:

```json
{
  "job_id": "job_8f8f1d",
  "pipeline_id": "pipe_3e9d7f",
  "status": "queued",
  "operation_kind": "translate",
  "request_ref": "project/p1/page/001",
  "status_url": "/v1/jobs/job_8f8f1d"
}
```

규칙:

- 권장 상태 코드는 `202 Accepted`다
- `saas` job idempotency는 caller scope다
- 같은 caller가 같은 `idempotency_key`를 다른 payload로 재사용하면 `409 model_job_conflict`다
- cloud 모드에서 bearer가 없으면 `401 session_key_required`다
- 현재 내부 실행은 placeholder executor 기반이다
- `pipeline`은 현재 `422 model_validation_error`다

### `GET /v1/jobs/{job_id}`

주의:

- 아래 응답 shape도 현재 reference implementation이다
- 최종 canonical cross-engine result schema는 UI/model 팀 합의 후 별도 문서화한다

```http
GET /v1/jobs/{job_id}
Authorization: Bearer <session_key>   # cloud only
```

규칙:

- `saas`에서는 create에 사용한 것과 같은 bearer로만 조회 가능하다
- auth 누락은 `401 session_key_required`다
- 다른 caller가 조회하면 `404 model_job_not_found`다
- `local`에서는 auth 없이 조회 가능하다

응답 예시:

```json
{
  "job_id": "job_8f8f1d",
  "pipeline_id": "pipe_3e9d7f",
  "status": "succeeded",
  "operation_kind": "translate",
  "request_ref": "project/p1/page/001",
  "document": {
    "id": "doc_page_001",
    "name": "page-001",
    "width": 1600,
    "height": 2400,
    "layers": [],
    "text_blocks": [],
    "stage_meta": {
      "translation": {
        "status": "done"
      }
    }
  },
  "artifacts": {},
  "stage_reports": [],
  "error": null
}
```

`status` 값:

- `queued`
- `running`
- `succeeded`
- `failed`
- `partial`

terminal state:

- `succeeded`
- `failed`
- `partial`

### Model Auth And Error Rules

- cloud 모드에서는 `Authorization: Bearer <session_key>`를 그대로 받는다
- `saas` job과 bridge 호출 시 같은 헤더를 `service_engine`으로 전달한다
- standalone 모드에서는 auth가 없어도 된다
- service가 돌려준 오류는 가능하면 그대로 전달한다
- service가 unreachable이면 model은 `502 service_engine_unreachable`를 반환한다

예시:

```json
{
  "error": {
    "code": "service_engine_unreachable",
    "message": "failed to reach service engine at http://service-engine:8000",
    "retryable": true,
    "details": null
  }
}
```

## Current Model Bridge

이 bridge는 현재 service contract를 거의 그대로 중계한다.
목적은 다음 두 가지다.

- docker bring-up 확인
- model -> service auth, billing pass-through 검증

주의:

- 이 경로는 개발용 bridge다
- 최종 UI가 service API를 model bridge를 통해 우회 호출하는 구조를 기본 계약으로 삼지는 않는다

## Operation Mapping

외부 `operation_kind`와 내부 stage capability 매핑:

- `detect` -> `text_detection`
- `inpaint` -> `text_detection`, `mask_or_erase_planning`, `inpaint`
- `translate` -> `text_detection`, `ocr`, `translation`
- `pipeline` -> 명시된 pipeline config에 따름

현재 구현 상태:

- `detect` 관련 built-in 있음
- `inpaint` 관련 built-in 있음
- `translate` pipeline은 아직 미완성이다

## Billing Boundary

원칙:

- UI는 billing, credit을 직접 계산하지 않는다
- model은 billed job 시작, 종료 시점만 판단한다
- service는 잔액, 상태 authority다

cloud billed flow:

1. UI가 service에서 `session_key` 획득
2. UI가 model에 작업 요청
3. model이 `POST /usage/jobs`
4. model 작업 성공 시 `capture`
5. model 작업 실패 시 `release`
6. UI는 필요하면 model job 상태와 service credit 상태를 별도로 조회

standalone flow:

- service 없음
- `Authorization` 헤더 없어도 된다
- usage hold, capture, release 호출도 없다

호환 규칙:

- 현재 service usage enum은 `mask|translate|inpaint`만 받는다
- 그래서 model의 `detect` 작업은 usage create 시 임시로 `mask`로 매핑한다
- UI와 model 사이 외부 계약은 계속 `detect`를 사용한다
- service public enum이 확장되면 이 임시 매핑은 제거 가능하다

## What Is Fixed Now

- cloud auth token은 `session_key` 하나
- service error envelope shape
- usage hold, capture, release 흐름
- model bridge의 service pass-through 동작
- `UI -> model` direct async job boundary와 auth/usage 책임 분리
- browser URL과 compose internal URL 구분

## What Still Needs Implementation

- `GET /v1/jobs/{job_id}` persistent status store
- 번역 pipeline의 실제 stage 구현
- model-side artifact transport와 최종 cross-engine result schema
- `pipeline` operation의 실제 지원

## Out Of Scope

- `UI engine` 내부 세션 보관 방식
- `model engine` 내부 pipeline 세부 구현
- 별도 runtime session이나 reconnect 정책
- 외부 결제 시스템
- cloud launch, exchange, heartbeat
