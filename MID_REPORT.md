# TOWA 중간보고서

## 1. 프로젝트 개요

TOWA는 만화 번역을 위한 통합 워크스테이션 with AI 개발 프로젝트이다. 사용자는 한 장 또는 여러 장의 만화 이미지를 불러오고, AI가 원문 텍스트 검출, OCR, 번역, 말풍선 지우기, 인페인팅, 식자 보조 작업을 수행한 뒤, 사용자가 최종 결과를 편집하고 저장하는 흐름을 목표로 한다.

프로젝트는 역할에 따라 세 엔진으로 분리되어 있다.

- `ui_engine`: 사용자가 직접 조작하는 편집 화면, 프로젝트 목록, 페이지 편집 상태, AI 작업 요청 UI를 담당한다.
- `service_engine`: 사용자 세션, 인증, 프로젝트/페이지 저장, usage/credit 관리, cloud 저장 authority를 담당한다.
- `model_engine`: OCR, 번역, 인페인팅 등 AI 추론 파이프라인과 모델 provider 연동을 담당한다.

이번 중간 단계에서 집중한 범위는 주로 `model_engine`이다. 초기에는 샘플 이미지를 대상으로 독립 실행되는 추론 스크립트 중심이었지만, 이번 작업을 통해 `model_engine`을 실제 `UI engine`과 `service_engine` 사이에서 HTTP job을 받고, 사용량을 기록하며, 결과를 `document_patch` 형태로 돌려줄 수 있는 실행 주체로 확장했다.

## 2. 개발 목표

이번 중간 개발의 목표는 단순히 OCR이나 번역 모델 하나를 붙이는 것이 아니라, 실제 제품 흐름에 필요한 AI 실행 기반을 만드는 것이었다.

구체 목표는 다음과 같다.

1. `model_engine` 내부에서 문서, 레이어, 텍스트 블록, 이미지 산출물을 일관된 IR로 다룰 수 있게 한다.
2. CRAFT, manga-ocr, OpenAI-compatible LLM, Vertex Gemini, nanobanana 인페인팅을 stage 단위로 연결한다.
3. 만화 OCR에서 발생하는 세로쓰기 정렬 오류, region over-segmentation, OCR hallucination 문제를 후처리로 완화한다.
4. `service_engine`의 세션과 usage authority를 침범하지 않고, SaaS 모드에서 usage hold/capture/release를 연동한다.
5. `UI engine`이 실제 이미지를 `model_engine`에 넘길 수 있도록 `multipart(metadata + primary_bitmap)` job 입력 계약을 마련한다.
6. AI 결과를 전체 문서 교체가 아니라 `document_patch`로 반환하여 UI가 현재 편집 상태에 병합할 수 있게 한다.
7. 현재는 API 서버와 추론 배치 컨테이너가 분리되어 있으므로, 다음 단계에서 `API + Inference` 통합 서빙 컨테이너로 전환할 계획을 수립한다.

따라서 이번 중간 결과물은 "완성된 만화 번역 애플리케이션"이 아니라, 실제 E2E를 만들기 위한 `model_engine` 실행 기반과 엔진 간 계약을 정리한 단계라고 볼 수 있다.

## 3. 전체 아키텍처 정리

### 3.1 엔진별 책임

현재 아키텍처에서 가장 중요하게 정리한 것은 각 엔진의 authority를 섞지 않는 것이다.

`service_engine`은 인증과 저장의 기준점이다. 세션 키를 발급하고 검증하며, 사용자의 credit balance와 reserved units를 관리한다. 또한 cloud 모드에서 프로젝트와 페이지 snapshot 저장의 authority를 가진다.

`model_engine`은 AI 작업 실행 주체이다. 입력 이미지를 받아 text detection, OCR, translation, inpaint 같은 stage를 실행하고, 결과를 patch와 artifact로 반환한다. 다만 사용자 인증 자체나 credit ledger를 직접 소유하지 않는다.

`ui_engine`은 사용자가 보는 현재 page state를 기준으로 AI 입력을 구성하고, AI 결과를 받아 화면에 병합한다. AI 결과를 최종적으로 사용자의 편집 상태에 반영하고 저장하는 주체도 UI이다.

이 분리는 이후 서버리스 배포나 클라우드 확장 구조에서도 중요하다. AI 작업은 무겁고 비동기적이지만, 인증과 저장 authority는 비교적 안정적이고 일관된 service layer에 남아야 하기 때문이다.

