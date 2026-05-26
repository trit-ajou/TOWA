# model_engine Progress

## 기준 문서

`model_engine` 문서는 `docs/` 아래에 정리한다.

- `README.md`: 현재 `model_engine` 내부 구현 기준서
- `PLAN.md`: 확정/미확정 범위 판단 기준
- `IMPLEMENTATION_SUMMARY.md`: 현재 실제 구현 완료 범위 요약
- `OCR_CAPABILITY.md`: OCR capability 공통 계약 초안
- `TROUBLESHOOTING.md`: OCR/번역 실행 중 관측한 문제와 threshold 튜닝 기록
- `SESSION_AND_CREDENTIAL_IMPLEMENTATION.md`: 세션, usage, provider credential 구현 준비 문서
- `INFERENCE_OUTPUT_SPEC.md`: 현재 구현 기준 model 추론 job 출력 envelope와 operation별 patch/artifact/stage report 명세
- `SERVING_PLAN.md`: `API + Inference` 통합 서빙 컨테이너 전략과 단일 serving image 전환 계획
- `NEXT_SESSION_HANDOFF.md`: 다음 세션 시작 시 바로 읽을 상태 요약과 우선순위 메모
- `SPEC.md`, `../docs/http-contract.md`: 외부 엔진 경계와 SaaS/local 계약 참고

## 이번에 구현한 범위

현재는 공통 계약층을 넘어서, 첫 built-in 모델 경로까지 구현했다.

이미 구현된 capability:

- built-in `text_detection=CRAFT`
- built-in `ocr=manga-ocr`
- 규칙 기반 `mask_or_erase_planning`
- built-in `inpaint=nanobanana(Vertex AI 경유)`
- built-in `translation=OpenAI-compatible`
- built-in `translation=Vertex Gemini`

아직 미구현인 영역은 식자/postprocess와 실제 billable provider smoke run이다.

README 기준서는 현재 코드와 동기화해 유지 중이다. 특히 stage IPC, artifact lifecycle, credential binding/key management 규칙을 README에 먼저 고정하고 그 범위까지만 구현했다.

최근 추가된 wiring:

- `service_engine` client/errors/models 패키지 추가
- `ServiceBackedPipelineRunner` 추가
- `StageRuntimeContext`에 SaaS usage wiring 필드 추가
- SaaS HTTP job 경로에서 `Authorization` bearer를 `runtime_context.service_session_key`로 정규화해 job context에 저장
- background usage capture/release가 request-local raw header가 아니라 저장된 `service_session_key` 기준으로 동작하도록 정리
- service usage hold/capture/release 테스트 추가
- OpenAI-compatible translation adapter 추가
- `model_engine/.runtime/runtime_config.json` 기반 local runtime config 로더 추가
- Docker Compose translation 기본 base URL을 host `127.0.0.1:1234/v1` 대응용 `host.docker.internal:1234/v1`로 설정
- `Tencent HY-MT` 구체 모델 병합 예시는 제거하고 generic custom runtime 방향으로 정리
- OCR stage에 `MangaOcr()` recognizer 재사용, region merge, `vertical_rtl` reading order, density/area 기반 `needs_review` 마킹 추가
- OCR/번역 튜닝 기록용 `TROUBLESHOOTING.md` 추가
- 세션/credential 책임과 실제 API 함수 기준 호환성을 정리한 `SESSION_AND_CREDENTIAL_IMPLEMENTATION.md` 추가
- `UI_MODEL_CONTRACT_DRAFT.md` 추가
- `SERVING_PLAN.md` 추가
- `NEXT_SESSION_HANDOFF.md` 추가
- `/v1/jobs`가 `multipart(metadata + primary_bitmap)` 입력을 수신할 수 있게 확장
- metadata의 `upload://primary_bitmap` descriptor를 request 시점에 `file://...` artifact로 물질화
- multipart request fingerprint에 uploaded bitmap sha256을 포함해 idempotency 충돌 판정을 안정화
- `GET /v1/jobs/{job_id}` 응답에 `document_patch` 필드 추가
- UI migration 전환을 위해 legacy JSON create와 full `document` 응답도 임시로 함께 유지
- 장기 이상형인 `API / Worker` 분리 전에, 현재 단계에서는 `API + Inference` 통합 서빙 컨테이너를 먼저 만들기로 전략을 정리
- root compose가 띄우는 `Dockerfile.api` 서빙 이미지도 Python 3.10 기반 CRAFT/Manga OCR 추론 의존성을 포함하도록 전환
- API job 실행 시 `workspace://...` 같은 외부 논리 workspace를 서버 내부 `file://` 실행 workspace로 보정해 stage artifact 저장이 실제 서빙 경로에서도 동작
- job 생성/시작/완료, background executor 예외, billing finalization 실패, stage 시작/종료/실패를 structured app log로 남기도록 보강
- 로그 payload는 `job_id`, `pipeline_id`, `operation_kind`, `request_ref`, `stage_name`, `stage_run_id`, `status`, `error_code` 중심으로 남기고 credential/session/token 계열 값은 redaction
- Mindlogic image 연동 전 실 API shape를 확인하기 위한 `scripts/probe_mindlogic_image_edit.py` probe 스크립트 추가. `/v1/gateway/images/generate/`와 legacy `/v1/api/google/models/edit-image` payload를 모두 확인할 수 있게 구성
- built-in `inpaint=mindlogic` adapter 추가. 기존 나노바나나 인페인트와 동일한 `NANOBANANA_DEFAULT_PROMPT`, full-page provider call, local mask composite 계약을 유지하고 provider 호출부만 Mindlogic Google edit endpoint로 분리
- API job inpaint 경로는 `TOWA_INPAINT_PROVIDER=mindlogic` 또는 runtime metadata `inpaint_provider=mindlogic`일 때 `builtin.mindlogic.inpaint`를 선택한다. SaaS/platform key env는 `TOWA_PLATFORM_PROVIDER_MINDLOGIC_API_KEY`
- Docker inference sample에서 `CRAFT -> mask_or_erase_planning -> Mindlogic inpaint` 추론 성공 확인. 결과 artifact는 `model_engine/.runtime/mindlogic_inpaint_docker/transactions/pipe_inpaint_sample/inpaint/pipe_inpaint_sample_inpaint_3/`
- Docker `model-engine`은 `model_engine/.runtime`을 `/app/model_engine/.runtime`로 마운트해 API 서버도 `runtime_config.json`을 읽는다. `TOWA_INPAINT_PROVIDER`, `TOWA_INPAINT_MODEL_NAME`, provider API key는 env 우선, runtime config fallback 순서로 해석한다
- Docker `model-engine`은 `model_engine/.cache/models`도 `/cache/models`로 마운트한다. UI에서 첫 inpaint job을 테스트할 때 CRAFT detector/refiner 가중치를 컨테이너 재생성마다 다시 다운로드하지 않도록 하여 polling timeout 가능성을 줄인다
- 공통 stage artifact dump 기능 추가. `TOWA_MODEL_ENGINE_STAGE_DUMP=1` 또는 `runtime_context.metadata.stage_artifact_dump=true`일 때 각 stage transaction 아래 `stage_artifact_dump/`를 만들고 `stage_request.json`, `stage_response.json`, `artifacts_before.json`, `artifacts_after.json`, `document_after.json`을 저장한다. 기본값으로 `file://` artifact는 `files/input`, `files/output` 아래 hardlink/copy하며, `TOWA_MODEL_ENGINE_STAGE_DUMP_COPY_FILES=0` 또는 metadata `stage_artifact_dump_copy_files=false`로 바이너리 복사를 끌 수 있다. dump JSON은 credential/session/token 계열 값을 redaction한다.
- bitmap-only inpaint 경로의 UI용 `inpainting_layer_bitmap`은 provider full-page output을 그대로 전달한다. 전체 provider 결과는 debug용 `provider_output_bitmap` artifact로도 함께 남긴다.
- Mindlogic/Nanobanana inpaint provider 호출 prompt에 입력 bitmap의 실제 canvas 크기를 동적으로 추가한다. 예를 들어 UI에서 받은 source bitmap이 `1333x750`이면 provider prompt에 output이 정확히 `1333x750 pixels`이고 crop/pad/stretch/scale 변경을 하면 안 된다는 제약을 붙인다. stage report에는 `prompt_output_size`를 남긴다.
- API `inpaint` job은 e2e 재검증을 위해 `inpaint` 단일 stage로 실행한다. UI에는 provider full-page output을 `inpainting_layer_bitmap`으로 그대로 반환하고, provider 결과도 debug용 `provider_output_bitmap`으로 남긴다.
- Mindlogic inpaint provider 호출은 gateway mask 계약 오류를 피하기 위해 raw 원본 bitmap 1장만 nested `reference_image` payload로 전달한다. stage report에는 `provider_reference_image_count=1`, `provider_mask_guide=no`, `composite_mask_mode=full_page`를 남긴다.

