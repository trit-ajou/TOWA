# model_engine Serving Plan

이 문서는 `model_engine`의 서빙 전략을 현재 코드 기준으로 정리한 구현 계획 문서다.

중요:

- 이 문서는 "지금 무엇을 먼저 만들 것인가"를 다룬다.
- 장기 이상형 아키텍처를 고정하는 문서가 아니다.
- 현재 단계의 목표는 `UI engine <-> model engine <-> service engine` 실제 E2E를 닫는 것이다.

관련 문서:

- `README.md`
- `PROGRESS.md`
- `IMPLEMENTATION_SUMMARY.md`
- `UI_MODEL_CONTRACT_DRAFT.md`
- `../docs/http-contract.md`
- `../docs/ui-model-implementation.md`

## 1. 현재 상태

현재 `model_engine`에는 성격이 다른 두 런타임이 공존한다.

### 1.1 API 서버 이미지

기준 파일:

- `Dockerfile.api`
- root `docker-compose.yml`의 `model-engine`

역할:

- `POST /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `GET /bridge/service/...`

현재 이 경로는 HTTP contract, SaaS usage wiring, session pass-through, job lifecycle 검증에는 적합하다.

하지만 이 이미지는 추론용 시스템 패키지와 모델 런타임을 충분히 포함하지 않을 수 있다.
즉 "상시 서빙되는 model API"는 제공하지만, "실제 OCR/번역/inpaint를 끝까지 수행하는 serving runtime"으로는 아직 완결되지 않았다.

### 1.2 Inference 배치 이미지

기준 파일:

- `Dockerfile.inference`
- `docker-compose.inference.yml`

역할:

- `craft-sample`
- `ocr-sample`
- `translation-sample`
- `pipeline`
- preload 스크립트

이 경로는 실제 CRAFT/OCR/번역/inpaint runtime을 포함한다.
다만 컨테이너가 스크립트를 1회 실행한 뒤 종료되는 배치 실행 모델이다.

즉 현재 상태는:

- API 서버는 상시 서빙되지만 추론 runtime이 가볍다
- 추론 runtime은 충분하지만 HTTP-serving 형태가 아니다

## 2. 왜 통합 서빙 컨테이너가 먼저 필요한가

장기적으로 cloud/serverless 환경의 이상형은 아래 구조다.

- API 컨테이너
- Worker 컨테이너
- Durable job store
- Durable artifact store

하지만 현재 프로젝트 단계에서는 이 구조를 바로 도입하는 것보다, 먼저 `API + Inference`를 하나의 장기 실행 컨테이너로 통합하는 편이 더 적절하다.

이유:

1. 지금 가장 시급한 목표는 `UI -> model -> service` 실제 E2E 검증이다.
2. `model_engine` 내부에는 이미 job API, background execution, orchestrated executor, service usage wiring이 구현되어 있다.
3. 부족한 것은 "HTTP 요청을 받아 실제 추론까지 수행하는 serving image"이지, job abstraction 자체가 아니다.
4. 지금 단계에서 API/worker 분리까지 동시에 도입하면 queue, durable state, artifact storage를 함께 설계해야 해서 범위가 지나치게 커진다.

따라서 현재 단계의 전략은 아래로 고정한다.

- 외부 계약은 계속 async job 기반으로 유지한다.
- 내부 배포는 `API + Inference` 통합 서빙 컨테이너를 먼저 만든다.
- 그 위에서 실제 inference, usage hold/capture/release, `document_patch` 반환까지 모두 검증한다.

## 3. 현재 코드에서 이미 구현된 것

통합 서빙 컨테이너 전략은 "새로운 아키텍처를 처음부터 다시 만드는 것"이 아니다.
현재 코드에는 이미 아래 기반이 있다.

### 3.1 Job API

기준 파일:

- `api/app.py`
- `api/schemas.py`
- `api/jobs.py`

현재 지원:

- `POST /v1/jobs`
- `GET /v1/jobs/{job_id}`
- JSON create path
- `multipart(metadata + primary_bitmap)` create path
- `document_patch` 포함 poll 응답

### 3.2 Background execution

기준 파일:

- `api/jobs.py`

현재 `ModelJobManager.create_job()`은 내부적으로 background thread를 생성하고, 같은 프로세스 내에서 job을 실행한다.

즉 현재 단계에서 새 `BackgroundTasks` 프레임워크를 도입하는 것이 본질은 아니다.
핵심은 이 background execution path가 실제 inference executor를 정상 수행할 수 있도록 서빙 이미지에 추론 런타임을 포함시키는 것이다.

### 3.3 Real executor

기준 파일:

- `api/jobs.py`
- `orchestrator.py`
- built-in model registration 관련 모듈

현재는:

- `PlaceholderJobExecutor`
- `OrchestratedJobExecutor`

가 공존한다.

통합 서빙 컨테이너 단계의 목표는 `OrchestratedJobExecutor`가 HTTP API 경로에서 실제로 안정적으로 동작하게 만드는 것이다.

### 3.4 SaaS usage wiring

기준 파일:

- `api/jobs.py`
- `service_engine/client.py`
- `api/service_bridge.py`

현재 구현:

- saas create 시 `Authorization: Bearer <session_key>`를 받아 `runtime_context.service_session_key`로 정규화
- create 시 usage hold
- 성공 시 capture
- 실패 시 release

즉 service 연동 자체는 이미 마련되어 있다.

## 4. 현재 단계에서 목표로 하는 서빙 형태

현재 단계의 목표 서빙 형태는 아래다.

### 4.1 배포 형태

- 컨테이너 하나가 `uvicorn`으로 상시 실행된다.
- 이 컨테이너가 `/v1/jobs` 요청을 받는다.
- 같은 컨테이너 내부에서 background thread가 실제 추론을 수행한다.
- poll 요청은 같은 컨테이너 내부 메모리 상태를 조회한다.

### 4.2 외부 계약

외부 API 계약은 계속 async job 기반으로 유지한다.

- `POST /v1/jobs`
  - 즉시 `job_id`, `pipeline_id`, `status_url` 반환
- `GET /v1/jobs/{job_id}`
  - `status`
  - `document_patch`
  - `artifacts`
  - `stage_reports`
  - `error`

즉 "동기 추론 API"로 바꾸는 것이 아니라, "통합 서빙 컨테이너 안에서 async job을 처리하는 것"이 목표다.

### 4.3 운영 제약

이 단계에서는 아래 전제를 둔다.

- `uvicorn --workers 1`
- `model-engine` 단일 replica
- job store는 in-memory 유지
- artifact는 local temp/file storage 유지

이유:

- 현재 `ModelJobManager`는 메모리 기반 job 저장소를 사용한다.
- 현재 poll은 같은 프로세스 메모리 상태를 조회한다.
- 다중 worker/다중 replica에서는 create와 get이 다른 프로세스로 가며 `model_job_not_found`가 발생할 수 있다.

즉 통합 서빙 컨테이너 단계는 반드시 single-process, single-instance 전제를 문서화해야 한다.

## 5. 구현 단계

### 5.1 1단계: `Dockerfile.serve` 추가

목표:

- 기존 `Dockerfile.api`의 HTTP entrypoint
- 기존 `Dockerfile.inference`의 시스템 패키지와 inference dependency

를 합친 새 이미지를 만든다.

원칙:

- 베이스 이미지는 inference 호환성이 검증된 Python 3.10 계열을 우선한다.
- API 서버 실행에 필요한 패키지와 추론 패키지를 모두 포함한다.
- 모델 캐시 관련 환경 변수는 inference 이미지 기준을 따른다.
- 기본 CMD는 `uvicorn main:app --host 0.0.0.0 --port 8100 --workers 1`로 둔다.

주의:

- 지금 리포에는 `requirements-inference.txt`가 없다.
- 실제 기준 파일은 `requirements-api.txt`, `requirements-craft.txt`다.
- 따라서 serving image는 기존 requirement 파일 구조를 재사용하거나, 필요하면 이후 별도 통합 requirement 파일로 정리한다.

### 5.2 2단계: API 실행 경로를 serving runtime에 연결

목표:

- `/v1/jobs` create path가 같은 컨테이너 안에서 실제 inference executor를 실행하게 만든다.

원칙:

- 새 background framework를 도입하는 것이 핵심이 아니다.
- 현재 `ModelJobManager` + background thread 경로를 유지한다.
- executor 기본값이 `PlaceholderJobExecutor`로 남아 있지 않도록 serving 환경에서 `OrchestratedJobExecutor`가 기본 경로가 되게 한다.

검토 포인트:

- OCR/CRAFT/inpaint runtime이 실제 serving process 안에서 import 가능해야 한다.
- model cache 경로와 temp artifact 경로가 runtime 중에 정상적으로 쓰여야 한다.
- provider credential resolution과 local session secret 주입이 serving 환경에서도 동일하게 동작해야 한다.

### 5.3 3단계: root compose의 `model-engine` 교체

목표:

- root `docker-compose.yml`의 `model-engine` 서비스가 새 `Dockerfile.serve`를 사용하게 한다.

필수 설정:

- `TOWA_SERVICE_ENGINE_URL=http://service-engine:8000`
- 필요한 CORS env
- translation/inpaint provider env
- 모델 캐시 mount
- 필요 시 artifact/temp workspace mount