### 3.2 Cloud 모드와 Standalone 모드

Cloud 모드에서는 세 엔진이 모두 동작한다.

표준 흐름은 다음과 같다.

1. UI가 `service_engine`에 로그인 요청을 보내 `session_key`를 받는다.
2. UI가 프로젝트와 페이지 snapshot을 `service_engine`에 저장하거나 불러온다.
3. UI가 `model_engine`에 AI job을 요청하면서 같은 `session_key`를 `Authorization: Bearer <session_key>`로 전달한다.
4. `model_engine`은 작업 시작 전 `service_engine`에 usage hold를 요청한다.
5. AI 작업이 성공하면 capture, 실패하면 release를 요청한다.
6. UI는 `model_engine`의 결과를 받아 현재 page state에 병합한다.
7. UI는 최종 편집 결과를 다시 `service_engine`에 full snapshot으로 저장한다.

Standalone 모드에서는 `service_engine`이 필수가 아니다. UI와 model이 로컬에서 직접 연결될 수 있고, provider key나 로컬 모델 경로는 `model_engine` runtime policy에 따라 처리한다.

## 4. Model Engine 내부 데이터 구조

### 4.1 DocumentIR

`model_engine` 내부에서는 Bitmappery의 문서 의미론을 참고하여 `DocumentIR`을 기준 데이터 구조로 삼았다.

`DocumentIR`에는 문서 크기, 레이어, 텍스트 블록, stage metadata가 들어간다. 이 구조는 향후 UI 편집 상태와 AI 결과를 연결하기 위한 중간 표현이다.

구현된 주요 구조는 다음과 같다.

- `DocumentIR`: 페이지 단위 문서 구조
- `LayerIR`: 원본 이미지, 인페인팅 레이어, 식자 레이어 등 레이어 표현
- `TextBlock`: OCR 원문과 번역문, bbox, polygon, reading order 등 텍스트 블록 표현
- `Transform`: scale, rotation, mirror 등 레이어 변환 정보
- `FilterSettings`: 레이어 필터 설정
- `TextStyle`: 식자 단계에서 사용할 수 있는 텍스트 스타일 기반

초기에는 Bitmappery의 `.bpy` 구조를 그대로 내부 교환 포맷으로 사용할 가능성도 검토했으나, `.bpy`는 비트맵이 base64로 인라인되는 self-contained 저장 포맷이기 때문에 AI stage 간 교환에는 비효율적이라고 판단했다.

따라서 `model_engine` 내부에서는 문서 구조와 큰 바이너리 산출물을 분리한다.

- 문서 구조: `document_ir`
- 큰 이미지, 마스크, OCR raw, 인페인팅 결과: `artifact_refs`

이 방식은 stage 하나가 작은 변경을 만들 때 전체 문서를 다시 압축하거나 큰 이미지를 JSON에 반복 포함하지 않아도 된다는 장점이 있다.

### 4.2 Patch 기반 변경

AI stage 결과는 전체 문서를 통째로 교체하는 방식보다 patch로 표현하는 편이 안전하다. 특히 UI는 사용자가 편집 중인 상태를 가지고 있으므로, AI 결과가 전체 page state를 덮어쓰면 충돌이나 데이터 손실이 발생할 수 있다.

이를 위해 `PatchOperation` 기반 변경 계약을 구현했다.

대표 patch op는 다음과 같다.

- `add_layer`: 새 레이어 추가
- `remove_layer`: 기존 레이어 제거
- `update_layer_props`: 레이어 속성 갱신
- `replace_source_ref`: 레이어 source artifact 교체
- `replace_mask_ref`: 레이어 mask artifact 교체
- `set_layer_text`: 레이어 텍스트 설정
- `append_text_blocks`: OCR/번역 텍스트 블록 추가
- `replace_text_blocks`: 텍스트 블록 목록 교체
- `set_stage_meta`: stage 실행 결과 metadata 기록
- `attach_artifact`: artifact를 문서에 연결
- `detach_artifact`: artifact 연결 해제

이번 단계에서 `GET /v1/jobs/{job_id}` 응답에 `document_patch` 필드를 추가한 것도 이 설계와 연결된다. UI는 장기적으로 full `document`보다 `document_patch`를 기준으로 현재 page state에 결과를 병합해야 한다.