## 2026-05-14 세션 handoff

현재 작업 브랜치와 PR 상태:

- branch: `model_engine`
- latest pushed commit: `88383a6` (origin/model_engine)
- 로컬 미푸시 커밋 4개 (아래 참고)
- PR: `https://github.com/trit-ajou/TOWA/pull/8`
- PR 상태: draft

이번 세션에서 수행한 작업:

### 1. 번역 설정 runtime_config.json fallback 추가

커밋: `c096a83`, `c91b3fe`, `23ab9d4`

수정 파일:

- `model_engine/api/jobs.py`
- `model_engine/builtin_models/openai_compatible_translation.py`

문제:

- UI에서 번역 요청 시 `runtime_context.metadata`에 `openai_compatible_base_url`, `translation_model_name`을 보내지 않았다
- `_translation_provider_config_from_runtime`은 `runtime_config.json`을 읽지 않고 metadata만 확인했다
- Docker 컨테이너 내에서 폴백 디폴트 `http://127.0.0.1:1234/v1`은 호스트에 접근 불가 → `Connection refused`
- API key도 credential 시스템에서만 가져왔는데, local 모드에서는 provider secrets가 없어서 None → `401 API key required`

반영한 변경:

- `_translation_model_id_from_runtime`과 `_translation_provider_config_from_runtime`에서 `metadata → runtime_config.json → 하드코딩 디폴트` 순서 fallback 체인 추가
- `TOWA_OPENAI_COMPATIBLE_BASE_URL`, `TOWA_TRANSLATION_MODEL_NAME`, `TOWA_TRANSLATION_BACKEND` 키를 중간 폴백으로 읽는다
- `TOWA_OPENAI_COMPATIBLE_API_KEY`를 stage config의 `api_key`로 주입한다
- `run_openai_compatible_translation`에서 credential 시스템에 API key가 없으면 stage config의 `api_key`를 폴백으로 사용한다
- Mindlogic API Gateway처럼 Cloudflare가 Python 기본 User-Agent를 막는 OpenAI-compatible endpoint를 위해 chat completions 요청에 `Accept: application/json`, `User-Agent: curl/8.7.1` 헤더를 추가했다. 로컬 개발 runtime config는 `gemini-3.1-flash-lite-preview`와 `https://factchat-cloud.mindlogic.ai/v1/gateway` 조합으로 검증했다
- 인페인트 설정(`_inpaint_provider_config_from_runtime`)과 동일한 패턴으로 통일했다

