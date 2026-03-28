# model_engine Progress

## 기준 문서

- `README.md`: 현재 `model_engine` 내부 구현 기준서
- `PLAN.md`: 확정/미확정 범위 판단 기준
- `SPEC.md`, `API_CONTRACT.md`: 외부 엔진 경계와 SaaS/local 계약 참고

## 이번에 구현한 범위

현재 `PLAN.md`에서 이미 확정된 공통 계약층만 구현했다. 아직 미정인 OCR/번역/식자/실제 provider adapter는 구현하지 않았다.

README 기준서는 현재 코드와 동기화해 유지 중이다. 특히 stage IPC, artifact lifecycle, credential binding/key management 규칙을 README에 먼저 고정하고 그 범위까지만 구현했다.

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
- 미정 영역 때문에 snapshot 기반 예외 경로는 아직 구현하지 않았다.

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
- session credential source는 타입과 런타임 필드만 열어두고, 실제 세션 주입 흐름은 아직 미구현이다.

### 8. Container Bootstrap

구현 파일:

- `Dockerfile`
- `Dockerfile.inference`
- `.dockerignore`
- `requirements-base.txt`
- `requirements-craft.txt`

구현 내용:

- Python 실행 가능한 최소 컨테이너 환경
- 기본 개발/테스트 이미지와 추론용 이미지 분리
- base/craft 의존성 파일 분리
- `/app` 작업 디렉토리
- `/workspace`, `/artifacts`, `/cache` 기본 경로 생성
- 기본 `CMD`로 현재 테스트 스위트 실행

비고:

- `Dockerfile`은 contract test와 개발용 기본 이미지다.
- `Dockerfile.inference`는 CRAFT 같은 로컬 모델 의존성을 담는 추론용 이미지다.
- 아직 GPU 세팅은 넣지 않았다.
- 현재 목적은 추론 런타임을 별도 이미지로 분리해 재현성과 확장성을 확보하는 것이다.

### 9. Model Merge / Adapter Registry

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
- `samples/images/README.md`

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
- `tests/test_nanobanana_inpaint.py`

구현 내용:

- `inpaint_tasks` payload/dataclass 계약 추가
- 규칙 기반 `mask_or_erase_planning` stage 구현
- `text_regions -> erase_mask + inpaint_tasks` 변환
- built-in `inpaint=nanobanana` manifest/adapter 등록 함수 추가
- crop 단위 inpaint 결과를 `layer_inpainting`용 bitmap으로 composite

현재 지원 규칙:

- planner는 `text_regions`와 `bitmap`을 입력으로 받는다
- planner는 `layer_inpainting` 대상 task와 mask artifact를 만든다
- inpaint stage는 `layer_inpainting` 이외의 레이어를 거부한다
- inpaint 결과는 새 bitmap artifact로 저장되고, 문서에는 `add_layer` 또는 `replace_source_ref` patch로 반영된다
- nanobanana 호출 prompt는 stage config override가 없으면 기본 프롬프트를 사용한다

비고:

- 실제 Vertex AI 호출은 `google-genai` 런타임이 필요하다
- 현재 저장소 테스트는 fake image edit 함수로 planner/composite 계약을 검증한다

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

현재 상태:

- `python3 -m unittest discover -s model_engine/tests -v`
- 총 19개 테스트 통과
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

- 12 tests passed

## 아직 구현하지 않은 것

아래는 의도적으로 보류했다.

- 실제 `text_detection=CRAFT` stage 실행체
- 실제 `inpaint=나노바나나 API` adapter
- OCR stage 구현
- translation stage 구현
- typesetting/layout stage 구현
- postprocess stage 구현
- durable artifact backend
- session credential ingress flow
- provider별 secret manager adapter
- GPU/container runtime 분화
- UI 반환 포맷
- capability contract test 세분화

이 항목들은 `PLAN.md` 기준으로 아직 스펙이 덜 닫혀 있거나, 외부 provider 계약이 필요하다.

## 다음 구현 후보

현재 코드에서 다음 단계로 자연스러운 순서는 아래다.

1. `text_detection` stage contract를 `CRAFT` 기준으로 구체화
2. `text_regions` / `text_blocks` schema를 더 닫기
3. `inpaint` stage용 provider adapter interface 정의
4. orchestrator에 optional stage / partial failure 정책 추가
5. `AdapterBackedStage`를 실제 capability stage에 연결
6. capability contract test를 adapter별 공통 테스트로 분리
7. 장기적으로 subprocess IPC와 별개로 socket/queue transport가 필요한지 판단
8. session credential을 실제 login/session 경로와 연결

## 메모

- Python 3.9 환경에서 돌아가도록 구현했다.
- `pydantic` 없이 표준 라이브러리 기반으로 작성했다.
- 수정 범위는 `model_engine/` 내부로 제한했다.
- 현재 Dockerfile은 CPU 개발용 최소 이미지다.
