# TOWA Service Engine v0 초안

## Summary
- 현재 [TOWA 루트](/home/user/dev/TOWA)는 `ui_engine`, `service_engine`, `model_engine` 3개 디렉터리만 있는 골격 상태다.
- 참고용 [after-trit server-engine](/home/user/dev/after-trit/server-engine)는 FastAPI + SQLAlchemy + Alembic 기반의 풀 버전이며, OAuth, cloud launch/exchange, client heartbeat, usage/billing, sweeper까지 포함한다.
- 이번 초안은 저 레퍼런스를 그대로 옮기지 않고, 그림에 있는 흐름만 남긴 축소판으로 간다.
- 목표 범위는 `로그인 -> 세션 키 발급 -> 모델 엔진의 credit hold 요청 -> 성공 시 capture / 실패 시 release` 까지다.
- 제외 범위는 Google OAuth, access/refresh/client/launch 다중 토큰, heartbeat/reconnect/sweeper, cloud runtime provisioning, 원본 이미지/결과 파일 저장이다.

## Implementation
- [service_engine](/home/user/dev/TOWA/service_engine)에 새 FastAPI 앱을 부트스트랩한다. 구조는 `app/api`, `app/core`, `app/db`, `app/modules`, `alembic`, `tests`로 고정한다.
- 런타임 저장소는 PostgreSQL, 테스트는 SQLite로 간다. `after-trit`의 설정/DB 세션/에러 envelope 패턴만 재사용하고, `clients/*`, OAuth, sweeper 코드는 가져오지 않는다.
- 데이터 모델은 `users`, `auth_sessions`, `credit_accounts`, `usage_jobs`, `credit_holds`, `credit_ledger` 6개만 둔다.
- `usage_jobs`는 `(user_id, idempotency_key)` 유니크로 잡고, 상태는 `authorized | succeeded | failed`만 둔다.
- `credit_holds` 상태는 `held | captured | released`만 둔다.
- 서비스 엔진은 이미지, OCR 원문, 생성 결과, 외부 API 키를 저장하지 않는다. 이 데이터는 모델 엔진 경계 밖으로 내보내지 않는다.
- 잔액/예약금 변경은 단일 트랜잭션으로 처리하고, `credit_accounts`에는 optimistic locking 또는 row lock을 적용해 이중 hold를 막는다.

## Public Interfaces
- `POST /auth/dev/login`
- 입력: `email`, 선택 `nickname`
- 동작: 유저가 없으면 생성하고 credit account도 생성, 세션 키 발급
- 응답: `session_key`, `expires_in`, `user`, `credit_balance`, `reserved_units`
- `GET /auth/me`
- 인증: `Authorization: Bearer <session_key>`
- 응답: 현재 유저와 credit 요약
- `POST /usage/jobs`
- 인증: 동일한 `session_key`
- 호출자: 모델 엔진
- 입력: `idempotency_key`, `operation_kind`, `request_ref`, `estimated_units`
- 동작: 세션 검증 후 잔액 확인, hold 생성, usage job 생성
- 응답: `job_id`, `status=authorized`, `reserved_units`, `hold_expires_at`
- `POST /usage/jobs/{job_id}/capture`
- 인증: 동일한 `session_key`
- 동작: held 금액을 최종 차감하고 ledger 기록, job을 `succeeded`로 전이
- `POST /usage/jobs/{job_id}/release`
- 인증: 동일한 `session_key`
- 입력: 선택 `error_code`, `reason`
- 동작: held 금액 해제, job을 `failed`로 전이
- `GET /usage/jobs/{job_id}`
- 용도: 디버깅 및 검증용 상태 조회
- 모든 오류 응답은 `after-trit`과 같은 공통 envelope를 유지한다. 기본 코드는 `401` 세션 오류, `404` 없는 job, `409` 잔액 부족/잘못된 상태 전이로 고정한다.

## Test Plan
- dev login이 신규 유저/기존 유저 모두에서 정상 동작하고 최초 로그인 시 기본 credit이 세팅되는지 검증
- `GET /auth/me`가 유효 세션과 만료/취소 세션을 정확히 구분하는지 검증
- `POST /usage/jobs`가 hold와 job 생성을 원자적으로 처리하고, 잔액 부족 시 둘 다 생성되지 않는지 검증
- 같은 `(user_id, idempotency_key)`에 대해 create가 idempotent한지 검증
- capture가 1회만 차감되고 중복 호출에도 금액이 추가 차감되지 않는지 검증
- release가 1회만 해제되고 중복 호출에도 상태/잔액이 깨지지 않는지 검증
- 동시 요청 2개가 같은 잔액을 경쟁할 때 초과 hold가 생기지 않는지 검증
- OpenAPI와 공통 error envelope 스키마가 노출되는지 검증

## Assumptions
- 인증 방식은 v0에서 `Dev 로그인`만 지원한다.
- UI가 받은 단일 `session_key`를 작업 요청에 포함하고, 모델 엔진도 그 키를 그대로 서비스 엔진에 전달한다.
- hold 수량은 모델 엔진이 `estimated_units`로 전달하고, 서비스 엔진은 금액 계산이 아니라 세션/잔액/상태를 authoritative 하게 판단한다.
- v0에서는 capture 시 실제 차감량을 다시 계산하지 않고, hold된 `reserved_units`를 그대로 확정 차감한다.
- 기본값은 `session TTL 24시간`, `hold TTL 30분`, `신규 유저 초기 credit 1000 units`로 둔다.