### 4.3 Artifact 관리

큰 산출물은 `ArtifactDescriptor`로 표현한다.

`ArtifactDescriptor`에는 다음 정보가 포함된다.

- `artifact_ref`
- `kind`
- `media_type`
- `uri`
- `width`
- `height`
- `byte_size`
- `checksum`
- `producer_stage`
- `status`

현재는 local `file://` URI와 in-memory registry 중심으로 동작한다. checksum verify도 지원한다. 운영용 durable storage나 presigned URL 기반 artifact handoff는 아직 구현하지 않았고, 다음 단계에서 별도 backend로 확장할 예정이다.

## 5. Stage Orchestration

`model_engine`의 AI 작업은 stage 단위로 구성된다. 각 stage는 입력 문서, artifact, stage config를 받아 실행되고, 변경 patch, 새 artifact, stage report를 반환한다.

현재 구현된 주요 stage는 다음과 같다.

- `text_detection`
- `ocr`
- `mask_or_erase_planning`
- `translation`
- `inpaint`

`PipelineOrchestrator`는 stage를 순차 실행한다. stage 결과로 나온 patch는 문서에 적용되고, 새 artifact는 registry에 등록된다. stage 실패 시 후속 stage를 중단하고 실패 report를 남기도록 했다.

또한 subprocess IPC 기반 stage 실행 구조도 마련했다. 지금은 가장 단순한 `stdin/stdout JSON` 방식이지만, custom model이나 독립 worker를 붙일 수 있는 방향을 열어두었다.

## 6. Built-in 모델 경로 구현

### 6.1 Text Detection: CRAFT

텍스트 검출은 CRAFT 기반 built-in model로 연결했다.

입력:

- 페이지 원본 bitmap artifact

출력:

- 텍스트 영역 polygon/bbox 목록
- `text_regions` artifact

이 stage는 OCR이 어느 영역을 읽을지 결정하는 첫 단계이므로 전체 파이프라인 품질에 큰 영향을 준다.

### 6.2 OCR: manga-ocr

OCR은 `manga-ocr`를 사용했다. 이 모델은 일본어 만화의 세로쓰기, 다양한 글꼴, 말풍선 텍스트를 어느 정도 처리할 수 있다는 장점이 있다. 다만 생성형 decoder를 사용하기 때문에 텍스트가 없거나 작은 영역에서 그럴듯한 문장을 만들어내는 hallucination 문제가 발생할 수 있다.

이번 작업에서 개선한 부분은 다음과 같다.

- OCR stage 내에서 `MangaOcr()` 인스턴스를 재사용하여 반복 초기화 비용을 줄였다.
- CRAFT region을 그대로 하나씩 OCR하지 않고, 인접 region merge를 추가했다.
- crop 영역에 padding을 주어 글자가 잘리는 문제를 완화했다.
- 세로쓰기 일본어 만화 기준으로 `vertical_rtl` reading order를 추가했다.
- 너무 작은 region은 OCR 전에 skip할 수 있게 했다.
- bbox 면적 대비 텍스트 길이가 비정상적으로 긴 경우 `needs_review`로 마킹했다.
- OCR block마다 density, area, text length를 metadata로 남겼다.

특히 `needs_review`를 drop이 아니라 mark로 처리한 것이 중요하다. OCR 결과가 의심스럽더라도 즉시 삭제하면 실제 작은 글자를 잃을 수 있다. 대신 UI에서 수동 검수 대상으로 강조할 수 있게 metadata를 남기는 쪽이 더 안전하다고 판단했다.

### 6.3 Translation: OpenAI-compatible / Vertex Gemini

번역 stage는 두 경로를 지원한다.

- OpenAI-compatible translation
- Vertex Gemini translation

OpenAI-compatible adapter는 아래 환경을 염두에 두었다.

- LM Studio
- Ollama
- OpenAI API
- Claude/Gemini 등을 OpenAI-compatible proxy 뒤에 둔 custom endpoint
- 로컬 LLM 서버

초기에는 매번 셸에서 export하는 방식이 번거로웠기 때문에, `model_engine/.runtime/runtime_config.json`을 통해 local runtime config를 읽도록 정리했다.

주요 설정 항목:

