# Session And Credential Implementation

`model_engine` 구현자가 cloud/standalone 모드에서 세션과 provider credential을 어떻게 다뤄야 하는지 정리한 구현 준비 문서다.

이 문서는 현재 canonical boundary 문서와 현재 `model_engine` 구현을 함께 읽고 정리한 것이다.

관련 문서:

- `docs/http-contract.md`
- `docs/service-engine-boundary.md`
- `docs/ui-model-abstract-boundary.md`
- `ui_engine/towa-app/src/backend/real.ts`
- `model_engine/api/app.py`
- `model_engine/api/service_bridge.py`
- `model_engine/api/jobs.py`
- `model_engine/orchestrator.py`
- `model_engine/credentials/resolver.py`
- `service_engine/app/api/dependencies.py`
- `service_engine/app/api/routers/auth.py`
- `service_engine/app/api/routers/usage.py`
- `service_engine/app/modules/billing/service.py`

## 1. 목적

이 문서의 목적은 아래 두 가지를 혼동하지 않게 하는 것이다.

1. `session_key`는 누가 발급하고 누가 검증하는가
2. provider API key는 누가 보관하고 누가 실제 stage에 주입하는가

핵심 요약은 다음과 같다.

- 세션 authority는 `service_engine`이다.
- provider credential의 resolve/inject 책임은 `model_engine` runtime에 있다.
- `model_engine`은 cloud 모드에서 bearer를 요구하지만, bearer의 실질 유효성은 service 호출 경로에서 service가 판정한다.

## 2. 현재 확정된 책임 경계

### 2.1 Service engine이 소유하는 것

- `session_key` 발급과 유효성 판단
- credit balance, reserved units, usage hold/capture/release
- cloud project/page snapshot authority

즉 `service_engine`은 인증과 사용량 authority다.

### 2.2 Model engine이 소유하는 것

- AI job 실행
- stage orchestration
- provider credential resolve/inject
- SaaS job owner scope 판정
- usage hold/capture/release를 service에 요청하는 책임

즉 `model_engine`은 추론 실행 주체이며, 인증 authority 자체는 아니지만 cloud 실행의 auth gate와 usage bridge 역할은 가진다.

## 2.3 실제 API 함수 기준 검증 결과

현재 문서 내용은 아래 실제 API 함수들과 대체로 호환된다.

### UI engine

`ui_engine/towa-app/src/backend/real.ts`

- `auth.devLogin()` -> `POST /auth/dev/login`
- `auth.getCurrentUser()` -> `GET /auth/me`
- `aiJobs.createJob()` -> `POST /v1/jobs`
- `aiJobs.getJob()` -> `GET /v1/jobs/{job_id}`

이때 `createJob()`과 `getJob()`은 `authorizationHeaders()`를 통해 `Authorization: Bearer <session_key>`를 `model_engine`에 붙인다.

### Model engine HTTP API

`model_engine/api/app.py`

- `POST /v1/jobs`는 raw `Authorization` 헤더를 그대로 `ModelJobManager.create_job()`에 넘긴다.
- `GET /v1/jobs/{job_id}`도 raw `Authorization` 헤더를 그대로 `ModelJobManager.get_job()`에 넘긴다.

즉 현재 `model_engine` HTTP API는 bearer를 자체적으로 파싱하지 않고 string 그대로 job manager에 전달하는 구조다.

### Model -> service bridge

`model_engine/api/service_bridge.py`

- `ServiceEngineBridgeClient`는 `authorization` 문자열을 그대로 upstream request header에 넣는다.

`model_engine/service_engine/client.py`

- `ServiceEngineClient`는 `session_key`를 받아 `_bearer_token()`으로 `Bearer <session_key>`를 만든다.
- direct runner path는 raw `Authorization` 헤더가 아니라 plain `session_key`를 입력으로 받는 형태다.

### Service engine

`service_engine/app/api/dependencies.py`

- `get_session_token()`은 `Authorization: Bearer <session_key>`에서 bearer 토큰 본문만 추출한다.

`service_engine/app/modules/billing/service.py`

- usage create/capture/release/get은 모두 `auth_service.authenticate_session_token()`를 다시 호출한다.
- usage job 조회는 `(user_id, job_id)`로 로드된다.

즉 usage 관련 session 유효성 검증과 usage job ownership은 service 쪽에서도 강하게 보장된다.

## 3. Session 처리 규칙

### 3.1 Cloud mode

cloud는 `UI -> model` 호출 시 아래 헤더를 전제로 한다.

```http
Authorization: Bearer <session_key>
```