### 2. 인페인트 파이프라인 단순화

커밋: `d088d7a`

수정 파일:

- `model_engine/api/jobs.py`
- `model_engine/builtin_models/nanobanana_inpaint.py`

변경 전:

- `inpaint` 요청 시 `text_detection(CRAFT) → mask_or_erase_planning → inpaint` 3단계 실행
- CRAFT 텍스트 검출 후 마스크를 만들고, provider 결과에서 마스크 영역만 합성

변경 후:

- `inpaint` 요청 시 `inpaint` 1단계만 실행
- 프롬프트가 이미 "모든 텍스트를 찾아서 지워라"고 지시하므로 CRAFT 검출이 불필요
- provider에 원본 이미지 전체를 보내고, provider 결과를 그대로 `layer_inpainting`으로 사용
- `inpaint_tasks` artifact가 있으면(기존 마스크 기반 경로) 여전히 마스크 합성 fallback으로 동작
- `builtin.nanobanana.inpaint`, `builtin.mindlogic.inpaint` manifest의 필수 artifact를 `bitmap`으로 맞춰 UI 단독 inpaint 요청에서도 registry selection이 통과하도록 수정

효과:

- CRAFT 모델 로딩/추론 시간 생략 → 인페인트 속도 개선
- 파이프라인 단계 감소로 실패 지점 감소

### 3. 임시 변경 (커밋 미포함)

- `ui_engine/towa-app/src/components/editor/AiToolbar.vue`의 `pollUntilTerminal` 타임아웃을 30초(60×500ms) → 5분(300×1000ms)으로 임시 확장
- 이 변경은 커밋에 포함하지 않았으며, UI 개발자에게 정식 수정을 요청해야 한다
- 로컬 LLM(gemma-4-e4b 등)이 느려서 UI 폴링이 먼저 타임아웃되는 문제 대응용

다음 세션에서 확인/진행할 항목:

- `git push`로 로컬 커밋 4개를 origin에 반영
- Docker 재빌드 후 번역/인페인트 end-to-end 테스트
- `c91b3fe` 커밋의 timeout 120→300 변경은 model engine 쪽인데, 현재 revert되어 120으로 돌아가 있다. 필요 시 다시 올릴 것
- UI 개발자에게 폴링 타임아웃 확장 요청 (최소 2~3분)
- `replace_source_ref` patch 처리 시 UI가 기존 레이어를 교체하지 않고 새 레이어를 추가하는 문제 확인

## 2026-05-12 세션 handoff

현재 작업 브랜치와 PR 상태:

- branch: `model_engine`
- history cleanup 전 backup branch: `backup/model_engine-before-history-fix-20260514`
- latest pushed commit은 새 세션에서 `git log -1 --oneline`으로 확인
- PR: `https://github.com/trit-ajou/TOWA/pull/8`
- PR 상태: draft
- local status는 새 세션에서 `git status --short --branch`로 확인

이번 세션의 주된 요청은 UI/server engine 개발자가 model engine 테스트 중 오류 로그를 보기 어렵다는 문제의 원인 조사와 개선이었다.

조사 결과:

- `ModelJobManager._run_job`에서 background executor 예외가 job error payload로 변환되지만 app log에 traceback/context가 남지 않았다.
- `PipelineOrchestrator.run`에서 stage 시작, 종료, 실패, 예외 전환점이 로그로 남지 않았다.
- `/v1/jobs` create path와 `/bridge/service/...` path의 validation/service 오류가 HTTP JSON 응답으로만 반환되고 container log에서 원인 추적용 event가 부족했다.
- 민감정보 정책상 credential/session/token류는 로그에 남기면 안 되므로, structured log helper에서 redaction을 먼저 고정해야 했다.

반영한 변경:

- `model_engine/logging_utils.py` 추가
  - structured log payload를 JSON string으로 출력
  - `authorization`, `api_key`, `credential`, `password`, `secret`, `session_key`, `token`, bearer 문자열을 redaction
  - exception log는 redacted traceback을 payload에 포함
- `model_engine/api/jobs.py`
  - `model_job_accepted`
  - `model_job_started`
  - `model_job_finished`
  - `model_job_idempotent_replay`
  - `model_job_exception`
  - `model_job_billing_finalization_failed`
  - `model_job_usage_hold_authorized`
- `model_engine/orchestrator.py`
  - `model_stage_started`
  - `model_stage_finished`
  - `model_stage_exception`
- `model_engine/api/app.py`
  - job create validation/service error 로그 추가
  - bridge service error/unavailable 로그 추가
- `model_engine/tests/test_job_executor.py`
  - background executor exception이 job context와 traceback을 남기는지 검증
- `model_engine/tests/test_orchestrator.py`
  - stage failure가 stage/status/error_code와 함께 로그에 남고 secret이 노출되지 않는지 검증

원격 `origin/model_engine`에 이미 있던 변경을 기준 base로 삼아 history를 정리했다.

- CRAFT detect job이 text blocks patch를 낼 수 있는 변경
- model image의 torch execstack 처리 변경
- 관련 contract/docs 업데이트
- 불필요한 `Merge remote-tracking branch 'origin/model_engine' into model_engine` 커밋은 backup branch에 보존한 뒤 제거하고, logging 변경을 다시 얹는 방식으로 정리했다.

