# Service Engine Boundary v1

현재 `service_engine`은 merge 전 authority stub에서 출발하지만, 이 브랜치의 v1 목표는 아래 두 축을 함께 고정하는 것이다.

- `세션 검증`, `credit hold/capture/release`, `usage ledger`
- cloud 모드의 `project/page snapshot` persistence authority

## Summary

- 실행은 `model engine`
- 사람 진입은 `UI engine`
- 세션, credit, usage 기록 authority는 `service engine`
- cloud `project/page` 저장 authority도 `service engine`이 가진다
- 현재 구현은 `dev login + usage + project/page storage API`까지 포함한다

즉, 최종 SaaS 전체를 먼저 구현하는 대신 다른 engine이 맞출 수 있는 저장/정산 경계부터 먼저 고정한 단계다.

## What Service Engine Owns

- 유저 identity의 최소 상태
- 세션 키 유효성 판단
- credit account의 잔액과 reserved amount
- usage job 상태
- capture 시 credit ledger 기록
- folder tree metadata
- project metadata
- page summary 목록
- page snapshot의 persistence authority

현재/목표 데이터 모델 범주:

- `users`
- `auth_sessions`
- `credit_accounts`
- `usage_jobs`
- `credit_holds`
- `credit_ledger`
- `folders`
- `projects`
- `pages`
- page snapshot binary storage

## What Service Engine Does Not Own

- bitmappery `layer_blob` 내부 구조
- `textBlocks`와 bitmappery text layer의 동기화 규칙
- provider API key
- 모델 선택 로직
- 실제 pipeline 실행 상태
- AI 작업 결과의 의미 해석
- export 포맷 상세
- `UI <-> model` 세부 payload/result wire shape

즉, service는 cloud 저장의 authority이지만 편집 엔진의 내부 semantics나 AI 실행 semantics를 소유하지 않는다.

## Current Interaction Boundary

### UI engine

- `POST /auth/dev/login`
- `GET /auth/me`
- cloud에서 folder CRUD/trash/restore
- cloud에서 project CRUD
- cloud에서 page summary 조회
- cloud에서 page snapshot load/save/delete
- 필요 시 `model engine`에 같은 bearer 전달

### Model engine

- billed job 시작 전 `POST /usage/jobs`
- 성공 시 `POST /usage/jobs/{job_id}/capture`
- 실패 시 `POST /usage/jobs/{job_id}/release`
- 필요 시 `GET /usage/jobs/{job_id}` 조회

### Service engine

- `session_key` 검증
- 잔액, 예약, 확정 차감 처리
- usage idempotency 보장
- cloud project/page snapshot 저장/조회
- cloud folder/project trash 상태 관리
- private page thumbnail fetch
- 공통 error envelope 유지

## Fixed Design Choices For v1

- 토큰은 `session_key` 하나만 쓴다
- `estimated_units`는 `model engine`이 계산해서 보낸다
- service는 가격 계산이 아니라 세션, 잔액, 상태 전이 authority 역할만 한다
- capture 금액은 현재 `estimated_units`와 동일하다
- release는 hold만 풀고 ledger는 남기지 않는다
- hold expiry cleanup은 background worker가 아니라 usage 요청 흐름에서 lazy하게 수행한다
- 잔액과 hold 변경은 단일 트랜잭션으로 처리한다
- credit account에는 동시성 보호가 필요하며, 현재 구현은 version 기반 optimistic locking을 사용한다
- cloud page 저장 단위는 자산별 세분화가 아니라 `page snapshot` 전체다
- page snapshot transport는 `multipart`를 사용한다
- page summary와 full snapshot은 분리한다
- page save 정책은 `last-write-wins`다
- page create는 append-only다
- page delete는 hard delete + dense reindex다
- folder와 project delete는 기본적으로 trash 이동이며, `permanent=true`일 때 hard delete한다
- folder tree depth 제한은 UI가 담당하고 service는 저장/권한/무결성만 담당한다
- `original image`는 immutable이 아니라 current page snapshot의 일부다
- `layer_blob`과 project `config`는 service 기준 opaque payload다
- `textBlocks`는 service 기준 구조화된 page metadata다
- project `thumbnail_url`은 nullable opaque metadata다
- page summary `thumbnail_url`은 private service URL이다
- snapshot binary backend는 현재 DB BLOB이다
- AI 결과를 project/page에 최종 반영하는 주체는 `UI engine`이다
- `model engine -> service engine` 직접 통신 범위는 auth/usage로 제한한다

## Operational Assumptions

- 인증 방식은 현재 `dev login`이 기준이다
- `UI engine`이 받은 bearer를 `model engine`이 그대로 전달한다
- 신규 유저 기본 credit은 `1000 units`다
- session TTL 기본값은 `24시간`이다
- hold TTL 기본값은 `30분`이다
- standalone의 project/page 저장은 UI 내부 IndexedDB가 담당한다
- cloud의 folder/project/page 저장은 service API가 담당한다
- project cover 선택과 cover 깨짐 후속 갱신은 UI가 담당한다

## Non-Goals For This Phase

- multi-token auth
- refresh, logout
- model session registration
- cloud launch, exchange
- heartbeat, reconnect
- cloud runtime provisioning
- export 포맷 상세
- revision/lock/conflict resolution
- collaboration/real-time sync
- page middle insert / reorder
- trash 자동 정리/보관 기간 정책
- bitmappery blob introspection
- `UI <-> model` 상세 wire contract 고정

## Pre-Merge Readiness Criteria

- 다른 engine 개발자가 구현 코드를 읽지 않고도 [http-contract.md](http-contract.md), [project-page-storage-boundary.md](project-page-storage-boundary.md), [ui-model-abstract-boundary.md](ui-model-abstract-boundary.md)를 보고 역할을 맞출 수 있어야 한다
- OpenAPI와 테스트는 `auth`, `usage`, `project/page snapshot` contract를 고정해야 한다
- service storage 구현은 bitmappery blob 내부를 해석하지 않아야 한다
- dev CLI와 migration 경로로 service를 단독 기동하고 상태를 준비할 수 있어야 한다