중요:

- serving 단계에서는 multi-worker/multi-replica를 금지한다.
- GPU 사용이 필요한 경우에만 별도 device reservation을 추가한다.

### 5.4 4단계: E2E smoke 검증

검증 순서:

1. `service_engine` health check
2. `model_engine` health check
3. `model -> service` bridge health/auth smoke
4. `saas` mode `/v1/jobs` create/get smoke
5. `multipart(metadata + primary_bitmap)` real inference smoke
6. usage hold/capture/release 확인
7. `document_patch`, `artifacts`, `stage_reports` shape 확인

목표:

- service/model 연동 smoke
- 실제 inference 실행
- UI가 이후 붙을 수 있는 poll 결과 shape 확인

## 6. 이 단계에서 의도적으로 미루는 것

이 문서는 아래 항목을 현재 단계의 범위 밖으로 둔다.

- API / Worker 분리
- durable job store
- durable artifact store
- multi-replica job routing
- presigned URL artifact handoff
- serverless cold-start 최적화
- queue 기반 worker orchestration

즉 이 문서는 "현재 코드를 기준으로 가장 빠르게 실제 서빙 경로를 만드는 전략"을 다루며, 장기 운영 구조는 후속 단계로 미룬다.

## 7. 완료 기준

이 문서 기준으로 통합 서빙 컨테이너 단계가 완료되었다고 판단하려면 아래를 만족해야 한다.

1. root compose의 `model-engine`가 상시 HTTP 서버로 뜬다.
2. 같은 컨테이너에서 실제 OCR/번역/inpaint job이 실행된다.
3. cloud/saas 모드에서 usage hold/capture/release가 실제 service에 반영된다.
4. `multipart(metadata + primary_bitmap)` create path가 정상 동작한다.
5. `GET /v1/jobs/{job_id}`가 `document_patch`, `artifacts`, `stage_reports`를 반환한다.
6. 단일 worker/단일 replica 전제가 문서와 compose에 명시되어 있다.

## 8. 다음 단계

통합 서빙 컨테이너가 안정화되면, 그 다음 단계는 아래 중 하나로 확장한다.

1. API / Worker 분리
2. durable artifact backend 추가
3. durable job state 추가
4. scale-out 가능한 cloud/serverless 구조로 재설계

즉 통합 서빙 컨테이너는 최종형이 아니라, 현재 프로젝트를 다음 단계로 넘기기 위한 의도적인 중간 단계다.
