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
- `inpaint` custom model이면 `inpaint_tasks`를 입력으로 받고 `inpainting layer`만 갱신하는가

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

## 10. 실행 방법

기본 검증은 테스트 스위트부터 돌리는 것이 가장 안전하다.

```bash
PYTHONPYCACHEPREFIX=/tmp/pythoncache python3 -m unittest discover -s model_engine/tests -v
```

### 10-1. Built-in CRAFT 실행

처음 한 번은 모델 weight를 미리 받아두는 쪽이 훨씬 빠르다.

```bash
cd model_engine
docker compose -f docker-compose.inference.yml run --rm craft-preload
```

이 명령은 CRAFT weight를 호스트의 `model_engine/.cache/models/` 아래에 받아둔다. 이후 `craft-sample`와 `inpaint-sample`는 같은 캐시를 재사용한다.

샘플 이미지로 `text_detection=CRAFT`만 실행하려면 아래 스크립트를 사용한다.

```bash
python3 model_engine/scripts/run_craft_sample.py \
  --image model_engine/samples/images/sample_page.webp \
  --workspace model_engine/.runtime
```

결과 `text_regions` artifact는 transaction 경로 아래에 생성된다.

- `model_engine/.runtime/transactions/pipe_craft_sample/text_detection/...`
- 현재 샘플 실행 결과 예:
  - `model_engine/.runtime/transactions/pipe_craft_sample/text_detection/pipe_craft_sample_text_detection_1/pipe_craft_sample_text_detection_1_text_regions.json`

복잡한 명령 대신 Docker Compose로도 바로 실행할 수 있다.

```bash
cd model_engine
docker compose -f docker-compose.inference.yml run --rm craft-sample
```

권장 순서:

1. `docker compose -f docker-compose.inference.yml run --rm craft-preload`
2. `docker compose -f docker-compose.inference.yml run --rm craft-sample`

### 10-2. Built-in Inpaint 실행

`CRAFT -> mask_or_erase_planning -> nanobanana inpaint` 최소 흐름은 아래 스크립트로 실행한다.

```bash
export TOWA_NANOBANANA_API_KEY="YOUR_API_KEY"

python3 model_engine/scripts/run_inpaint_sample.py \
  --image model_engine/samples/images/sample_page.webp \
  --workspace model_engine/.runtime
```

규칙:

- API 키는 코드나 manifest에 쓰지 않고 환경 변수로만 넣는다.
- `inpaint` 결과는 원본 페이지와 병합되지 않고 새 `inpainting layer` artifact로 남는다.
- planner mask는 provider에 보내지 않고 로컬 `inpainting layer` 합성에만 쓴다.
- 생성 파일은 모두 transaction 경로 아래에 저장된다.
- provider가 멈추거나 timeout이면 stage는 `failed`가 되고, partial bitmap + failure snapshot이 남는다.
- 현재 기본 image model 이름은 사용자 지정 최신값인 `gemini-3.1-flash-image-preview`를 사용한다.

결과물을 보는 위치:

- CRAFT 결과:
  - `model_engine/.runtime/transactions/pipe_craft_sample/text_detection/.../text_regions.json`
- planner 결과:
  - `model_engine/.runtime/transactions/pipe_inpaint_sample/mask_or_erase_planning/.../inpaint_tasks.json`
  - `model_engine/.runtime/transactions/pipe_inpaint_sample/mask_or_erase_planning/.../mask_0001.png`
- inpaint 결과:
  - `model_engine/.runtime/transactions/pipe_inpaint_sample/inpaint/.../provider_output.png`
  - `model_engine/.runtime/transactions/pipe_inpaint_sample/inpaint/.../inpainting.png`
  - 실패 시 같은 디렉터리 아래 `partial_inpainting.png`, `failure_snapshot.json`

기본 API 키 환경 변수 이름은 `TOWA_NANOBANANA_API_KEY`이며, 필요하면 `--api-key-env`로 바꿀 수 있다.

Compose로 실행하면 더 단순하다.

```bash
cd model_engine
export TOWA_NANOBANANA_API_KEY="YOUR_API_KEY"
docker compose -f docker-compose.inference.yml run --rm inpaint-sample
```

권장 순서:

1. `docker compose -f docker-compose.inference.yml run --rm craft-preload`
2. `docker compose -f docker-compose.inference.yml run --rm inpaint-sample`

Compose 파일은 아래를 자동으로 처리한다.

- `Dockerfile.inference` 빌드
- `model_engine/.runtime -> /workspace_out` 마운트
- `model_engine/.cache/models -> /cache/models` 마운트
- 샘플 이미지 경로와 workspace 경로 전달
- `HOME`, `XDG_CACHE_HOME`, `TORCH_HOME`을 `/cache/models` 기준으로 고정

주의:

- 현재 `Dockerfile.inference`는 CRAFT 호환성을 위해 Python 3.10을 사용한다.
- `craft-text-detector` 계열이 Python 3.11에서 `numpy==1.21.2` 의존성 때문에 실패할 수 있어서, CRAFT 실행은 compose/inference 이미지 기준으로 맞춰두었다.
- OpenCV 런타임 때문에 `libGL.so.1`이 필요하므로, 로컬이 아니라 inference 이미지 안에서 실행하는 것을 기준으로 본다.
- CRAFT/OpenCV 조합은 현재 NumPy 2.x와 ABI 충돌이 날 수 있어서 inference 의존성은 `numpy<2`로 고정했다.
- CRAFT 이미지에서는 `opencv-python==4.7.0.72` 한 계열만 설치해 `cv2.dnn.DictValue` 충돌을 피한다.

### 10-3. Built-in OCR 실행

`CRAFT -> manga-ocr` 최소 흐름은 아래 스크립트로 실행한다.

```bash
python3 model_engine/scripts/run_ocr_sample.py \
  --image model_engine/samples/images/sample_page.webp \
  --workspace model_engine/.runtime
```

규칙:

- `ocr` stage는 `text_regions`를 입력으로 받아 `DocumentIR.text_blocks`를 교체한다.
- canonical OCR artifact는 `ocr_text_blocks` JSON이다.
- `manga-ocr`는 Hugging Face / Transformers cache를 사용한다.

결과물을 보는 위치:

- detection 결과:
  - `model_engine/.runtime/transactions/pipe_ocr_sample/text_detection/.../text_regions.json`
- OCR 결과:
  - `model_engine/.runtime/transactions/pipe_ocr_sample/ocr/.../ocr_text_blocks.json`

Compose로 실행하면 더 단순하다.

```bash
cd model_engine
docker compose -f docker-compose.inference.yml run --rm ocr-sample
```

권장 순서:

1. `docker compose -f docker-compose.inference.yml run --rm craft-preload`
2. `docker compose -f docker-compose.inference.yml run --rm ocr-preload`
3. `docker compose -f docker-compose.inference.yml run --rm ocr-sample`

Compose 파일은 OCR 실행 시 아래 cache를 재사용한다.

- `torch` cache
- Hugging Face / Transformers cache
- `ocr-preload`는 `kha-white/manga-ocr-base` 모델 파일을 host-mounted `model_engine/.cache/models/` 아래로 미리 받아둔다.
- CRAFT가 `torchvision.models.vgg.model_urls`를 직접 참조하므로, 추론 이미지는 `torch==1.12.1`, `torchvision==0.13.1` 조합으로 고정한다.

### 10-4. Built-in Translation 실행

`CRAFT -> manga-ocr -> Vertex translation` 최소 흐름은 아래 스크립트로 실행한다.

```bash
export TOWA_TRANSLATION_PROVIDER_API_KEY="YOUR_API_KEY"
python3 model_engine/scripts/run_translation_sample.py \
  --image model_engine/samples/images/sample_page.webp \
  --workspace model_engine/.runtime
```

규칙:

- `translation` stage는 `DocumentIR.text_blocks`를 읽고 `translated_text`만 채운다.
- canonical translation artifact는 `translated_text_blocks` JSON이다.
- Vertex 호출 credential 경로는 `nanobanana`와 동일한 `google-genai` / API key binding 방식을 재사용한다.

Compose로 실행하면 더 단순하다.

```bash
cd model_engine
docker compose -f docker-compose.inference.yml run --rm translation-sample
```

권장 순서:

1. `docker compose -f docker-compose.inference.yml run --rm craft-preload`
2. `docker compose -f docker-compose.inference.yml run --rm ocr-preload`
3. `docker compose -f docker-compose.inference.yml run --rm translation-sample`

### 10-3. Custom Python 모델 실행 흐름

1. manifest JSON을 만든다.
2. `adapter_config.import_path`에 `module:symbol`을 적는다.
3. `ModelRegistry.load_custom_model_directory(...)`로 manifest 디렉터리를 로드한다.
4. `AdapterBackedStage(stage_kind=...)`로 stage를 실행한다.

예시 코드는 `custom_models/demo.py`와 `tests/test_custom_models.py`를 기준으로 보면 된다.

### 10-4. Custom HTTP API 모델 실행 흐름

1. manifest JSON에 `adapter_type=http_api`를 적는다.
2. `endpoint_url` 또는 `endpoint_url_env`를 설정한다.
3. 필요하면 `auth_header_name`, `auth_header_prefix`, `credential_alias`를 설정한다.
4. orchestrator가 해석한 credential은 헤더로만 전달되고, stage JSON 본문에는 raw secret이 들어가지 않는다.

API custom model 예시는 `tests/test_custom_models.py`의 `custom.remote.inpaint` 케이스를 기준으로 보면 된다.
