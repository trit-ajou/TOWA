# Inter-Engine HTTP Contract v0

현재 브랜치의 엔진 간 통신 기준 문서다.
목표는 `UI engine`, `service engine`, `model engine` 개발자가 같은 wire contract를 보고 맞출 수 있게 하는 것이다.

이 문서는 두 층을 함께 다룬다.

- `현재 구현되어 있는 contract`
- `다음으로 고정할 추천 contract`

## Scope

- 전송 방식: `HTTP REST`
- payload: `application/json; charset=utf-8`
- 공통 actor:
  - `UI engine`: 사용자 진입점
  - `service engine`: 세션/credit/usage authority
  - `model engine`: AI 작업 실행 주체
- 제외:
  - websocket/sse streaming
  - cloud launch/exchange/heartbeat
  - object storage 상세 설계
  - provider API 세부 프로토콜

## Deployment Modes

### Cloud

- `UI -> service`: 로그인, 세션 확인
- `UI -> model`: 작업 요청
- `model -> service`: hold/capture/release

UI의 `deployment mode=cloud`는 model 쪽 `runtime_context.mode=saas`에 대응한다.

### Standalone

- `UI -> model`만 필수
- `service engine`은 없어도 된다
- 개인 API 키 또는 로컬 모델 경로는 `model engine` 내부 정책으로 처리한다

UI의 `deployment mode=standalone`은 model 쪽 `runtime_context.mode=local`에 대응한다.

## Base URLs

### Browser-facing

- `UI`: `http://localhost:5173`
- `service`: `http://localhost:8000`
- `model`: `http://localhost:8100`

### Docker internal

- `service-engine`: `http://service-engine:8000`
- `model-engine`: `http://model-engine:8100`
- `db`: `postgresql://db:5432`

브라우저와 컨테이너 내부 주소는 다르다.
그래서 UI env는 `localhost` 기준, 컨테이너 간 호출은 compose service name 기준으로 맞춘다.

## Shared Rules

### Auth

- cloud 모드에서 세 엔진 간 사용자 식별 토큰은 현재 `session_key` 하나만 사용한다
- 전달 방식:

```http
Authorization: Bearer <session_key>
```

- `UI engine`이 `service engine`에서 받은 `session_key`를 `model engine`에도 그대로 보낸다
- `model engine`은 billing/usage 관련 service 호출에 같은 헤더를 그대로 전달한다

### Request Correlation

가능하면 아래 헤더를 추가한다.

```http
X-Towa-Request-Id: <client-generated-request-id>
```

- UI가 생성
- model이 service 호출 시 그대로 전달
- 로그/트레이싱 용도

현재 구현 필수는 아니지만, inter-engine 디버깅 기준으로 권장한다.

### Time Format

- 모든 timestamp는 UTC ISO-8601 문자열을 사용한다
- 예: `2026-03-29T06:15:00Z`

### Idempotency

- `service engine`의 usage create는 body의 `idempotency_key`를 authoritative key로 사용한다
- `model engine`의 작업 create도 body에 `idempotency_key`를 둔다
- UI는 "한 번의 사용자 의도"마다 stable key를 생성해야 한다

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

- `service engine`은 이미 이 형식을 사용한다
- `model engine`도 가능하면 같은 envelope을 사용한다
- `502`가 필요할 때 model은 `service_engine_unreachable` 같은 code를 쓴다

권장 model error code:

- `model_validation_error`
- `model_job_not_found`
- `model_job_conflict`
- `model_stage_failed`
- `service_engine_unreachable`

### Large Payload Rule

큰 비트맵을 JSON 본문에 base64로 직접 넣는 것은 inter-engine 기준 계약으로 채택하지 않는다.

규칙:

- 작은 메타데이터는 JSON 본문
- 큰 이미지/마스크/OCR raw/result는 artifact descriptor로 전달
- descriptor는 `uri`를 통해 실제 payload 위치를 가리킨다

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

## Pairwise Contract

## UI -> Service

현재 구현 기준:

- `POST /auth/dev/login`
- `GET /auth/me`

자세한 schema는 [service_engine/API_CONTRACT.md](/home/user/dev/TOWA/service_engine/API_CONTRACT.md)를 따른다.

UI 책임:

- 로그인으로 `session_key` 획득
- 세션 키 보관
- model 호출 시 같은 `Authorization` 헤더 전달

service 책임:

- 세션 유효성 판단
- credit/usage authority 유지

## Model -> Service

현재 구현 기준:

- `POST /usage/jobs`
- `POST /usage/jobs/{job_id}/capture`
- `POST /usage/jobs/{job_id}/release`
- `GET /usage/jobs/{job_id}`

자세한 schema는 [service_engine/API_CONTRACT.md](/home/user/dev/TOWA/service_engine/API_CONTRACT.md)를 따른다.

규칙:

1. billed operation 시작 전 `POST /usage/jobs`
2. 성공 시 `capture`
3. 실패 시 `release`
4. 같은 `Authorization: Bearer <session_key>` 헤더를 그대로 사용

호환 규칙:

- 현재 service usage enum은 `mask|translate|inpaint`만 받는다
- 그래서 model의 `detect` 작업은 usage create 시 임시로 `mask`로 매핑한다
- UI와 model 사이 외부 계약은 계속 `detect`를 사용한다

## Current Model Bridge

현재 `model engine`에는 service 연동 smoke test용 bridge endpoint가 있다.

- `GET /healthz`
- `GET /bridge/service/healthz`
- `GET /bridge/service/auth/me`
- `POST /bridge/service/usage/jobs`
- `POST /bridge/service/usage/jobs/{job_id}/capture`
- `POST /bridge/service/usage/jobs/{job_id}/release`
- `GET /bridge/service/usage/jobs/{job_id}`

이 bridge는 현재 service contract를 거의 그대로 중계한다.
목적은 다음 두 가지다.

- docker bring-up 확인
- model -> service auth/billing pass-through 검증

주의:

- 이 경로는 개발용 bridge다
- 최종 UI가 service API를 model bridge를 통해 우회 호출하는 구조를 기본 계약으로 삼지는 않는다

자세한 내용은 [model_engine/API_CONTRACT.md](/home/user/dev/TOWA/model_engine/API_CONTRACT.md)를 따른다.

## UI -> Model

현재 placeholder job API까지 구현된 구간이다.
아래를 현재 v0 계약으로 둔다.

### Health

```http
GET /healthz
```

응답:

```json
{
  "status": "ok"
}
```

### Create Job

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
  - 서비스 usage 정산의 `request_ref`와 같은 의미를 갖는다
- `document`
  - Bitmappery 의미론 기반 `DocumentIR`
- `artifacts`
  - 큰 payload는 반드시 여기의 ref/uri로 전달
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

권장 상태 코드는 `202 Accepted`다.

### Get Job

```http
GET /v1/jobs/{job_id}
Authorization: Bearer <session_key>   # cloud only
```

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

`status`는 아래를 권장한다.

- `queued`
- `running`
- `succeeded`
- `failed`
- `partial`

terminal state:

- `succeeded`
- `failed`
- `partial`

### Operation Mapping

외부 `operation_kind`와 내부 stage capability는 아래처럼 매핑하는 것을 권장한다.

- `detect` -> `text_detection`
- `inpaint` -> `text_detection`, `mask_or_erase_planning`, `inpaint`
- `translate` -> `text_detection`, `ocr`, `translation`
- `pipeline` -> 명시된 pipeline config에 따름

현재 구현 상태:

- `detect` 관련 built-in 있음
- `inpaint` 관련 built-in 있음
- `translate` pipeline은 아직 미완성

따라서 `translate`는 계약을 먼저 고정하고 구현이 뒤따르는 상태로 본다.

## Billing Boundary

원칙:

- UI는 billing/credit을 직접 계산하지 않는다
- model은 billed job 시작/종료 시점만 판단한다
- service는 잔액/상태 authority다

cloud billed flow:

1. UI가 service에서 `session_key` 획득
2. UI가 model에 작업 요청
3. model이 `POST /usage/jobs`
4. model 작업 성공 시 `capture`
5. model 작업 실패 시 `release`
6. UI는 필요하면 model job 상태와 service credit 상태를 별도로 조회

standalone flow:

- service 없음
- `Authorization` 헤더 없어도 됨
- usage hold/capture/release 호출도 없음

## What Is Fixed Now

- cloud auth token은 `session_key` 하나
- service error envelope shape
- usage hold/capture/release 흐름
- model bridge의 service pass-through 동작
- UI는 browser URL, model/service는 internal compose URL을 사용

## What Still Needs Implementation

- `UI -> model` 실제 `POST /v1/jobs`
- `GET /v1/jobs/{job_id}` persistent status store
- 번역 pipeline의 실제 stage 구현
- 대용량 artifact 전달용 storage 정책

## Local Bring-Up

```bash
cp .env.example .env
docker compose up --build
```

기본 포트:

- UI: `5173`
- Service: `8000`
- Model: `8100`
- Postgres: `5432`
