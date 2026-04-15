# Service Engine Boundary v0

현재 `service_engine`은 merge 전 개발용 authority stub이다.
목표는 다른 engine과 붙기 전에 `세션 검증`, `credit hold/capture/release`, `usage ledger` 경계를 먼저 고정하는 것이다.

## Summary

- 실행은 `model engine`
- 사람 진입은 `UI engine`
- 세션, credit, usage 기록 authority는 `service engine`
- 현재 구현은 `dev login + single session_key` 기준의 축소판이다

즉, 최종 SaaS 전체를 먼저 구현하는 대신, 다른 engine이 맞출 수 있는 경계와 상태 전이부터 고정한 단계다.

## What Service Engine Owns

- 유저 identity의 최소 상태
- 세션 키 유효성 판단
- credit account의 잔액과 reserved amount
- usage job 상태
- capture 시 credit ledger 기록

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
- 중앙 파일 저장소

즉, 작업의 내용은 `model engine`에 남기고, 작업의 권한과 정산 상태만 `service engine`이 가진다.

## Current Interaction Boundary

### UI engine

- `POST /auth/dev/login` 호출
- 받은 `session_key`를 보관
- 필요 시 `model engine`에 같은 bearer를 전달

### Model engine

- billed job 시작 전 `POST /usage/jobs`
- 성공 시 `POST /usage/jobs/{job_id}/capture`
- 실패 시 `POST /usage/jobs/{job_id}/release`
- 필요 시 `GET /usage/jobs/{job_id}` 조회

### Service engine

- `session_key` 검증
- 잔액, 예약, 확정 차감 처리
- idempotency 보장
- 공통 error envelope 유지

## Fixed Design Choices For v0

- 토큰은 `session_key` 하나만 쓴다
- `estimated_units`는 `model engine`이 계산해서 보낸다
- service는 가격 계산이 아니라 세션, 잔액, 상태 전이 authority 역할만 한다
- capture 금액은 현재 `estimated_units`와 동일하다
- release는 hold만 풀고 ledger는 남기지 않는다
- hold expiry cleanup은 background worker가 아니라 usage 요청 흐름에서 lazy하게 수행한다
- 잔액과 hold 변경은 단일 트랜잭션으로 처리한다
- credit account에는 동시성 보호가 필요하며, 현재 구현은 version 기반 optimistic locking을 사용한다

## Operational Assumptions

- v0 인증 방식은 `dev login`만 지원한다
- `UI engine`이 받은 bearer를 `model engine`이 그대로 전달한다
- 신규 유저 기본 credit은 `1000 units`다
- session TTL 기본값은 `24시간`이다
- hold TTL 기본값은 `30분`이다

## Non-Goals For This Phase

- multi-token auth
- refresh, logout
- model session registration
- cloud launch, exchange
- heartbeat, reconnect
- cloud runtime provisioning
- object storage 상세 설계
- provider 호출 대행
- 이미지, OCR, 결과물 영속 저장

## Pre-Merge Readiness Criteria

- 다른 engine 개발자가 구현 코드를 읽지 않고도 [http-contract.md](http-contract.md)만 보고 호출 가능해야 한다
- OpenAPI와 테스트가 현재 wire contract를 고정해야 한다
- dev CLI로 유저 seed, credit 보정, migration을 서비스 엔진 단독으로 수행할 수 있어야 한다
