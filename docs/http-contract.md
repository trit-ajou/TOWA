# HTTP Contract v0

현재 `service_engine` 브랜치의 canonical HTTP contract 문서다.
목표는 `UI engine`, `service engine`, `model engine` 개발자가 같은 wire contract를 보고 구현을 맞출 수 있게 하는 것이다.

이 문서는 현재 구현되어 있는 contract만 다룬다.
설계 경계와 비목표는 [service-engine-boundary.md](service-engine-boundary.md)에서 함께 본다.

## Scope

- 전송 방식: `HTTP REST`
- payload: `application/json; charset=utf-8`
- 공통 actor:
  - `UI engine`: 사용자 진입점
  - `service engine`: 세션, credit, usage authority
  - `model engine`: AI 작업 실행 주체
- 제외:
  - websocket, SSE streaming
  - cloud launch, exchange, heartbeat
  - object storage 상세 설계
  - provider API 세부 프로토콜

## Deployment Modes

### Cloud

- `UI -> service`: 로그인, 세션 확인
- `UI -> model`: 작업 요청
- `model -> service`: hold, capture, release

UI의 `deployment mode=cloud`는 model의 `runtime_context.mode=saas`에 대응한다.

### Standalone

- `UI -> model`만 필수다
- `service engine`은 없어도 된다
- 개인 API 키 또는 로컬 모델 경로는 `model engine` 내부 정책으로 처리한다

UI의 `deployment mode=standalone`은 model의 `runtime_context.mode=local`에 대응한다.

## Caller Matrix

| Caller | Target | Endpoints |
| --- | --- | --- |
| `UI engine` | `service engine` | `POST /auth/dev/login`, `GET /auth/me` |
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
- model 공통:
  - `model_validation_error`
  - `model_job_not_found`
  - `model_job_conflict`
  - `model_stage_failed`
  - `service_engine_unreachable`

### Large Payload Rule

큰 비트맵을 JSON 본문에 base64로 직접 넣는 것은 현재 inter-engine 계약으로 채택하지 않는다.

규칙:

- 작은 메타데이터는 JSON 본문
- 큰 이미지, 마스크, OCR raw, 결과물은 artifact descriptor로 전달
- descriptor는 `uri`로 실제 payload 위치를 가리킨다

artifact descriptor 예시:

```json
{
  "artifact_ref": "artifact://page-original",
  "kind": "bitmap",
  "media_type": "image/png",
  "uri": "https://storage.example.test/page-001.png",
  "width": 1600,
  "height": 2400,
  "byte_size": 2481301,
  "checksum": "sha256:...",
  "producer_stage": "upload"
}
```

## Service Engine Endpoints

### `POST /auth/dev/login`

용도:

- 개발용 로그인
- 신규 유저와 credit account 자동 생성

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

### `GET /auth/me`

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

### `POST /usage/jobs`

호출자:

- `model engine`

헤더:

```http
Authorization: Bearer <session_key>
```

요청:

```json
{
  "idempotency_key": "page-1-translate",
  "operation_kind": "translate",
  "request_ref": "page-1",
  "estimated_units": 20
}
```

응답:

```json
{
  "job_id": "uuid",
  "status": "authorized",
  "reserved_units": 20,
  "hold_expires_at": "2026-03-25T01:00:00Z"
}
```

규칙:

- `estimated_units`는 0보다 커야 한다
- `estimated_units`는 `model engine`이 계산해서 보낸다
- 같은 유저가 같은 `idempotency_key`로 다시 호출하면 같은 `job_id`를 돌려준다
- 같은 유저가 같은 `idempotency_key`를 다른 payload로 재사용하면 `409 usage_conflict`와 `details.reason=idempotency_payload_mismatch`를 반환한다
- 사용 가능한 credit이 부족하면 `409 insufficient_credits`다
- stale hold 정리는 authenticated user 범위에서만 수행한다

### `POST /usage/jobs/{job_id}/capture`

용도:

- 성공한 작업의 hold 확정 차감

요청:

```json
{}
```

응답:

```json
{
  "id": "uuid",
  "operation_kind": "translate",
  "request_ref": "page-1",
  "estimated_units": 20,
  "status": "succeeded",
  "reserved_units": 20,
  "hold_status": "captured",
  "hold_expires_at": "2026-03-25T01:00:00Z",
  "error_code": null,
  "error_detail": null,
  "requested_at": "2026-03-25T00:30:00Z",
  "finished_at": "2026-03-25T00:31:00Z"
}
```

규칙:

- 실제 차감량은 현재 `estimated_units`와 동일하다
- 이미 `succeeded`인 job에 다시 capture하면 같은 성공 상태를 반환한다
- 이미 `failed`인 job에 capture하면 `409 usage_conflict`다
- hold가 만료된 뒤 capture하면 먼저 release 처리되고 `409 usage_conflict`를 반환한다

### `POST /usage/jobs/{job_id}/release`

용도:

- 실패한 작업의 hold 해제

요청:

```json
{
  "error_code": "upstream_error",
  "reason": "timeout"
}
```

응답:

```json
{
  "id": "uuid",
  "operation_kind": "translate",
  "request_ref": "page-1",
  "estimated_units": 20,
  "status": "failed",
  "reserved_units": 20,
  "hold_status": "released",
  "hold_expires_at": "2026-03-25T01:00:00Z",
  "error_code": "upstream_error",
  "error_detail": "timeout",
  "requested_at": "2026-03-25T00:30:00Z",
  "finished_at": "2026-03-25T00:31:00Z"
}
```

규칙:

- `error_code`, `reason`은 optional이다
- 둘 다 없으면 `error_code`는 `job_released`로 저장된다
- 이미 `failed`인 job에 다시 release하면 같은 실패 상태를 반환한다
- 이미 `succeeded`인 job에 release하면 `409 usage_conflict`다

### `GET /usage/jobs/{job_id}`

용도:

- 개별 job 상태 조회

응답:

- `UsageJobResponse`
- 현재 세션 유저 소유 job만 조회 가능하다
- 다른 유저 job이면 `404 usage_job_not_found`다

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

- `service engine`은 이미지, OCR 원문, 생성 결과, provider secret을 저장하지 않는다
- `service engine`은 `estimated_units`의 business authority가 아니라 세션, 잔액, 상태 authority다
- capture, release는 같은 `job_id`에 대해 idempotent 하게 동작해야 한다
- `credit_ledger`는 capture 때만 증가한다
- release는 ledger entry를 만들지 않는다

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
- `/v1/jobs`: placeholder job create, status API
- `bridge/service/*`: service contract pass-through smoke test

### `GET /healthz`

응답:

```json
{
  "status": "ok"
}
```

### `POST /v1/jobs`

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
- `UI -> model`의 `POST /v1/jobs`, `GET /v1/jobs/{job_id}` 기본 계약
- browser URL과 compose internal URL 구분

## What Still Needs Implementation

- `GET /v1/jobs/{job_id}` persistent status store
- 번역 pipeline의 실제 stage 구현
- 대용량 artifact 전달용 storage 정책
- `pipeline` operation의 실제 지원

## Out Of Scope

- `UI engine` 내부 세션 보관 방식
- `model engine` 내부 pipeline 세부 구현
- 별도 runtime session이나 reconnect 정책
- 외부 결제 시스템
- cloud launch, exchange, heartbeat