- `TOWA_TRANSLATION_BACKEND`
- `TOWA_TRANSLATION_MODEL_NAME`
- `TOWA_OPENAI_COMPATIBLE_BASE_URL`
- `TOWA_OPENAI_COMPATIBLE_API_KEY`
- `TOWA_NANOBANANA_API_KEY`

우선순위는 `env > runtime_config.json > default`이다. 이 파일은 Git ignore 대상이므로 provider key를 repository에 올리지 않는다.

현재 번역은 OCR된 block들을 한 번에 모아 LLM에 전달하는 batch 방식이다. 즉 OCR block이 10개면 LLM을 10번 호출하는 것이 아니라, `blocks` 배열을 한 요청에 담아 번역한다. 이 방식은 호출 비용과 latency를 줄이고, 문맥을 일부 공유할 수 있다는 장점이 있다.

다만 남은 과제도 있다.

- JSON response 강제와 repair
- `block_id` 정합성 검증 강화
- OCR `needs_review` 정보를 prompt에 반영
- 긴 페이지를 위한 chunking
- retry/backoff
- glossary/term map

### 6.4 Inpaint: nanobanana

인페인팅은 nanobanana provider를 Vertex AI 경유 built-in model로 연결했다.

현재 구현은 provider가 반환한 전체 페이지 이미지를 그대로 최종본으로 쓰지 않는다. 대신 planner가 만든 mask 영역만 취해 `inpainting layer` artifact를 만든다.

이 방식의 장점은 다음과 같다.

- 원본 페이지 bitmap을 직접 파괴하지 않는다.
- provider output과 최종 inpainting layer를 분리해서 비교할 수 있다.
- UI에서 인페인팅 레이어를 별도 편집 대상으로 다룰 수 있다.

결과 artifact는 보통 다음과 같이 구분된다.

- provider가 반환한 전체 결과 이미지
- mask 영역만 추출한 최종 inpainting layer
- 실패 시 partial artifact와 failure snapshot

## 7. OCR 품질 평가와 튜닝 결과

이번 작업 중 실제 OCR 결과를 확인하면서 중요한 사실을 확인했다. 번역 결과가 이상한 경우, 번역 모델 자체의 문제보다 OCR 입력이 이미 잘못된 경우가 많았다.

대표 문제는 다음과 같았다.

- 세로쓰기 말풍선의 reading order가 왼쪽에서 오른쪽으로 뒤집힘
- 한 문장이 여러 작은 block으로 과도하게 분리됨
- 스마트폰 UI나 작은 글자 영역에서 hallucination 발생
- 손글씨나 장식 글씨 영역에서 의미 없는 일본어 생성
- OCR 결과가 깨진 상태로 LLM 번역에 들어가 자연스러운 한국어 오역으로 변환됨

이를 해결하기 위해 OCR 평가를 번역 결과와 분리했다.

평가 기준:

- OCR 원문이 이미지와 맞는가
- block 단위가 너무 작거나 너무 크지 않은가
- reading order가 일본어 만화 기준으로 맞는가
- hallucination 의심 block이 `needs_review`로 표시되는가
- OCR metadata가 threshold 조정에 충분한 정보를 제공하는가

현재 OCR block에는 다음 metadata가 남는다.

- `ocr_text_density_per_1000_px2`
- `ocr_region_area_px`
- `ocr_text_length`
- `ocr_status`
- `ocr_warnings`

초기 density threshold가 너무 관대해 hallucination block이 걸리지 않았고, 실제 값 분석 후 기준을 낮춰 `needs_review` 마킹이 작동하도록 조정했다. 이 내용은 `model_engine/docs/TROUBLESHOOTING.md`에 정리했다.

## 8. Service Engine 연동

### 8.1 세션 책임 경계

세션 발급과 유효성 판단 authority는 `service_engine`에 있다.

Cloud 모드에서 UI는 `service_engine`의 로그인 API를 통해 `session_key`를 발급받고, 같은 session key를 `model_engine`에도 전달한다.

```http
Authorization: Bearer <session_key>
```

`model_engine`은 이 bearer가 존재하는지 확인하고, bearer 본문을 `runtime_context.service_session_key`로 저장한다. 하지만 이 토큰이 실제로 유효한지는 `model_engine`이 직접 판단하지 않는다.

실제 유효성 검증은 usage API 호출 과정에서 `service_engine`이 수행한다.

### 8.2 Usage lifecycle

