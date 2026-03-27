# Custom Models

`model_engine`에서 custom model을 붙이는 방법을 정의한 문서다.  
이 문서는 Python 로컬 모델과 HTTP API 모델을 같은 계약으로 등록하는 기준서다.

## 1. 목표

- 개발자가 `model_engine` 코드를 크게 뜯지 않고 모델을 붙일 수 있어야 한다.
- local Python 모델과 외부 API 모델이 같은 `stage capability` 계약에 합류해야 한다.
- custom model도 built-in 모델과 동일하게 `manifest + adapter + StageResponse`를 따라야 한다.

## 2. 지원 방식

현재 지원하는 custom adapter 타입은 두 가지다.

- `python_callable`
  - 같은 Python 환경 안에서 함수를 직접 호출한다.
  - 로컬 모델, PyTorch 모델, 실험용 모델에 적합하다.

- `http_api`
  - JSON 기반 stage request를 HTTP POST로 전송한다.
  - 외부 inference 서버, SaaS provider, 사내 API 래퍼에 적합하다.

## 3. 등록 절차

1. custom model manifest JSON 파일을 만든다.
2. Python 모델이면 `import_path`, API 모델이면 `endpoint_url` 또는 `endpoint_url_env`를 적는다.
3. `ModelRegistry`에 `CustomModelLoader`로 디렉터리 전체를 로드한다.
4. `AdapterBackedStage`가 capability 기준으로 호환 모델을 선택한다.

## 4. Manifest Schema

파일 확장자는 `.json`이고, 현재 `schema_version`은 `v1`만 지원한다.

```json
{
  "schema_version": "v1",
  "adapter_type": "python_callable",
  "model_id": "custom.example.detector",
  "adapter_id": "adapter.custom.example.detector",
  "stage_kind": "text_detection",
  "input_contract_version": "v1",
  "output_contract_version": "v1",
  "required_artifact_kinds": ["bitmap"],
  "produced_artifact_kinds": ["text_regions"],
  "supported_modes": ["local", "saas"],
  "allowed_credential_sources": ["none"],
  "billing_modes": ["none"],
  "resource_profile": {
    "cpu_threads": 2,
    "memory_mb": 1024,
    "gpu_required": false,
    "gpu_memory_mb": 0,
    "latency_tier": "default"
  },
  "custom_model": true,
  "priority": 100,
  "display_name": "Example Detector",
  "tags": ["custom", "example"],
  "adapter_config": {
    "import_path": "model_engine.custom_models.demo:demo_text_detection"
  }
}
```

## 5. Python Callable 모델

`python_callable`은 `module.submodule:symbol` 형식의 `import_path`를 사용한다.

요구사항:

- symbol은 callable이어야 한다.
- 시그니처는 `fn(request: StageRequest) -> StageResponse`를 따른다.
- 출력은 반드시 표준 `StageResponse`여야 한다.

예:

```python
from model_engine.contracts.stages import StageRequest, StageResponse


def my_detector(request: StageRequest) -> StageResponse:
    ...
```

## 6. HTTP API 모델

`http_api`는 `StageRequest` JSON을 그대로 POST하고, 응답으로 `StageResponse` JSON을 받아야 한다.

`adapter_config` 예:

```json
{
  "endpoint_url_env": "TOWA_CUSTOM_API_URL",
  "timeout_seconds": 30,
  "headers": {
    "X-Towa-Model": "demo"
  },
  "auth_header_name": "Authorization",
  "auth_header_prefix": "Bearer",
  "credential_alias": "primary_provider"
}
```

규칙:

- `endpoint_url` 또는 `endpoint_url_env` 중 하나는 필수다.
- `auth_header_name`이 있으면 orchestrator가 해석한 `resolved_credentials[credential_alias]`의 secret을 헤더로 주입한다.
- raw secret은 stage JSON 본문에 포함되지 않는다.

## 7. 로딩 예시

```python
from model_engine.models import ModelRegistry
from model_engine.stages import AdapterBackedStage
from model_engine.contracts.models import StageKind

registry = ModelRegistry()
registry.load_custom_model_directory("model_engine/custom_model_specs")

stage = AdapterBackedStage(
    "text_detection",
    stage_kind=StageKind.TEXT_DETECTION,
    registry=registry,
)
```

## 8. 개발자 체크리스트

- manifest의 `stage_kind`가 실제 capability와 맞는가
- `required_artifact_kinds`가 현재 pipeline 입력과 맞는가
- `allowed_credential_sources`가 local/SaaS 실행 방식과 맞는가
- 반환값이 항상 `StageResponse`인가
- patch/artifact/report가 README의 공통 계약을 따르는가

## 9. 현재 범위와 한계

현재는 다음까지 지원한다.

- manifest JSON 기반 custom model 로딩
- Python callable custom model
- HTTP API custom model
- capability/credential/schema 호환성 기반 선택

아직 없는 것:

- wheel/plugin 설치 자동화
- registry hot reload
- provider별 재시도/서킷브레이커 정책
- sandbox 격리된 third-party plugin 실행 환경