검증:

- `python3 -m unittest model_engine.tests.test_job_executor model_engine.tests.test_orchestrator model_engine.tests.test_craft_text_detection -v`
- `PYTHONPYCACHEPREFIX=/private/tmp/towa_model_engine_pycache python3 -m compileall -q model_engine`

참고:

- 로컬 기본 `python3 -m compileall -q model_engine`은 macOS Python이 `/Users/kmins/Library/Caches/com.apple.python/...` 아래 pyc를 쓰려다가 sandbox 권한에 막힐 수 있다.
- 이 경우 위처럼 `PYTHONPYCACHEPREFIX=/private/tmp/towa_model_engine_pycache`를 지정한다.
- `model_engine/tests/test_job_api.py`는 현재 로컬 Python 환경에 `fastapi`가 없으면 실행되지 않는다. Docker/API 의존성 환경에서 돌려야 한다.
- 컨테이너 로그 확인 시 `model_job_` 또는 `model_stage_` event prefix로 필터링하면 된다.

### 1. Canonical IR

구현 파일:

- `contracts/document_ir.py`

구현 내용:

- Bitmappery 의미론 기반 `DocumentIR`
- `LayerIR`, `Transform`, `FilterSettings`, `TextStyle`
- OCR/번역/식자 연결용 `TextBlock`
- 문서 clone, layer 조회/삭제 유틸리티

### 2. IR Patch

구현 파일:

- `contracts/patches.py`

구현 내용:

- 고정 patch op enum
- `PatchOperation`
- patch 적용기 `apply_patch`, `apply_patches`

현재 구현된 op:

- `add_layer`
- `remove_layer`
- `update_layer_props`
- `replace_source_ref`
- `replace_mask_ref`
- `set_layer_text`
- `set_layer_transform`
- `set_layer_filters`
- `set_document_selection`
- `append_text_blocks`
- `replace_text_blocks`
- `set_stage_meta`
- `attach_artifact`
- `detach_artifact`

### 3. Artifact Registry

구현 파일:

- `contracts/artifacts.py`

구현 내용:

- `ArtifactDescriptor`
- `ArtifactStatus`
- `ArtifactRegistry` 추상 인터페이스
- `InMemoryArtifactRegistry`

현재 지원 동작:

- register
- resolve
- verify
- mark failed
- release/orphan
- gc

비고:

- `file://` URI 기준 checksum verify를 지원한다.
- local file artifact는 `{workspace}/transactions/{pipeline_id}/{stage_name}/{stage_run_id}/`
  경로 아래에 stage-run 단위로 저장한다.
- 운영용 durable registry는 아직 구현하지 않았다.

### 4. Stage I/O / Report Contract

구현 파일:

- `contracts/stages.py`

구현 내용:

- `ExecutionMode`
- `StageStatus`
- `StageRuntimeContext`
- `StageRequest`
- `StageResponse`
- `StageReport`

비고:

- stage output은 patch + artifact + report 조합을 기본으로 둔다.
- provider hang/timeout 시 snapshot artifact를 남기는 실패 경로를 지원한다.

### 5. Orchestrator / Stage Base

구현 파일:

- `orchestrator.py`
- `stages/base.py`

구현 내용:

- 순차 실행 `PipelineOrchestrator`
- 추상 `Stage`
- 계약 검증용 `StaticStage`
- stage별 patch 누적, artifact 등록, 실패 시 후속 stage 중단

### 6. Stage IPC

구현 파일:

- `ipc/serde.py`
- `ipc/process_stage.py`
- `ipc/worker_entrypoint.py`
- `stages/ipc_demo.py`

구현 내용:

- `StageRequest` / `StageResponse` / `DocumentIR` / `ArtifactDescriptor` JSON 직렬화
- `stdin/stdout JSON` 기반 subprocess IPC
- 독립 process stage 래퍼 `ProcessStage`
- import path 기반 worker handler 로딩
- IPC 계약 검증용 demo worker stage

현재 IPC 방식:

- orchestrator
  -> `ProcessStage`
  -> `python -m model_engine.ipc.worker_entrypoint --handler ...`
  -> worker handler
  -> JSON response

비고:

- 지금은 가장 단순한 subprocess IPC를 기준으로 고정했다.
- 실제 CRAFT/OCR/API adapter는 이후 같은 프로토콜 위에 연결하면 된다.

### 7. Credential Binding / Key Management

구현 파일:

- `contracts/credentials.py`
- `credentials/resolver.py`
- `contracts/stages.py`
- `ipc/serde.py`
- `ipc/process_stage.py`

구현 내용:

- `CredentialSource`, `BillingMode`, `CredentialBinding`, `ResolvedCredential`
- `DefaultCredentialResolver`
- local persisted credential / SaaS platform credential 기본 해석
- `StageRequest.credential_bindings`
- `StageRequest.resolved_credentials`
- `StageReport.provider`
- subprocess child env 기반 secret injection

현재 지원 규칙:

- `inpaint`
  - local: persisted personal key 우선
  - SaaS: platform-managed key

- `translation`
  - provider 이름은 열어두되 credential source 규칙은 동일

- `text_detection`, `ocr`, `typesetting`, `postprocess`
  - 기본적으로 credential 비사용

비고:

- raw secret은 stage IPC JSON에 싣지 않는다.
- subprocess worker에는 env로만 주입한다.
- local persisted credential 기본 경로는 `~/.config/towa/model_engine/credentials.json`이다.
- `.runtime/runtime_config.json`은 샘플 스크립트용 runtime config이고, 기본 resolver persisted source 그 자체는 아니다.
- local 샘플 실행은 runtime config에서 읽은 값을 `session_provider_secrets`로 옮겨 stage 실행에 사용한다.