AI 작업은 비용이 드는 작업이므로, SaaS 모드에서는 usage lifecycle을 따라야 한다.

현재 흐름:

1. `model_engine`이 job create 시 `service_engine`에 usage hold 요청
2. AI stage 실행
3. 성공하면 capture 요청
4. 실패하면 release 요청

초기에는 request-local raw authorization header에 의존하는 구조였으나, background job과 서버리스 가능성을 고려하면 request가 끝난 후에도 필요한 session context가 job에 남아 있어야 한다. 따라서 bearer에서 추출한 session token을 `runtime_context.service_session_key`에 저장하고, background billing은 이 값을 기준으로 인증 헤더를 재구성하도록 변경했다.

이로써 job lifecycle과 request lifecycle이 더 잘 분리되었다.

### 8.3 Job 소유권

`model_engine`은 SaaS job 조회 시 같은 사용자만 job을 조회할 수 있게 owner scope를 사용한다.

현재 방식:

- 요청 시 받은 `Authorization` 문자열을 정규화한다.
- 해당 문자열의 SHA-256 hash를 owner scope로 저장한다.
- poll 요청 시 다시 owner scope를 계산한다.
- owner scope가 다르면 `404 model_job_not_found`를 반환한다.

이 방식은 `model_engine`의 AI job 조회 권한을 제한하기 위한 것이다. 별도로 `service_engine`의 usage job은 service 내부에서 `user_id + job_id` 기준으로 보호된다.

## 9. UI / Model Job Contract

### 9.1 입력: multipart

`UI -> model` 입력은 `multipart/form-data`로 구체화했다.

필수 part:

- `metadata`
- `primary_bitmap`

`metadata`에는 JSON payload가 들어간다.

주요 필드:

- `schema_version`
- `idempotency_key`
- `operation_kind`
- `request_ref`
- `document`
- `artifacts`
- `runtime_context`

`document`는 service 저장용 full snapshot이 아니다. AI 실행에 필요한 최소 문서 projection이다.

`primary_bitmap`은 실제 AI가 읽어야 하는 핵심 bitmap이다. 항상 원본 이미지만 의미하는 것은 아니며, 향후 UI가 현재 렌더 상태를 보내는 경우에도 사용할 수 있다.

### 9.2 `upload://primary_bitmap` 처리

metadata의 artifact descriptor는 실제 binary를 직접 담지 않고 `upload://primary_bitmap` URI를 가진다.

예:

```json
{
  "artifact_ref": "artifact://input/primary_bitmap",
  "kind": "bitmap",
  "media_type": "image/png",
  "uri": "upload://primary_bitmap"
}
```

`model_engine`은 multipart part의 `primary_bitmap` 파일을 받아 임시 파일로 저장하고, descriptor의 URI를 `file://...`로 바꿔 내부 pipeline에 전달한다.

이 방식은 JSON body에 base64 이미지를 넣지 않으면서도, 별도 artifact store 없이 현재 단계의 E2E를 실행할 수 있게 한다.

### 9.3 출력: `document_patch`

기존에는 poll 결과의 `document`를 어떻게 해석해야 하는지 모호할 수 있었다. 이번 작업에서는 `document_patch` 필드를 추가해 UI가 병합해야 할 변경 사항을 명시했다.

응답 구조:

- `job_id`
- `pipeline_id`
- `status`
- `operation_kind`
- `request_ref`
- `document`
- `document_patch`
- `artifacts`
- `stage_reports`
- `error`

현재는 migration 기간이므로 full `document`도 함께 반환한다. 하지만 장기적으로 UI가 authoritative merge source로 사용해야 하는 것은 `document_patch`이다.

### 9.4 Idempotency

AI job은 사용자가 재시도하거나 UI가 같은 요청을 반복할 수 있으므로 idempotency가 필요하다.

현재 `model_engine` job create는 `idempotency_key`를 사용한다. 같은 key와 같은 payload는 replay로 처리할 수 있지만, 같은 key로 다른 payload를 보내면 conflict로 처리한다.

multipart 요청에서는 metadata뿐 아니라 업로드된 bitmap의 sha256도 fingerprint에 포함한다. 따라서 같은 metadata라도 이미지가 달라지면 다른 요청으로 판단한다.

## 10. API와 추론 서빙 전략