현재 구현 기준 동작은 다음과 같다.

1. `UI engine`이 `service_engine`에서 받은 `session_key`를 `model_engine`에도 그대로 보낸다.
2. `model_engine`은 `runtime_context.mode=saas`일 때 bearer 헤더가 없으면 즉시 `401 session_key_required`를 반환한다.
3. `model_engine`은 bearer에서 session token 본문을 추출해 `runtime_context.service_session_key`에 저장한다.
4. 이후 usage hold/capture/release는 저장된 `service_session_key`를 사용해 authenticated path로 수행한다.
5. 이 usage 호출 과정에서 session의 실질 유효성은 `service_engine`이 검증한다.

중요:

- 현재 구현은 `service_engine`에 별도의 `/auth/validate` 같은 검증 호출을 먼저 보내지 않는다.
- 세션 유효성 검증은 `POST /usage/jobs`, `POST /usage/jobs/{job_id}/capture`, `POST /usage/jobs/{job_id}/release` 경로에서 service가 수행한다.

### 3.1.1 Direct runner path

현재 코드에는 HTTP API 외에 direct runner 경로도 있다.

`model_engine/orchestrator.py`의 `ServiceBackedPipelineRunner`는:

- `runtime_context.service_session_key`
- `runtime_context.service_base_url`

를 명시적으로 요구한다.

즉 현재 세션 전달 경로는 둘로 나뉜다.

1. HTTP API 경로
- 입력: raw `Authorization` 헤더
- 내부 저장 형태: `runtime_context.service_session_key`
- 사용 위치: `ModelJobManager`

2. direct runner 경로
- 입력: plain `service_session_key`
- 사용 위치: `ServiceBackedPipelineRunner`

둘 다 최종적으로는 service usage API를 호출하지만, 입력 형태가 다르다.

### 3.2 Job 소유권 판정

현재 `model_engine`은 SaaS job 읽기 권한을 service에 다시 묻지 않는다.

대신 아래 방식으로 자체 판정한다.

- 요청 시 받은 `Authorization` 헤더를 정규화한다.
- 그 문자열의 SHA-256 해시를 `owner_scope`로 저장한다.
- 이후 `GET /v1/jobs/{job_id}` 요청에서도 같은 방식으로 `owner_scope`를 계산한다.
- 저장된 `owner_scope`와 다르면 `404 model_job_not_found`를 반환한다.

즉 현재 job 소유권 판정은 `service_engine` 재질의가 아니라 `model_engine` 내부 `owner_scope` 비교다.

주의:

- 이것은 `model_engine`의 AI job 조회 권한 판정 방식이다.
- 별도로 `service_engine`의 usage job은 `user_id + job_id` 기준으로 다시 보호된다.
- 즉 AI job ownership과 usage job ownership은 서로 다른 계층에서 각각 제한된다.

### 3.3 Standalone mode

`runtime_context.mode=local`에서는:

- `service_engine` 호출이 필수가 아니다.
- bearer session auth는 강제가 아니다.
- job owner scope는 local 문맥 기준으로 계산한다.

## 4. Usage/Billing 처리 규칙

cloud 모드에서 billed job의 표준 흐름은 아래와 같다.

1. 작업 생성 시 `POST /usage/jobs`로 hold를 만든다.
2. 작업이 성공하면 `POST /usage/jobs/{job_id}/capture`를 호출한다.
3. 작업이 실패하면 `POST /usage/jobs/{job_id}/release`를 호출한다.

즉 `model_engine`은 사용량을 authoritative하게 기록하지 않고, service에 상태 전이를 요청하는 쪽이다.

이 흐름에서 중요한 구현 원칙:

- billed SaaS job은 usage hold 없이 실행되면 안 된다.
- capture/release 실패는 별도 오류로 기록해야 한다.
- usage authority는 service 쪽에만 남겨야 한다.

## 5. Provider credential 처리 규칙

provider API key는 `service_engine` 소관이 아니다.

더 정확히는:

- provider credential storage owner는 deployment/runtime 환경에 따라 달라질 수 있다.
- provider credential의 resolve/inject 책임은 `model_engine` runtime에 있다.

현재 `model_engine`이 다루는 credential source는 아래와 같다.

### 5.1 Cloud/SaaS

기본 경로는 `platform managed` credential이다.

예:

- secret manager
- container/env injected secret
- platform-level provider key

### 5.2 Local/Standalone

기본 경로는 아래 둘이다.

- `session_provider_secrets`
- local persisted config or file

예:

- `~/.config/towa/model_engine/credentials.json`
- `TOWA_CREDENTIALS_FILE`로 지정한 사용자 credentials file
- runtime payload에 실린 session secret

중요:

- `DefaultCredentialResolver`가 읽는 persisted credential 기본 경로는 `.runtime/runtime_config.json`이 아니다.
- 기본 persisted 경로는 `~/.config/towa/model_engine/credentials.json`이다.
- `.runtime/runtime_config.json`은 샘플 스크립트가 local 실행 편의를 위해 읽는 runtime config이며, 보통 여기서 읽은 값을 `session_provider_secrets`나 stage metadata로 옮겨 넣는다.

현재 샘플 경로 예:

- `model_engine/scripts/run_translation_sample.py`
- `model_engine/scripts/run_pipeline_sample.py`

이 스크립트들은 `.runtime/runtime_config.json`을 직접 읽은 뒤 `session_provider_secrets`를 채운다.

### 5.3 Stage 주입

credential은 orchestrator가 stage 실행 직전에 resolve해서 stage request에 넣는다.

즉 stage는 직접 저장소를 뒤지지 않고, runtime이 공급한 resolved credential만 사용해야 한다.

현재 구현 기준 세부 규칙:

- `ExecutionMode.SAAS`에서는 `PLATFORM_MANAGED`
- `ExecutionMode.LOCAL`에서는 우선 `USER_PERSONAL_SESSION`, 없으면 `USER_PERSONAL_PERSISTED`

즉 cloud와 local의 기본 credential path는 코드상으로도 분기되어 있다.

## 6. 서버리스 실행을 고려한 구현 포인트

동기 HTTP 처리만 보면 현재 구조는 서버리스와도 잘 맞는다.

- UI가 bearer를 보낸다
- model HTTP endpoint가 bearer를 받는다
- model이 service usage API에 같은 bearer를 전달한다

하지만 진짜 비동기 background job까지 고려하면 추가 고려가 필요하다.

### 6.1 현재 구조에서 안전한 것

- request lifetime 안에서 바로 usage hold 호출
- request lifetime 안에서 바로 short-lived inference 수행
- usage capture/release를 같은 runtime context로 마무리

### 6.2 추가 구현이 필요한 것

job이 request 종료 이후에도 계속 실행되는 구조라면 아래를 명시적으로 정해야 한다.

- `service_session_key`를 job runtime context에 저장할지
- service-to-service internal auth를 새로 둘지
- delayed capture/release에서 어떤 auth principal을 쓸지

현재 코드에는 `runtime_context.service_session_key` 필드가 있으므로, 장기적으로는 bearer를 job context에 명시적으로 보존하는 방향이 자연스럽다.

추가로 direct runner와 HTTP API가 공존하므로 아래도 정리해야 한다.

- HTTP API의 raw `Authorization`와 direct runner의 `service_session_key`를 하나의 canonical contract로 합칠지
- 둘을 병행 유지한다면 어떤 경로가 product path인지

## 7. 구현 체크리스트

현재/다음 구현 체크리스트는 아래와 같다.

### 7.1 현재 유지해야 하는 규칙

- SaaS job create 시 bearer 필수
- usage hold 없이 billed SaaS job 실행 금지
- job read access는 `owner_scope`로 제한
- provider credential resolve는 orchestrator/runtime에서만 수행
- usage API 호출은 항상 bearer 또는 `service_session_key`를 통해 authenticated path로만 수행

### 7.2 다음 구현 과제

- serverless async job 기준 `service_session_key` persistence 정책 확정
- delayed capture/release auth 방식 확정
- provider credential source 우선순위 문서와 코드 일치 여부 검증
- UI/model wire contract가 구체화되면 `runtime_context` 필수 필드 재정의

## 8. 피해야 하는 오해

아래 표현은 현재 구현 기준으로는 부정확하다.

- "`model_engine`이 세션 유효성을 직접 검증한다"
- "`model_engine`이 모든 job 접근 권한을 service에 매번 질의한다"
- "`service_engine`이 provider API key를 저장하고 내려준다"
- "local persisted credential은 `.runtime/runtime_config.json`에서 자동으로 resolve된다"

현재 더 정확한 표현은 아래다.

- `model_engine`은 SaaS auth gate를 수행하지만, session authority는 service에 있다.
- job 소유권 판정은 현재 `model_engine` 내부 `owner_scope` 비교다.
- provider credential resolve/inject 책임은 `model_engine` runtime에 있다.
- `.runtime/runtime_config.json`은 샘플 실행 편의용 runtime config이지, `DefaultCredentialResolver`의 persisted credential source 그 자체는 아니다.