### 8. SaaS Usage Wiring

구현 파일:

- `service_engine/client.py`
- `service_engine/errors.py`
- `service_engine/models.py`
- `orchestrator.py`
- `contracts/stages.py`
- `ipc/serde.py`

구현 내용:

- `service_engine` error envelope를 내부 예외로 매핑하는 client 계층
- `StageRuntimeContext.service_session_key`, `service_base_url`, `service_request_ref`
- 순수 `PipelineOrchestrator` 위에 얹는 `ServiceBackedPipelineRunner`
- SaaS 실행 시 `POST /usage/jobs` -> pipeline 실행 -> `capture` 또는 `release`
- release 사유를 마지막 실패 stage 기준으로 정리하는 기본 매핑
- SaaS HTTP job 생성 시 raw bearer에서 session token 본문을 추출해 `runtime_context.service_session_key`에 저장
- background usage hold/capture/release는 저장된 `service_session_key`로 authenticated path를 재구성해 service 호출

비고:

- 현재 `text_detection` 계열 실행은 service usage enum 호환을 위해 `mask`로 매핑한다.
- 기존 `/v1/jobs` API 브리지는 유지하고, core orchestrator wiring을 별도로 닫았다.
- 현재 cloud 경로에는 두 세션 입력 형태가 공존한다.
  - HTTP API 경로: raw `Authorization` 헤더 입력 -> 내부에서 `service_session_key`로 정규화
  - direct runner 경로: `service_session_key`를 runtime context에 직접 주입

### 9. Container Bootstrap

구현 파일:

- `Dockerfile`
- `Dockerfile.inference`
- `docker-compose.inference.yml`
- `.dockerignore`
- `requirements-base.txt`
- `requirements-craft.txt`
- `scripts/preload_craft.py`
- `scripts/preload_manga_ocr.py`

구현 내용:

- Python 실행 가능한 최소 컨테이너 환경
- 기본 개발/테스트 이미지와 추론용 이미지 분리
- 추론 샘플 실행용 Docker Compose 추가
- CRAFT weight 사전 다운로드용 preload runner 추가
- `manga-ocr` Hugging Face weight 사전 다운로드용 preload runner 추가
- base/craft 의존성 파일 분리
- `/app` 작업 디렉토리
- `/workspace`, `/artifacts`, `/cache` 기본 경로 생성
- 기본 `CMD`로 현재 테스트 스위트 실행

비고:

- `Dockerfile`은 contract test와 개발용 기본 이미지다.
- `Dockerfile.inference`는 CRAFT 같은 로컬 모델 의존성을 담는 추론용 이미지다.
- 현재 `Dockerfile.inference`는 CRAFT 의존성 호환성 때문에 Python 3.10을 사용한다.
- OpenCV/CRAFT 런타임을 위해 `libGL.so.1` system package를 포함한다.
- CRAFT/OpenCV ABI 충돌을 피하기 위해 inference 의존성은 `numpy<2`로 고정했다.
- CRAFT 런타임의 `cv2.dnn.DictValue` 충돌을 피하기 위해 OpenCV는 `opencv-python==4.7.0.72`로 고정했다.
- CRAFT의 구형 `model_urls` 참조를 수용하기 위해 torch stack은 `torch==1.12.1`, `torchvision==0.13.1`로 고정했다.
- CRAFT 패키지의 ragged polygon 후처리 오류를 피하기 위해 `adjustResultCoordinates`를 안전 버전으로 monkey patch한다.
- CRAFT `predict.py`의 ragged polygon `np.array(...)` 실패를 피하기 위해 모듈 전용 safe numpy proxy를 적용한다.
- 아직 GPU 세팅은 넣지 않았다.
- 현재 목적은 추론 런타임을 별도 이미지로 분리해 재현성과 확장성을 확보하는 것이다.

### 9-1. Job Executor Stage Composition

구현 파일:

- `api/jobs.py`
- `tests/test_job_executor.py`

구현 내용:

- 기본 `ModelJobManager` executor를 placeholder에서 orchestrator 기반 executor로 전환
- `detect`는 built-in `CRAFT text_detection` stage 조합 사용
- `translate`는 `text_detection -> ocr -> translation` 조합 사용
- `inpaint`는 e2e 재검증을 위해 `inpaint` 단일 stage 조합 사용
- planner 함수는 직접 stage 테스트와 샘플 경로에서 계속 재사용 가능하도록 유지

비고:

- 실제 `/v1/jobs` 경로에서도 `ocr`와 `translation` stage가 더 이상 샘플 전용이 아니라 기본 실행 경로 일부가 된다.

### 9-2. Built-in Vertex Translation

구현 파일:

- `contracts/translated_text_blocks.py`
- `builtin_models/vertex_translation.py`
- `tests/test_vertex_translation.py`
- `scripts/run_translation_sample.py`
- `scripts/run_pipeline_sample.py`
- `docker-compose.inference.yml`

구현 내용:

- built-in `translation` capability를 Vertex Gemini adapter로 구현
- 입력은 `DocumentIR.text_blocks`, 출력은 `translated_text_blocks` artifact와 `replace_text_blocks` patch
- local/SaaS 모두 `user_personal_*` 또는 `platform_managed` credential binding을 사용
- provider 호출은 `nanobanana`와 같은 `google-genai` / Vertex API key 경로를 재사용
- 전체 샘플 흐름을 `pipeline` compose 서비스로 묶어 `translation + inpaint`를 한 번에 실행 가능하게 함