현재 `model_engine`에는 두 Docker 경로가 있다.

### 10.1 API image

`Dockerfile.api`는 FastAPI 서버를 띄우는 가벼운 이미지다.

역할:

- `/healthz`
- `/v1/jobs`
- `/bridge/service/...`

이 이미지는 HTTP contract와 service bridge smoke에는 적합하다. 하지만 CRAFT, manga-ocr, OpenCV 계열 시스템 패키지 등 무거운 inference runtime을 충분히 포함하지 않는다.

### 10.2 Inference image

`Dockerfile.inference`와 `docker-compose.inference.yml`은 실제 OCR/번역/inpaint 샘플 실행에 사용된다.

예:

- `craft-sample`
- `ocr-sample`
- `translation-sample`
- `pipeline`

이 경로는 실제 추론 runtime을 포함하지만, 컨테이너가 스크립트를 한 번 실행하고 종료된다. 즉 HTTP serving 형태가 아니다.

### 10.3 통합 serving image 계획

다음 단계에서는 `Dockerfile.serve`를 추가하여 `API + Inference` 통합 서빙 컨테이너를 만들 계획이다.

목표 형태:

- 컨테이너 하나가 `uvicorn`으로 상시 실행된다.
- `/v1/jobs` 요청을 받는다.
- 같은 컨테이너 내부 background thread가 `OrchestratedJobExecutor`를 통해 실제 stage를 실행한다.
- `GET /v1/jobs/{job_id}`로 상태와 결과를 polling한다.

이 단계에서는 단일 worker와 단일 replica를 전제로 한다.

이유:

- 현재 job store는 in-memory이다.
- poll은 같은 process의 job state를 읽는다.
- multi-worker나 multi-replica에서는 create와 get이 다른 process로 가서 job을 찾지 못할 수 있다.

따라서 다음 단계의 목표는 서버리스 최종형이 아니라, 실제 E2E를 검증하기 위한 단일 통합 serving runtime이다.

장기적으로는 API/Worker 분리, durable job store, durable artifact store, presigned URL 기반 artifact handoff로 확장해야 한다.

## 11. 문서화 작업

이번 중간 단계에서는 구현뿐 아니라 문서 구조도 정리했다.

루트 `docs/`에는 엔진 간 boundary와 contract를 정리했다.

- `docs/http-contract.md`: 엔진 간 HTTP contract
- `docs/service-engine-boundary.md`: service 책임 경계
- `docs/project-page-storage-boundary.md`: project/page 저장 boundary
- `docs/ui-model-abstract-boundary.md`: UI/model 추상 boundary
- `docs/ui-model-implementation.md`: 현재 구현 기준 UI/model 연결 가이드
- `docs/boundary-open-questions.md`: 아직 남은 결정 사항

`model_engine/docs/`에는 model 내부 구현 기준과 다음 작업 계획을 정리했다.

- `README.md`: model 내부 구현 기준서
- `PROGRESS.md`: 구현 진행 상황
- `TROUBLESHOOTING.md`: OCR/번역 튜닝과 문제 사례
- `SESSION_AND_CREDENTIAL_IMPLEMENTATION.md`: 세션과 provider credential 처리
- `UI_MODEL_CONTRACT_DRAFT.md`: UI/model concrete contract 초안
- `SERVING_PLAN.md`: 통합 serving container 전략
- `NEXT_SESSION_HANDOFF.md`: 다음 세션 작업 인계 문서

문서 정리는 단순 기록 목적이 아니라, 세 엔진이 서로 다른 브랜치와 책임 범위에서 병렬 개발될 때 contract drift를 줄이기 위한 것이다.

## 12. 검증 내역

현재까지 수행한 대표 검증은 다음과 같다.

### 12.1 Unit test

검증한 항목:

- IR patch 적용
- artifact lifecycle
- credential resolution
- orchestrator 순차 실행
- IPC stage 실행
- custom model loading
- job executor lifecycle
- SaaS usage runner

대표 명령:

```bash
python3 -m unittest model_engine.tests.test_job_executor model_engine.tests.test_saas_usage_runner -v
```

### 12.2 Docker API route test

FastAPI route 수준에서 multipart `/v1/jobs` 생성과 poll 응답을 검증했다.

검증한 항목:

- multipart parser 동작
- `metadata + primary_bitmap` 수신
- `upload://primary_bitmap` materialization
- `document_patch` 응답 포함
- CORS preflight
- SaaS auth scope
- idempotency conflict

