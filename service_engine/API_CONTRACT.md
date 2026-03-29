# Service Engine API Contract v0

현재 `service_engine`의 merge 전 기준 계약 문서다.
이 문서는 지금 구현된 `dev login + single session_key + credit hold/capture/release` 흐름만 다룬다.
세 엔진 전체 기준 계약은 [INTER_ENGINE_HTTP.md](/home/user/dev/TOWA/INTER_ENGINE_HTTP.md)에서 함께 본다.

## Scope

- 대상 actor: `UI engine`, `model engine`, `service engine`
- 모드: 현재는 merge 전 개발용 `v0` 계약만 정의한다
- 제외: launch/exchange, refresh/logout, heartbeat, 별도 model token, 이미지/OCR/result payload 저장

## Actors

- `UI engine`: 사람 로그인과 세션 획득 주체
- `model engine`: 실제 작업 실행 주체, hold/capture/release 호출자
- `service engine`: 세션 검증, credit authority, usage ledger authority

## Token Model

현재는 토큰이 하나뿐이다.

- `session_key`
  - `POST /auth/dev/login`에서 발급
  - `Authorization: Bearer <session_key>`로 전달
  - `GET /auth/me`, `POST /usage/jobs`, `POST /usage/jobs/{job_id}/capture`, `POST /usage/jobs/{job_id}/release`, `GET /usage/jobs/{job_id}`에 사용

중요한 점:

- 아직 `model engine` 전용 토큰은 없다
- `UI engine`이 얻은 `session_key`를 `model engine`이 그대로 사용한다
- idempotency scope는 `user_id + idempotency_key`다

## Error Envelope

모든 JSON 오류 응답은 아래 형태를 사용한다.

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

기본 규칙:

- `401`: 세션 누락/무효/만료
- `404`: 없는 `job_id`
- `409`: 잔액 부족, 잘못된 상태 전이, 동시성 충돌
- `422`: body/path validation 실패

주요 `error.code`:

- `session_key_required`
- `session_invalid`
- `session_expired`
- `validation_error`
- `insufficient_credits`
- `usage_job_not_found`
- `usage_conflict`
- `missing_credit_account`
- `concurrent_update_conflict`

## Endpoint Contract

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

- `email`은 trim/lowercase 처리
- 기존 유저면 새 `session_key`를 다시 발급
- `nickname`이 들어오면 기존 유저 닉네임도 갱신

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
- 같은 유저가 같은 `idempotency_key`를 다른 payload로 재사용하면
  `409 usage_conflict`와 `details.reason=idempotency_payload_mismatch`를 반환한다
- 사용 가능한 credit이 부족하면 `409 insufficient_credits`
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
- 이미 `failed`인 job에 capture하면 `409 usage_conflict`
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

- `error_code`, `reason`은 optional
- 둘 다 없으면 `error_code`는 `job_released`로 저장된다
- 이미 `failed`인 job에 다시 release하면 같은 실패 상태를 반환한다
- 이미 `succeeded`인 job에 release하면 `409 usage_conflict`

### `GET /usage/jobs/{job_id}`

용도:

- 개별 job 상태 조회

응답:

- `UsageJobResponse`
- 현재 세션 유저 소유 job만 조회 가능
- 다른 유저 job이면 `404 usage_job_not_found`

## State Rules

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

## Invariants

- `service engine`은 이미지, OCR 원문, 생성 결과, provider secret을 저장하지 않는다
- `service engine`은 `estimated_units`의 business authority가 아니라 세션/잔액/상태 authority다
- capture/release는 같은 `job_id`에 대해 idempotent 하게 동작해야 한다
- `credit_ledger`는 capture 때만 증가한다
- release는 ledger entry를 만들지 않는다

## Out Of Scope

- `UI engine`의 세션 전달 방식
- `model engine` 내부 pipeline
- 별도 runtime session이나 reconnect 정책
- 외부 결제 시스템
- cloud launch / exchange / heartbeat
