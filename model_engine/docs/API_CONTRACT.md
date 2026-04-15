# Model Engine HTTP Contract v0

`model_engine`이 외부와 주고받는 HTTP 계약 요약본이다.
세 엔진 전체 관점의 기준 문서는 [INTER_ENGINE_HTTP.md](../../INTER_ENGINE_HTTP.md)다.

## Current Implemented Endpoints

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
- `/v1/jobs`: placeholder job create/status API
- `bridge/service/*`: service contract pass-through smoke test

## Auth Rule

- cloud 모드에서는 `Authorization: Bearer <session_key>`를 그대로 받는다
- `saas` job과 bridge 호출 시 같은 헤더를 `service_engine`으로 전달한다
- standalone 모드에서는 auth가 없어도 된다
- `saas`의 `GET /v1/jobs/{job_id}`도 같은 bearer가 필요하다
- 다른 caller가 만든 `saas` job을 조회하면 `404 model_job_not_found`를 반환한다

## Error Rule

- service가 돌려준 오류는 가능하면 그대로 전달한다
- service가 unreachable이면 model은 `502`와 아래 오류를 돌린다

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

## Job Contract

현재 구현된 UI -> model 작업 계약:

- `POST /v1/jobs`
- `GET /v1/jobs/{job_id}`

요청/응답 shape는 [INTER_ENGINE_HTTP.md](../../INTER_ENGINE_HTTP.md)의 `UI -> Model` 섹션을 따른다.

현재 성격:

- 내부 실행은 placeholder executor 기반이다
- local/`saas` 모두 동일한 job API를 사용한다
- `pipeline`은 아직 `422 model_validation_error`다
- idempotency scope는 caller별로 분리된다
  - `saas`: bearer 기준
  - `local`: `runtime_context.requested_by` 또는 local default
- 같은 scope에서 같은 `idempotency_key`를 다른 payload로 재사용하면 `409 model_job_conflict`를 반환한다

## Billing Compatibility Note

현재 `service_engine` usage enum은 `mask|translate|inpaint`만 받는다.
그래서 `model_engine`은 `detect` 작업을 billing create 단계에서 임시로 `mask`로 매핑한다.

이 규칙은 service public enum이 확장되기 전까지의 런타임 호환 규칙이다.
