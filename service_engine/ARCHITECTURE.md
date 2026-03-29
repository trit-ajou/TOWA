# Service Engine Architecture v0

현재 `service_engine`은 merge 전 개발용 authority stub이다.
목표는 다른 engine과 붙기 전에 `세션 검증`, `credit hold/capture/release`, `usage ledger` 경계를 먼저 고정하는 것이다.

## Summary

- 실행은 `model engine`
- 사람 진입은 `UI engine`
- 세션/credit/usage 기록 authority는 `service engine`

현재 구현은 `dev login + single session_key` 기반이다.
즉, 최종 SaaS 구조 전체를 구현한 것이 아니라, merge 전 공통 계약을 먼저 고정한 단계다.

## What Service Engine Owns

- 유저 identity의 최소 상태
- 세션 키 유효성 판단
- credit account 잔액과 reserved amount
- usage job 상태
- capture 시 ledger 기록

현재 데이터 모델:

- `users`
- `auth_sessions`
- `credit_accounts`
- `usage_jobs`
- `credit_holds`
- `credit_ledger`

## What Service Engine Does Not Own

- 원본 이미지
- OCR 텍스트
- 생성 결과 원본
- provider API key
- 모델 선택 로직
- 실제 pipeline 실행 상태

즉, 작업의 내용은 `model engine`에 남기고, 작업의 권한/정산 상태만 `service engine`이 가진다.

## Current Engine Boundary

### UI engine

- `POST /auth/dev/login` 호출
- 받은 `session_key`를 보관
- 필요 시 `model engine`이 사용할 수 있게 전달

### Model engine

- 작업 실행 전 `POST /usage/jobs`
- 성공 시 `POST /usage/jobs/{job_id}/capture`
- 실패 시 `POST /usage/jobs/{job_id}/release`
- 필요 시 `GET /usage/jobs/{job_id}` 조회

### Service engine

- session_key 검증
- 잔액/예약/확정 차감 처리
- 중복 요청 idempotency 보장
- 에러 envelope 일관성 유지

## Design Choices Fixed For v0

- 토큰은 `session_key` 하나만 쓴다
- `estimated_units`는 `model engine`이 계산해서 보낸다
- service는 가격 계산 대신 잔액/상태 전이 authority 역할만 한다
- capture 금액은 현재 `estimated_units`와 동일하다
- release는 hold만 풀고 ledger는 남기지 않는다
- hold expiry cleanup은 background worker가 아니라 usage 요청 흐름에서 lazy하게 수행한다

## Non-Goals For This Phase

- multi-token auth
- refresh/logout
- model session registration
- cloud launch/exchange
- heartbeat/reconnect
- 중앙 파일 저장소
- provider 호출 대행

이 항목들은 나중에 확장 가능하지만, 현재 merge 전 단독 개발 범위에는 넣지 않는다.

## Pre-Merge Readiness Criteria

- 다른 engine 개발자가 Python 구현을 읽지 않고도 [API_CONTRACT.md](/home/user/dev/TOWA/service_engine/API_CONTRACT.md)만 보고 호출 가능해야 한다
- OpenAPI와 테스트가 현재 wire contract를 고정해야 한다
- dev CLI로 유저 seed, credit 보정, migration을 서비스 엔진 단독으로 수행할 수 있어야 한다