대표 명령:

```bash
docker compose run --build --rm --no-deps model-engine python3 -m unittest model_engine.tests.test_job_api -v
```

### 12.3 Live smoke

실제 환경에서 확인한 항목:

- OpenAI-compatible endpoint 호출
- OCR sample 실행
- translation sample 실행
- pipeline sample 실행
- service/model bridge health check
- service auth/me pass-through
- usage hold/capture/release 흐름

특히 OpenAI-compatible endpoint는 로컬 `127.0.0.1:1234/v1` 계열 서버를 Docker 내부에서 `host.docker.internal:1234/v1`로 접근하는 구성을 검증했다.

## 13. 현재 한계

현재 구현에는 명확한 한계가 있다.

첫째, `model_engine` API 서버 이미지와 inference 배치 이미지가 아직 통합되지 않았다. 따라서 root compose의 `model-engine`만으로 실제 무거운 OCR/번역/inpaint를 안정적으로 serving하는 단계는 아직 남아 있다.

둘째, job state와 artifact가 아직 in-memory/local file 중심이다. 프로세스 재시작, multi-worker, multi-replica 환경에서는 job polling과 artifact 접근이 깨질 수 있다.

셋째, UI editor와 실제 wiring이 아직 완료되지 않았다. `UI engine`의 backend adapter는 방향이 잡혔지만, 실제 편집 화면에서 `createJob()`, polling, `document_patch` merge reducer가 완전히 연결되어야 한다.

넷째, 번역 LLM 호출 안정화가 더 필요하다. JSON 강제, JSON repair, block id 정합성 검증, OCR warning prompt 반영, glossary 기능이 아직 후속 과제로 남아 있다.

다섯째, OCR 품질은 개선되었지만 자동 평가 도구가 부족하다. 현재는 `needs_review`와 metadata를 남기는 수준이며, debug crop 저장과 분석 스크립트가 추가되면 threshold 튜닝이 더 체계화될 수 있다.

## 14. 향후 계획

다음 단계의 우선순위는 다음과 같다.

1. `Dockerfile.serve`를 추가해 `API + Inference` 통합 serving image를 만든다.
2. root `docker-compose.yml`의 `model-engine`를 serving image로 교체한다.
3. root compose 기준 `service_engine + model_engine` E2E smoke를 수행한다.
4. `multipart(metadata + primary_bitmap)` real inference smoke를 수행한다.
5. `ui_engine`의 `real.ts`를 multipart create와 `documentPatch` 소비 경로로 수정한다.
6. editor placeholder를 제거하고 실제 create/poll/merge wiring을 구현한다.
7. OCR debug artifact 저장과 OCR 분석 스크립트를 추가한다.
8. 번역 LLM 호출 안정화를 진행한다.
9. typesetting/layout stage를 설계하고 구현한다.
10. 장기적으로 durable job store와 durable artifact backend를 도입한다.

## 15. 중간 결론

이번 중간 단계에서 `model_engine`은 단순한 샘플 추론 스크립트 묶음에서, 실제 제품 흐름에 연결될 수 있는 AI job 실행 기반으로 확장되었다.

핵심 성과는 다음과 같다.

- Bitmappery 의미론 기반 `DocumentIR`과 artifact 분리 구조를 마련했다.
- CRAFT, manga-ocr, OpenAI-compatible translation, Vertex translation, nanobanana inpaint를 built-in stage로 연결했다.
- OCR 품질 문제를 분석하고, 세로쓰기 reading order, region merge, hallucination 의심 마킹을 추가했다.
- SaaS 세션과 usage lifecycle을 `service_engine` authority에 맞춰 정리했다.
- `UI -> model` job 입력을 `multipart(metadata + primary_bitmap)`로 구체화했다.
- `model -> UI` 결과를 `document_patch` 중심으로 반환하도록 확장했다.
- 다음 단계인 `API + Inference` 통합 serving container 계획을 문서화했다.

아직 최종 제품 E2E는 완성되지 않았지만, AI pipeline, service 연동, UI contract, 서빙 전략의 핵심 기반은 마련되었다. 다음 단계에서는 이 기반을 실제 루트 compose serving runtime과 UI editor wiring으로 연결하는 것이 가장 중요하다.
