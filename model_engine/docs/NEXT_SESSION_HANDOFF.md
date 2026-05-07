# model_engine Next Session Handoff

이 문서는 다음 세션에서 `model_engine` 작업을 바로 재개하기 위한 handoff 메모다.

목표는 두 가지다.

1. 지금 어디까지 정리되었는지 빠르게 복기한다.
2. 다음 구현을 어디서부터 시작해야 하는지 바로 알 수 있게 한다.

## 1. 현재 상태 요약

현재 `model_engine`은 아래까지 정리된 상태다.

- `UI -> model` 입력은 `multipart(metadata + primary_bitmap)` 기준으로 draft와 구현이 맞춰져 있다.
- `POST /v1/jobs`, `GET /v1/jobs/{job_id}`가 동작한다.
- create 응답은 async job shape를 유지한다.
- poll 응답에는 `document_patch`가 포함된다.
- saas 모드에서는 bearer가 `runtime_context.service_session_key`로 정규화된다.
- `model -> service` usage hold/capture/release 경로가 연결돼 있다.
- OCR 튜닝과 translation/openai-compatible 경로는 1차 정리됐다.
- `API + Inference` 통합 서빙 컨테이너 전략은 문서화되었다.

즉 현재 병목은 contract나 개념 부족이 아니라, "실제 serving runtime을 루트 compose 기준으로 어떻게 띄울 것인가"에 가깝다.

## 2. 먼저 읽을 문서

다음 세션 시작 시 아래 문서를 이 순서대로 다시 보면 된다.

1. `README.md`
2. `PROGRESS.md`
3. `SERVING_PLAN.md`
4. `UI_MODEL_CONTRACT_DRAFT.md`
5. `SESSION_AND_CREDENTIAL_IMPLEMENTATION.md`

의도:

- `README.md`
  - `model_engine` 내부 구현 원칙 복기
- `PROGRESS.md`
  - 최근에 실제로 무엇이 반영됐는지 복기
- `SERVING_PLAN.md`
  - 다음 구현의 중심 작업 확인
- `UI_MODEL_CONTRACT_DRAFT.md`
  - UI/model 입출력 계약 확인
- `SESSION_AND_CREDENTIAL_IMPLEMENTATION.md`
  - saas/session/usage 경로 확인

## 3. 다음 구현의 1순위

다음 구현의 1순위는 아래다.

- `Dockerfile.serve` 추가
- root `docker-compose.yml`의 `model-engine`를 serving image로 교체

이 작업의 목적은:

- 지금의 `Dockerfile.api`
  - HTTP API는 되지만 inference runtime이 약함
- 지금의 `Dockerfile.inference`
  - inference는 되지만 batch 컨테이너라 종료됨

이 둘을 합쳐서:

- `/v1/jobs`를 받는 상시 HTTP 서버
- 같은 컨테이너 안에서 실제 OCR/번역/inpaint 실행

이 가능하게 만드는 것이다.

## 4. 구현 시작 시 바로 확인할 코드

다음 세션에서 실제 코드 작업은 아래 파일부터 보면 된다.

- `model_engine/Dockerfile.api`
- `model_engine/Dockerfile.inference`
- `docker-compose.yml`
- `model_engine/api/app.py`
- `model_engine/api/jobs.py`

읽는 목적:

- `Dockerfile.api`
  - 현재 API image가 무엇을 포함하는지 확인
- `Dockerfile.inference`
  - inference runtime에 필요한 system/python dependency 확인
- `docker-compose.yml`
  - root compose의 `model-engine` 서비스 교체 포인트 확인
- `api/app.py`
  - serving app entrypoint 확인
- `api/jobs.py`
  - background execution, executor, usage wiring 확인

## 5. 구현 원칙

다음 세션 구현에서는 아래를 유지해야 한다.

- 외부 계약은 계속 async job 기반으로 유지한다.
- `POST /v1/jobs`가 즉시 결과를 동기 반환하도록 바꾸지 않는다.
- 내부적으로는 현재 `ModelJobManager`의 background thread 경로를 재사용한다.
- 새 background framework를 억지로 도입하지 않는다.
- serving 단계에서는 `uvicorn --workers 1`을 유지한다.
- serving 단계에서는 단일 replica 전제를 문서와 compose에 명시한다.

이유:

- 현재 job store는 in-memory다.
- poll도 같은 프로세스 메모리를 읽는다.
- worker 수나 replica를 늘리면 create/get이 다른 프로세스로 가서 job 조회가 깨질 수 있다.

## 6. 구현 시 주의할 점

### 6.1 `requirements-inference.txt`는 없다

현재 실제 기준 파일은 아래다.

- `requirements-api.txt`
- `requirements-craft.txt`

즉 `Dockerfile.serve`는 새 fictitious requirements 파일을 가정하지 말고, 현재 리포 파일 구조를 기준으로 조합해야 한다.

### 6.2 serving 단계는 "서버리스 최종형"이 아니다

현재 목표는:

- 장기 이상형인 API/worker/durable-store 분리

가 아니라:

- `API + Inference` 통합 서빙 컨테이너

다.

즉 이 단계의 성공 기준은 "운영 최종형"이 아니라 "실제 E2E가 동작하는가"다.

### 6.3 placeholder 경로가 serving 환경에 남지 않게 확인

serving image로 전환한 뒤에는:

- `/v1/jobs`가 실제 `OrchestratedJobExecutor`를 타는지
- 여전히 `PlaceholderJobExecutor`가 기본값으로 남아 있지 않은지

를 꼭 확인해야 한다.

## 7. 다음 세션에서 바로 할 일

추천 순서는 아래다.

1. `Dockerfile.serve` 추가
2. root `docker-compose.yml`의 `model-engine` build/dockerfile 교체
3. health check로 serving 부팅 확인
4. `bridge/service/healthz` 확인
5. `POST /v1/jobs` saas smoke
6. `multipart(metadata + primary_bitmap)` real smoke

## 8. 검증 목표

다음 세션 구현이 끝나면 최소한 아래를 확인해야 한다.

1. root compose에서 `model-engine`가 HTTP 서버로 뜬다.
2. 같은 컨테이너에서 실제 OCR/번역/inpaint가 실행된다.
3. saas 모드에서 usage hold/capture/release가 service에 반영된다.
4. `GET /v1/jobs/{job_id}`에서 `document_patch`가 나온다.
5. 단일 worker/단일 replica 전제가 실제 설정에 반영된다.

## 9. 보류 항목

다음 세션에서도 아래는 바로 건드리지 않아도 된다.

- API / Worker 분리
- durable job store
- durable artifact store
- presigned URL artifact handoff
- multi-replica scaling
- serverless cold start 최적화

이건 통합 serving image가 안정화된 뒤 다음 단계로 넘긴다.