비고:

- 기본 모델은 `gemini-3.1-flash-lite-preview`
- 결과 응답은 JSON으로 강제하고, block id 또는 순서 기준으로 번역 결과를 원문 block에 다시 병합한다.

### 9-3. Built-in OpenAI-compatible Translation

구현 파일:

- `builtin_models/openai_compatible_translation.py`
- `config/runtime_config.py`
- `tests/test_openai_compatible_translation.py`
- `tests/test_runtime_config.py`
- `scripts/run_translation_sample.py`
- `scripts/run_pipeline_sample.py`

구현 내용:

- built-in `translation` capability에 OpenAI-compatible adapter 추가
- LM Studio, Ollama OpenAI-compatible endpoint, custom proxy를 공통 경로로 사용
- API key가 없어도 동작 가능한 local server 경로와, Bearer key가 필요한 proxy 경로를 모두 허용
- `env > runtime_config.json > default` 우선순위로 local runtime config를 해석
- 기본 translation backend를 OpenAI-compatible로 전환하고, Vertex는 명시적 backend 선택으로 유지

비고:

- 현재 기본 base URL은 host 실행 시 `http://127.0.0.1:1234/v1`, Docker 실행 시 `http://host.docker.internal:1234/v1`
- 현재 구현은 page block 전체를 한 번의 LLM 호출로 보내는 batch translation 방식이다.
- JSON 출력은 provider/prompt 기반으로 유도하지만, provider별 strict structured output 보강은 아직 남아 있다.

남은 보완:

- JSON repair path 추가
- `block_id` 누락 시 positional fallback 제거 또는 제한
- OCR `needs_review`/warning 정보를 prompt에 반영
- 많은 block에 대한 chunking 정책
- retry/backoff 및 provider compatibility 보강
- glossary / term map 추가

### 9-3-1. OpenAI-compatible Translation runtime_config fallback

구현 파일:

- `api/jobs.py`
- `builtin_models/openai_compatible_translation.py`

구현 내용:

- `_translation_model_id_from_runtime`과 `_translation_provider_config_from_runtime`에서 `runtime_context.metadata` → `runtime_config.json` → 하드코딩 디폴트 순서로 fallback 체인을 추가
- 기존에는 UI가 `runtime_context.metadata`에 `openai_compatible_base_url`, `translation_model_name`, `translation_backend`를 보내지 않으면 하드코딩 디폴트(`http://127.0.0.1:1234/v1`, `local-model`)로만 폴백되었다
- 이제 `runtime_config.json`의 `TOWA_TRANSLATION_BACKEND`, `TOWA_OPENAI_COMPATIBLE_BASE_URL`, `TOWA_TRANSLATION_MODEL_NAME`을 중간 폴백으로 읽는다
- API key도 동일 방식으로 추가: `runtime_config.json`의 `TOWA_OPENAI_COMPATIBLE_API_KEY`를 stage config에 `api_key`로 주입한다
- `run_openai_compatible_translation`에서 credential 시스템에 API key가 없으면 stage config의 `api_key`를 폴백으로 사용한다
- 인페인트 설정(`_inpaint_provider_config_from_runtime`)과 동일한 `metadata → runtime_config → default` 패턴으로 통일했다

비고:

- Docker 컨테이너 내에서 `127.0.0.1:1234`는 컨테이너 자신의 localhost이므로 호스트 LM Studio에 접근할 수 없었다. `runtime_config.json`에 `http://host.docker.internal:1234/v1`을 설정하면 Docker에서도 호스트 모델에 접근 가능하다
- credential 시스템(`_optional_api_key`)은 `resolved_credentials`에서 provider를 찾는데, local 모드에서 provider secrets가 없으면 None을 반환한다. 이 경우 `runtime_config.json`의 `TOWA_OPENAI_COMPATIBLE_API_KEY`가 폴백으로 동작한다

### 9-4. OCR Post-processing / Reading Order

구현 파일:

- `builtin_models/manga_ocr.py`
- `tests/test_manga_ocr.py`
- `scripts/run_ocr_sample.py`
- `scripts/run_translation_sample.py`
- `scripts/run_pipeline_sample.py`

구현 내용:

- `MangaOcr()` 인스턴스를 OCR stage 내에서 1회만 생성하고 재사용
- detection region들을 OCR 전에 merge해 crop 수를 줄이고 말풍선/문장 단위 인식 가능성을 높임
- 세로쓰기 일본어 만화 기준 `reading_order_mode=vertical_rtl` 정렬 추가
- `min_ocr_region_area_*`, `max_text_density_per_1000_px2`, `small_region_long_text_*` 규칙으로 환각 의심 block을 `needs_review`로 마킹
- 모든 OCR block에 density/area/text length debug 값을 `style_hint`에 기록

비고:

- 현재 기본 threshold는 `max_text_density_per_1000_px2=1.5`
- 환각 의심 block은 기본적으로 삭제하지 않고 `style_hint.ocr_status=needs_review`로 보존한다.
- threshold 근거와 샘플별 튜닝 규칙은 `TROUBLESHOOTING.md`에 정리한다.

남은 보완:

- `needs_review` block crop debug artifact 저장
- 실제 샘플 여러 장 기준 density/area 분포 수집
- `manga-ocr` confidence 대체 지표 또는 logits 기반 confidence 조사
- UI에서 `needs_review` block 시각 강조
- merge 규칙을 말풍선/세로열 단위로 더 정교화

### 10. Model Merge / Adapter Registry

구현 파일:

- `contracts/models.py`
- `adapters/base.py`
- `models/registry.py`
- `stages/adapter_stage.py`

구현 내용:

- `StageKind`, `StageManifest`, `ResourceProfile`
- `ModelAdapter` 추상 인터페이스
- `ModelRegistry`
- compatibility 기반 `ModelSelection`
- generic `AdapterBackedStage`

현재 지원 규칙:

- pipeline은 모델 이름이 아니라 `stage capability` 기준으로 유지한다.
- 모델 구현체는 `manifest + adapter` 조합으로만 registry에 합류한다.
- selector는 아래 기준으로 호환 여부를 판단한다.
  - `stage_kind`
  - `schema_version`
  - `runtime mode`
  - `required_artifact_kinds`
  - `allowed_credential_sources`
  - `preferred_model_id`

- 기본 선택은 `priority`가 가장 높은 호환 manifest다.
- custom model은 자동 특혜가 아니라 `priority` 또는 명시 선택으로만 우선된다.

비고:

- 아직 orchestrator가 stage graph 전체를 manifest로만 구성하지는 않는다.
- 현재는 `AdapterBackedStage`가 registry selection과 실제 stage 실행을 연결하는 최소 계층이다.
- 실제 CRAFT, 나노바나나, custom remote model은 이후 이 registry에 adapter로 등록하면 된다.

### 10. Custom Model Manifest Loader

구현 파일:

- `CUSTOM_MODELS.md`
- `adapters/callable.py`
- `adapters/http_api.py`
- `custom_models/spec.py`
- `custom_models/loader.py`
- `custom_models/demo.py`

구현 내용:

- manifest JSON 기반 custom model 등록 규칙
- `python_callable` adapter 지원
- `http_api` adapter 지원
- custom model 디렉터리 전체 로드 helper
- manifest -> `StageManifest` 변환

현재 지원 규칙:

- Python 모델은 `module:symbol` import path로 등록한다.
- HTTP API 모델은 stage request JSON을 POST하고 stage response JSON을 반환해야 한다.
- API endpoint는 manifest의 `endpoint_url` 또는 `endpoint_url_env`로 설정한다.
- API credential은 `resolved_credentials`에서 꺼내 헤더로 전달할 수 있다.

비고:

- 아직 plugin 설치/배포 자동화는 없다.
- 현재 범위는 "개발자가 manifest와 adapter entrypoint를 추가하면 쉽게 붙일 수 있는 수준"이다.

### 11. Built-in CRAFT Text Detection

구현 파일:

- `contracts/text_regions.py`
- `builtin_models/craft_text_detection.py`
- `builtin_models/__init__.py`
- `scripts/run_craft_sample.py`
- `SAMPLE_IMAGES.md`

구현 내용:

- `text_regions` payload/dataclass 계약 추가
- built-in `text_detection=CRAFT` manifest/adapter 등록 함수 추가
- CRAFT 결과를 `text_regions` artifact로 정규화
- stage meta에 `text_detection.engine=craft` 기록
- 샘플 이미지 실행용 runner 추가

현재 지원 규칙:

- 입력은 `bitmap` artifact 하나 이상 필요
- 현재는 `file://` 기반 bitmap/workspace만 지원
- 출력은 `text_regions` artifact + `set_stage_meta(text_detection)` patch
- built-in model id는 `builtin.craft.text_detection`

비고:

- 실제 추론 런타임은 `craft-text-detector` 설치가 필요하다.
- 현재 저장소 테스트는 fake detector로 계약과 artifact 생성을 검증한다.

### 12. Rule-based mask_or_erase_planning + Nanobanana Inpaint

구현 파일:

- `contracts/inpaint_tasks.py`
- `stages/mask_or_erase_planning.py`
- `builtin_models/nanobanana_inpaint.py`
- `scripts/run_inpaint_sample.py`
- `scripts/preload_craft.py`
- `docker-compose.inference.yml`
- `tests/test_nanobanana_inpaint.py`

구현 내용:

- `inpaint_tasks` payload/dataclass 계약 추가
- 규칙 기반 `mask_or_erase_planning` stage 구현
- `text_regions -> erase_mask + inpaint_tasks` 변환
- built-in `inpaint=nanobanana` manifest/adapter 등록 함수 추가
- provider 전체 페이지 결과에서 mask 영역만 별도 `layer_inpainting` bitmap으로 유지
- provider 실패 시 partial bitmap + failure snapshot 보존
- 샘플 이미지 실행용 end-to-end runner 추가
- Compose 기반 샘플 실행 경로 추가
- host-mounted `.cache/models` 재사용을 위한 preload 경로 추가
- nanobanana 기본 model name을 `gemini-3.1-flash-image-preview`로 변경

현재 지원 규칙:

- planner는 `text_regions`와 `bitmap`을 입력으로 받는다
- planner는 `layer_inpainting` 대상 task와 mask artifact를 만든다
- inpaint stage는 `layer_inpainting` 이외의 레이어를 거부한다
- provider에는 원본 페이지 전체 이미지를 1회 전달하고, planner mask는 로컬 합성에만 사용한다
- inpaint 결과는 원본 페이지와 병합하지 않고 새 `layer_inpainting` artifact로만 저장된다
- provider가 돌려준 전체 페이지 원본 출력도 별도 bitmap artifact로 저장한다
- transaction 경로 아래에 mask/task/output/snapshot 파일이 정리된다
- nanobanana 호출 prompt는 stage config override가 없으면 기본 프롬프트를 사용한다

비고:

- 실제 Vertex AI 호출은 `google-genai` 런타임이 필요하다
- 현재 저장소 테스트는 fake image edit 함수로 planner/composite/failure snapshot 계약을 검증한다

## 테스트 상태

테스트 파일:

- `tests/test_contracts.py`
- `tests/test_credentials.py`
- `tests/test_orchestrator.py`
- `tests/test_ipc.py`
- `tests/test_model_merge.py`
- `tests/test_custom_models.py`
- `tests/test_craft_text_detection.py`
- `tests/test_nanobanana_inpaint.py`

검증한 항목:

- document IR patch 적용
- artifact registry 등록/검증/release/gc
- local persisted / SaaS platform credential resolution
- orchestrator의 순차 stage 실행
- stage 실패 시 이후 stage 중단
- subprocess IPC를 통한 stage 실행
- IPC stage 실패 시 pipeline 중단
- manifest 기반 Python custom model 로드/실행
- manifest 기반 HTTP API custom model 로드/실행
- built-in CRAFT text detection artifact 생성/registry 실행
- 규칙 기반 planner와 nanobanana inpaint composite 실행
- transaction-scoped artifact 저장 경로
- nanobanana failure snapshot 보존
- multipart upload를 artifact descriptor로 정규화
- `document_patch` 응답 생성

현재 상태:

- `python3 -m unittest discover -s model_engine/tests -v`
- 총 20개 테스트 통과
- subprocess child env로 credential secret 주입
- manifest 기반 adapter selection
- `preferred_model_id` override
- credential source에 따른 inpaint adapter filtering
- Python 3.9 환경 문법 호환

실행 명령:

```bash
PYTHONPYCACHEPREFIX=/tmp/pythoncache python3 -m unittest discover -s model_engine/tests -v
```

결과:

- 20 tests passed

## 아직 구현하지 않은 것

아래는 의도적으로 보류했다.

- typesetting/layout stage 구현
- postprocess stage 구현
- durable artifact backend
- session credential ingress flow
- provider별 secret manager adapter
- GPU/container runtime 분화
- 실제 Vertex AI billable smoke run
- UI 반환 포맷
- capability contract test 세분화

이 항목들은 `PLAN.md` 기준으로 아직 스펙이 덜 닫혀 있거나, 외부 provider 계약이 필요하다.

## 최근 설계 결정

- custom model 충돌 회피 전략으로 `runtime isolation` 원칙을 명시했다.
- 앞으로 custom model의 장기 기본 실행 방식은 같은 Python 프로세스 import가 아니라 격리 worker runtime이다.
- capability와 runtime을 분리해서 본다.
  - capability 예: `translation`, `ocr`, `inpaint`
  - runtime family 예: `craft-py310-cpu`, `gemini-http-light`, `custom-translation-cu124`
- `python_callable`은 계속 지원하지만 개발/실험용 우선 경로로 본다.
- 장기 기본 backend 후보는 `http_api`, `subprocess_ipc`, `container_worker`다.
- 같은 runtime image에 모든 모델 의존성을 누적하는 방식은 피하고, ABI/의존성이 같은 것끼리 runtime family로 묶는 쪽을 기준으로 한다.
- stage migration 기준도 고정했다.
  - `text_detection`, `ocr`, `translation`, `inpaint`는 장기적으로 worker 또는 remote backend 우선
  - `mask_or_erase_planning`은 당분간 in-process 유지
  - `typesetting`, `postprocess`는 실제 의존성 무게에 따라 단계적으로 분리

## 이번 구현

- `StageManifest`에 runtime isolation 관련 필드를 추가했다.
  - `execution_backend`
  - `runtime_family`
  - `runtime_image`
  - `runtime_command`
  - `python_version`
  - `cuda_version`
  - `dependency_lock_ref`
  - `cache_mounts`
  - `network_policy`
- custom model spec/loader가 `container_worker` adapter type을 지원한다.
- baseline `ContainerWorkerModelAdapter`를 추가했다.
  - `docker run --rm -i`로 worker를 1회성 실행
  - `StageRequest`/`StageResponse`는 stdin/stdout JSON IPC 사용
  - workspace와 path mapping, cache mount를 컨테이너로 전달
  - credential secret은 기존 subprocess IPC와 같은 env 주입 경로를 재사용
- stage selection 결과 메타데이터에 `execution_backend`, `runtime_family`를 기본으로 남기도록 했다.
- 특정 local translation model 병합 예시는 제거하고, `container_worker` adapter는 generic custom runtime 기반으로만 유지한다.

## 다음 구현 후보

현재 코드에서 다음 단계로 자연스러운 순서는 아래다.

1. `text_regions` / `text_blocks` 연결 규칙을 더 닫기
2. typesetting/layout stage 구현
3. orchestrator에 optional stage / partial failure 정책 추가
4. capability contract test를 adapter별 공통 테스트로 분리
5. 실제 Vertex AI smoke run과 error mapping 검증
6. 장기적으로 subprocess IPC와 별개로 socket/queue transport가 필요한지 판단
7. session credential을 실제 login/session 경로와 연결

## 메모

- Python 3.9 환경에서 돌아가도록 구현했다.
- `pydantic` 없이 표준 라이브러리 기반으로 작성했다.
- 수정 범위는 `model_engine/` 내부로 제한했다.
- 현재 Dockerfile은 CPU 개발용 최소 이미지다.
- 실제 provider key는 코드/저장소에 하드코딩하지 않고 credential binding 경로로만 주입한다.
- custom model 통합은 "모델 import"보다 "runtime worker 호출"을 기본 방향으로 기억한다.
