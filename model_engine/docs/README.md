# model_engine

`model_engine`의 구현 명세 문서다. 이 디렉토리의 구현은 항상 이 문서를 기준으로 진행한다.

핵심 전제는 다음과 같다.

- `model_engine` 내부에는 stage별 독립 process가 있다.
- 상위 orchestrator가 stage를 순서대로 호출한다.
- stage 간 데이터 전달의 기준 계약은 Bitmappery 기반 IR이다.
- 큰 산출물은 JSON 본문에 직접 싣지 않고 별도 전달 매체로 분리한다.
- custom model은 입력 포트를 조정 가능한 custom stage process로 삽입한다.

## 1. 이 문서의 역할

`model_engine` 문서는 `docs/` 아래에 모은다.

- `SPEC.md`: 제품/엔진 간 역할과 장기 아키텍처
- `../docs/http-contract.md`: 현재 구현 기준 canonical HTTP contract
- `README.md`(이 문서): `model_engine` 내부 구현 명세
- `TROUBLESHOOTING.md`: OCR/번역 실행 중 관측한 문제와 튜닝 기록
- `SESSION_AND_CREDENTIAL_IMPLEMENTATION.md`: cloud/standalone 기준 세션, usage, provider credential 책임과 구현 포인트
- `UI_MODEL_CONTRACT_DRAFT.md`: `UI engine <-> model engine` concrete contract 최소 합의안 draft
- `INFERENCE_OUTPUT_SPEC.md`: 현재 구현 기준 model 추론 job의 출력 envelope, patch, artifact, stage report 명세
- `SERVING_PLAN.md`: `API + Inference` 통합 서빙 컨테이너 전략과 단계별 구현 계획
- `NEXT_SESSION_HANDOFF.md`: 다음 세션에서 바로 구현을 재개하기 위한 handoff 메모

즉, 앞으로 `model_engine` 구현 판단은 이 README를 직접 기준으로 한다.

## 2. UI 엔진에서 실제 확인한 Bitmappery 사실

아래 내용은 추정이 아니라 `ui_engine/bitmappery` 코드를 읽고 확인한 사실이다.

### 2.1 Bitmappery의 문서 모델은 이미 IR에 가깝다

Bitmappery는 `Document`와 `Layer`를 중심으로 동작한다.

- `Document`는 `id`, `name`, `layers`, `width`, `height`, `selections`를 가진다.
- `Layer`는 위치/크기, `source`, `mask`, `transform`, `filters`, `text`를 가진다.
- `activeSelection`, `invertSelection`은 runtime 전용이며 직렬화 대상이 아니다.

참조:

- `ui_engine/bitmappery/src/definitions/document.ts`
- `Document`: `layers`, `width`, `height`, `selections`, runtime-only selection 필드
- `Layer`: `source`, `mask`, `transform`, `filters`, `text`

이 구조는 `model_engine`이 stage 간에 주고받을 문서 중심 IR의 출발점으로 쓰기에 적합하다.

### 2.2 Bitmappery의 저장 포맷은 "압축된 JSON 문서"다

`DocumentFactory.serialize()`는 문서를 축약 키 기반 JSON으로 바꾼다.

- 문서 레벨 키: `n`, `w`, `h`, `l`, `s`
- 레이어 레벨 키: `n`, `t`, `tr`, `s`, `m`, `x`, `y`, `x2`, `y2`, `w`, `h`, `tx`, `f`, `fl`, `v`

이후 `toBlob()`에서 JSON을 압축하고, `fromBlob()`에서 압축 해제 후 다시 `Document`로 복원한다.

참조:

- `ui_engine/bitmappery/src/factories/document-factory.ts`
- `ui_engine/bitmappery/src/factories/layer-factory.ts`
- `ui_engine/bitmappery/src/workers/compression.worker.ts`

즉 Bitmappery의 실제 전달 단위는 "문서 구조체 -> 직렬화 JSON -> 압축 blob(.bpy)"다.

### 2.3 현재 Bitmappery는 큰 비트맵을 JSON 내부 base64로 저장한다

레이어 직렬화 시 `source`와 `mask`는 `imageToBase64()`를 통해 data URL로 저장된다.

- `source` -> `s`
- `mask` -> `m`

즉 현재 `.bpy`는 작은 메타데이터만 따로 들고 있는 포맷이 아니라, 비트맵도 인라인으로 포함하는 self-contained 포맷이다.

참조:

- `ui_engine/bitmappery/src/factories/layer-factory.ts`
- `ui_engine/bitmappery/src/utils/canvas-util.ts`

이 점은 `model_engine` 설계에서 매우 중요하다. Bitmappery의 개념 모델은 재사용하되, 내부 stage 간 전달은 `.bpy` 그대로 복제하면 안 된다.

### 2.4 Bitmappery 내부 렌더링도 이미 "단계적 처리"로 구현돼 있다

`renderEffectsForLayer()`는 레이어 렌더링을 순차 단계로 처리한다.

1. 텍스트면 텍스트 비트맵 생성 또는 캐시 재사용
2. 필터 적용
3. 마스크 적용
4. 캐시 갱신 및 렌더러 업데이트

필터 단계는 `FilterWorker`를 사용한 별도 worker에서 처리된다. WASM 모드가 아니면 job마다 worker를 생성해 병렬화한다.

참조:

- `ui_engine/bitmappery/src/services/render-service.ts`

즉 "독립 process + orchestrator 순차 호출"이라는 방향은 Bitmappery 코드 구조와도 잘 맞는다.

### 2.5 현재 towa-app에는 아직 Bitmappery 임베드가 없다

현재 `towa-app`의 상세 편집 화면은 placeholder다. Bitmappery가 실제로 앱에 통합된 상태는 아니다.

참조:

- `ui_engine/towa-app/src/views/DetailEditorTab.vue`

따라서 `model_engine`은 아직 `towa-app`의 별도 포맷이나 wrapper contract를 기대하면 안 된다. 현재 기준 참조 대상은 `bitmappery` 자체의 문서 모델이다.

## 3. model_engine 내부 데이터 계약

`model_engine`은 Bitmappery의 개념 모델을 기반으로 하지만, 내부 전달 포맷은 `.bpy`와 다르게 나눈다.

### 3.1 Canonical IR

stage 간 canonical IR은 `Bitmappery Document IR`이다.

이 IR은 아래 두 층으로 나뉜다.

1. `document_ir`
- 문서 구조, 레이어 구조, 텍스트, 변형, 필터, selection, stage 메타데이터

2. `artifact_refs`
- 큰 이미지, 마스크, OCR raw, inpaint result, intermediate raster 등의 별도 참조

즉 stage 간 전달의 기준은 "Bitmappery 의미론을 따르는 문서 JSON + 외부 artifact 참조"다.

### 3.2 왜 `.bpy`를 내부 IR로 그대로 쓰지 않는가

`.bpy`는 UI 저장 포맷으로는 적합하지만, `model_engine` stage 간 교환 포맷으로는 비효율적이다.

- 큰 비트맵이 base64로 인라인된다.
- stage 하나가 작은 변경만 해도 문서 전체를 다시 압축해야 한다.
- 중간 산출물을 부분 재사용하기 어렵다.
- 프로세스 간 메모리/IPC 비용이 커진다.

따라서 `model_engine`은 Bitmappery의 `Document/Layer` 의미는 유지하되, 내부 실행에서는 artifact externalization을 기본 규칙으로 삼는다.

### 3.3 Canonical IR의 최소 형태

```json
{
  "document": {
    "id": "doc_001",
    "name": "page-001",
    "width": 1600,
    "height": 2400,
    "layers": [
      {
        "id": "layer_clean",
        "name": "Clean Plate",
        "type": "graphic",
        "left": 0,
        "top": 0,
        "width": 1600,
        "height": 2400,
        "visible": true,
        "transparent": true,
        "transform": {
          "scale": 1,
          "rotation": 0,
          "mirrorX": false,
          "mirrorY": false
        },
        "filters": {},
        "text": {},
        "source_ref": "artifact://clean-plate",
        "mask_ref": "artifact://bubble-mask"
      }
    ],
    "selections": {},
    "activeSelection": [],
    "invertSelection": false
  },
  "artifacts": {
    "artifact://clean-plate": {
      "kind": "bitmap",
      "media_type": "image/png",
      "width": 1600,
      "height": 2400,
      "uri": "file:///tmp/towa/clean-plate.png"
    }
  },
  "stage_meta": {
    "pipeline_id": "pipe_001",
    "stage_history": []
  }
}
```

주의:

- Bitmappery 원본의 `source`/`mask`는 `HTMLCanvasElement`지만, `model_engine` IR에서는 직접 객체를 넘기지 않는다.
- 내부 IR에서는 `source_ref`/`mask_ref`로 치환한다.
- runtime-only selection 필드는 필요 시 유지할 수 있지만, persistence와 IPC에서는 최소화한다.

## 4. Stage Process 규칙

### 4.1 모든 stage는 독립 process다

각 stage는 독립 실행 단위다.

- OCR
- 말풍선/텍스트 영역 감지
- 지우기/클린플레이트
- 번역
- 식자 배치
- 후처리
- custom model stage

각 stage는 orchestrator에 의해 호출된다.

### 4.2 Stage 입출력 규칙

모든 stage는 아래 계약을 따른다.

- 입력: `document_ir`, 필요한 `artifact_refs`, `stage_config`
- 출력: 변경된 `document_ir` patch 또는 새 문서 스냅샷, 새 `artifact_refs`, `stage_report`

stage는 원칙적으로 아래를 지켜야 한다.

- 이전 stage의 artifact를 in-place 파괴하지 않는다.
- 새 산출물이 생기면 새 artifact ref를 발급한다.
- 문서 구조 변경은 IR patch로 표현 가능해야 한다.
- 실패 시 부분 산출물과 오류 메타데이터를 명확히 돌려준다.

### 4.3 Orchestrator 책임

orchestrator는 아래를 담당한다.

- stage 순서 결정
- 입력 ref 해석
- stage process 실행
- 출력 IR 검증
- artifact lifecycle 관리
- SaaS 모드에서 hold/capture/release와 연결
- 실패 시 rollback 또는 실패 상태 봉인

즉 stage는 "순수 작업 단위", orchestrator는 "실행과 연결의 책임자"다.

## 5. Bitmappery 기반 IR 매핑 규칙

### 5.1 유지할 것

아래 개념은 Bitmappery와 최대한 같은 의미를 유지한다.

- `Document`
- `Layer`
- `transform`
- `filters`
- `text`
- `selection`
- 레이어 좌표계와 문서 좌표계

이렇게 해야 결과물을 UI의 Bitmappery 편집기로 무리 없이 넘길 수 있다.

### 5.2 바꿀 것

아래는 `model_engine`용으로 변경한다.

- `source`, `mask`: `HTMLCanvasElement` 대신 artifact ref
- `.bpy` 축약 키: 내부 실행에서는 사람이 읽을 수 있는 명시 키 사용
- 전체 문서 blob 저장: stage 간 전달에서는 patch + artifact ref 중심으로 변경

### 5.3 결과 전달 원칙

모델 추론 결과는 가능하면 아래 둘 중 하나로 귀결되어야 한다.

1. Bitmappery 문서에 새 레이어를 추가
2. 기존 레이어의 `source_ref`, `mask_ref`, `text`, `transform`, `filters`를 갱신

즉 추론 결과도 결국 Bitmappery 문서 계층 위에 투영되어야 한다.

## 6. 큰 산출물 전달 매체

큰 산출물은 IR 본문에 직접 넣지 않는다.

허용되는 전달 매체 예:

- 로컬 임시 파일 경로
- object storage URI
- shared blob store key
- 메모리 맵 또는 프로세스 공유 버퍼를 감싼 핸들

최소 요구사항:

- `uri`
- `media_type`
- `width`, `height` 또는 payload 크기
- 무결성 확인용 checksum 또는 version

추론 단계가 image-heavy 하므로, 이 규칙은 선택이 아니라 기본값이다.

## 7. Custom Model Stage 규칙

custom model은 독립 stage로 삽입한다.

custom stage는 입력 포트를 조정할 수 있다.

예:

- 전체 페이지 raster
- 특정 레이어 raster
- bubble mask
- OCR text blocks
- translated text blocks
- selection polygon
- prompt / style config

하지만 출력은 반드시 표준화해야 한다.

- 문서 변경은 Bitmappery 기반 IR patch
- 큰 결과물은 artifact ref
- stage report는 공통 메타데이터 형식

즉 custom 입력은 유연하게, 출력 계약은 고정한다.

추가 규칙:

- custom model의 등록 방식은 `CUSTOM_MODELS.md`를 따른다.
- 현재 지원하는 custom adapter 타입은 `python_callable`, `http_api`, `container_worker`다.
- custom model은 manifest JSON으로 registry에 로드된다.
- built-in 모델과 custom 모델은 모두 `StageManifest + ModelAdapter` 계약으로 합류한다.
- OCR capability의 공통 규격은 `OCR_CAPABILITY.md`를 source of truth로 본다.
- capability와 runtime은 분리해서 본다.
- custom model은 장기적으로 같은 Python 프로세스 import보다 격리 runtime 실행을 기본값으로 한다.
- 같은 capability를 만족해도 runtime family가 다르면 별도 worker/image로 분리하는 쪽을 우선한다.

## 8. Stage I/O Schema

모든 stage process는 아래 입력 스키마를 받아야 한다.

```json
{
  "schema_version": "v1",
  "pipeline_id": "pipe_001",
  "job_id": "job_001",
  "stage_name": "ocr",
  "stage_run_id": "stage_run_001",
  "document": {},
  "artifacts": {},
  "patches_applied": [],
  "stage_config": {},
  "credential_bindings": {
    "primary_provider": {
      "provider": "nanobanana",
      "credential_source": "platform_managed",
      "credential_id": "platform/nanobanana/default",
      "credential_version": "2026-03-27",
      "billing_mode": "platform_credit"
    }
  },
  "runtime_context": {
    "mode": "local",
    "workspace_uri": "file:///tmp/towa/run-001",
    "requested_by": "user_or_session_ref"
  }
}
```

필수 규칙:

- `document`는 항상 canonical Bitmappery-based IR이어야 한다.
- `artifacts`는 현재 시점에서 참조 가능한 artifact registry snapshot이어야 한다.
- `patches_applied`는 현재 stage 이전까지 누적된 patch 로그다.
- `stage_config`는 stage별 자유 입력이 가능하지만 JSON-serializable 이어야 한다.
- `credential_bindings`는 stage가 사용할 credential의 메타데이터다.
- raw secret은 `StageRequest` JSON에 넣지 않는다.
- actual secret은 orchestrator가 stage process 실행 시 env 또는 동등한 secure injection 경로로 전달한다.
- `runtime_context`는 실행 환경 정보이며, 문서 의미론을 바꾸는 용도로 쓰면 안 된다.

모든 stage process는 아래 출력 스키마를 돌려야 한다.

```json
{
  "schema_version": "v1",
  "stage_name": "ocr",
  "stage_run_id": "stage_run_001",
  "status": "succeeded",
  "patches": [],
  "artifacts": {},
  "stage_report": {}
}
```

출력 규칙:

- 성공 시 `patches`는 빈 배열일 수 있지만, `stage_report`는 비어 있으면 안 된다.
- 실패 시 partial artifact가 생겼더라도 `stage_report.status`와 artifact 상태가 함께 반환되어야 한다.
- stage는 전체 문서 스냅샷을 재작성하기보다 가능한 한 patch 기반 출력을 우선한다.
- 전체 스냅샷 재작성은 patch로 표현이 과도하게 복잡한 경우에만 허용한다.

## 9. IR Patch Schema

patch 포맷은 고정한다. stage 간 호환을 위해 자유형 patch는 허용하지 않는다.

기본 형태:

```json
{
  "op": "replace_source_ref",
  "target": {
    "document_id": "doc_001",
    "layer_id": "layer_clean"
  },
  "payload": {
    "source_ref": "artifact://clean-plate-v2"
  }
}
```

초기 구현에서 허용하는 `op`는 아래로 제한한다.

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

연산별 규칙:

- `add_layer`: Bitmappery `Layer` 의미론을 따르는 완전한 layer payload를 요구한다.
- `update_layer_props`: 위치, 크기, visible, transparent 같은 경량 속성만 갱신한다.
- `replace_source_ref`: 새 source artifact ref만 교체한다.
- `replace_mask_ref`: 새 mask artifact ref만 교체한다.
- `set_layer_text`: text stage가 생산한 텍스트 payload를 반영한다.
- `set_document_selection`: selection 관련 상태를 문서에 반영한다.
- `append_text_blocks`: OCR/번역 결과를 stage 메타 또는 별도 overlay layer 준비 데이터로 추가한다.
- `replace_text_blocks`: OCR stage가 현재 문서의 canonical text block 집합을 새 결과로 교체한다.
- `set_stage_meta`: `document.stage_meta` 또는 pipeline 메타를 갱신한다.

patch 공통 규칙:

- patch는 적용 순서에 의미가 있으므로 orchestrator는 반환 순서를 보존한다.
- patch 적용 실패는 해당 stage 실패로 간주한다.
- 하나의 patch는 하나의 명확한 의미만 가져야 한다.
- stage가 같은 layer에 대해 여러 속성을 바꿔야 하면 작은 patch 여러 개보다 의미 있는 묶음 patch를 우선한다.

## 10. Artifact Registry Interface

artifact registry는 큰 산출물의 생명주기를 책임진다.

최소 인터페이스:

```json
{
  "artifact_ref": "artifact://clean-plate-v2",
  "kind": "bitmap",
  "media_type": "image/png",
  "uri": "file:///tmp/towa/run-001/clean-plate-v2.png",
  "width": 1600,
  "height": 2400,
  "byte_size": 523001,
  "checksum": "sha256:...",
  "version": 2,
  "producer_stage": "clean_plate",
  "status": "ready",
  "created_at": "2026-03-26T10:00:00Z",
  "expires_at": null
}
```

registry가 지원해야 하는 동작:

- `register_artifact`
- `resolve_artifact`
- `verify_artifact`
- `mark_artifact_failed`
- `release_artifact`
- `gc_artifacts`

artifact lifecycle 규칙:

- 새 산출물은 항상 새 `artifact_ref`로 등록한다.
- 같은 논리 산출물의 재생성은 `version` 증가로 표현한다.
- checksum mismatch는 artifact 손상으로 간주하고 해당 stage를 실패 처리한다.
- stage 실패 후 생성된 partial artifact는 기본적으로 `failed` 상태로 등록한다.
- orchestrator가 실패 봉인을 끝내면 `failed` artifact는 GC 대상이 된다.
- 성공 경로에서 더 이상 참조되지 않는 artifact는 pipeline 종료 후 GC 후보가 된다.
- rollback이 발생하면 rollback 이후 도달 불가능한 artifact는 `orphaned`로 표시하고 정리한다.

로컬 파일 저장 규칙:

- local artifact는 transaction 단위 경로 아래 저장한다.
- 기본 경로 형식:
  - `{workspace}/transactions/{pipeline_id}/{stage_name}/{stage_run_id}/`
- stage는 이 경로 아래에서만 산출물을 만든다.
- orchestrator는 transaction 종료 후 성공/실패 상태에 따라 정리 또는 보존을 결정한다.

즉 local `file://` 저장은 허용하지만, transaction 범위를 벗어난 임의 경로 쓰기는 금지한다.

전달 매체 기본 우선순위:

- local 기본: `file://` 임시 파일
- SaaS 기본: object storage URI
- 고성능 옵션: shared memory handle 또는 동등한 zero-copy 수단

첫 구현은 이 우선순위를 바꾸지 않는다.

## 11. Stage Report Schema

모든 stage는 아래 공통 report를 생성해야 한다.

```json
{
  "stage_name": "ocr",
  "stage_run_id": "stage_run_001",
  "status": "succeeded",
  "input_refs": [
    "artifact://page-source"
  ],
  "output_refs": [
    "artifact://ocr-json"
  ],
  "warnings": [],
  "metrics": {
    "latency_ms": 1200
  },
  "provider": {
    "name": "nanobanana",
    "credential_source": "platform_managed",
    "credential_id": "platform/nanobanana/default",
    "credential_version": "2026-03-27",
    "billing_mode": "platform_credit"
  },
  "error_code": null,
  "error_message": null,
  "started_at": "2026-03-26T10:00:00Z",
  "finished_at": "2026-03-26T10:00:01Z"
}
```

필수 필드:

- `stage_name`
- `stage_run_id`
- `status`
- `input_refs`
- `output_refs`
- `warnings`
- `metrics`
- `provider`
- `error_code`
- `error_message`
- `started_at`
- `finished_at`

`status` 허용값:

- `succeeded`
- `failed`
- `partial`
- `skipped`

규칙:

- `partial`은 부분 산출물은 남았지만 다음 stage 진행 가능 여부가 orchestrator 판단에 달린 상태다.
- `skipped`는 조건부 stage 미실행을 의미하며 오류가 아니다.
- `warnings`는 사람이 읽을 수 있는 문자열 또는 구조화 warning object를 허용한다.
- `metrics`는 stage 자유 확장을 허용하되, 공통 지표로 `latency_ms`는 권장한다.
- `provider`는 raw secret이 아니라 provider/credential source/version/billing metadata만 담는다.
- 실패 시 `error_code`는 machine-readable 해야 하고, `error_message`는 운영/디버깅용 사람이 읽을 수 있어야 한다.

외부 provider stage 추가 규칙:

- provider가 멈추거나 timeout/abort 상태로 끝나면 기본적으로 `failed`로 처리한다.
- 이 경우 마지막 입력 snapshot, task snapshot, 이미 생성된 output artifact는 transaction 경로 아래에 남길 수 있다.
- 즉 "조용한 partial 성공"보다 "명시적 실패 + snapshot 보존"이 기본 규칙이다.

## 12. Selection 및 Runtime Field 구분

selection 관련 필드는 아래 세 층으로 나눈다.

1. UI round-trip selection
- UI에 다시 돌려줄 때 보존해야 하는 selection
- 문서 IR에 포함 가능

2. stage working selection
- 특정 stage 내부 알고리즘을 위해 잠시 쓰는 selection
- 기본적으로 stage 종료 후 patch 또는 artifact로 승격되지 않으면 폐기

3. ephemeral runtime cache
- 성능 최적화를 위한 마스크 캐시, crop box 캐시, 좌표 인덱스 등
- 문서 IR, patch, artifact registry에 올리지 않는다

규칙:

- stage working selection을 UI round-trip selection과 혼용하지 않는다.
- UI에 노출될 selection만 문서에 남긴다.
- stage 내부 임시 selection은 가능하면 artifact 또는 runtime context에 둔다.

## 13. Credential 및 Key Management

이 섹션은 `model_engine`의 provider credential 운영 규칙을 정의한다.

핵심 원칙:

- secret authority와 billing authority를 분리한다.
- credential은 `model_engine`이 직접 사용하지만, credit 정산 authority는 `service_engine`에 남긴다.
- raw secret은 artifact, patch, stage_report, log, README 예시 payload에 절대 남기지 않는다.
- stage는 secret 자체보다 `credential_binding`을 기준으로 동작한다.

### 13.1 Credential Source

`model_engine`이 사용할 수 있는 credential source는 아래 다섯 가지로 제한한다.

1. `platform_managed`
- SaaS용 platform provider key
- 배포 환경의 secret store 또는 env를 통해 `model_engine`에 주입
- billed operation과 연결 가능

2. `user_personal_persisted`
- local 사용자가 저장해 둔 개인 API key
- local credential store에서 읽음
- 기본적으로 credit과 무관한 `user_direct` 실행

3. `user_personal_session`
- local 또는 cloud 세션 중 사용자가 일시적으로 제공한 개인 API key
- 메모리 전용
- job 또는 session 종료 시 폐기

4. `worker_identity`
- API key가 아니라 cloud worker identity, IAM role, workload identity 같은 간접 인증
- object storage 접근이나 internal service 접근용

5. `none`
- local model, 규칙 기반 stage, CPU/GPU 자체 추론처럼 외부 provider credential이 불필요한 경우

이 외의 source는 v1에서 허용하지 않는다.

### 13.2 Stage별 기본 Credential Source

v1 기준 기본 source 정책은 아래와 같다.

- `text_detection`
  - 기본: `none`
  - CRAFT/local model 기준

- `ocr`
  - 기본: `none`
  - 외부 OCR provider를 도입하면 그때 `user_personal_*` 또는 `platform_managed`를 명시적으로 추가

- `mask_or_erase_planning`
  - 기본: `none`

- `inpaint`
  - local 기본: `user_personal_persisted` 또는 `user_personal_session`
  - SaaS 기본: `platform_managed`
  - 현재 나노바나나 API를 사용하는 대표 external-provider stage

- `translation`
  - local 기본: `user_personal_persisted` 또는 `user_personal_session`
  - SaaS 기본: `platform_managed`
  - local model translator를 쓰면 `none`

- `typesetting`
  - 기본: `none`
  - 외부 layout/model provider를 붙일 때만 credential 사용

- `postprocess`
  - 기본: `none`

즉, stage별 credential source는 "기본값은 문서에 고정, override는 request에서 명시" 원칙을 따른다.

### 13.3 Storage Location

credential 저장 위치는 source별로 구분한다.

#### local persisted credential

기본 위치:

- `~/.config/towa/model_engine/credentials.json`

override:

- `TOWA_CREDENTIALS_FILE`

규칙:

- 파일 권한은 사용자 전용 읽기/쓰기만 허용한다.
- repo 내부 경로에는 저장하지 않는다.
- artifact/workspace 경로 아래에는 저장하지 않는다.
- 이 파일에는 사용자 개인 key만 저장한다.
- platform key는 local persisted credential 파일에 저장하지 않는다.

권장 형식:

```json
{
  "providers": {
    "nanobanana": {
      "api_key": "secret",
      "updated_at": "2026-03-27T00:00:00Z"
    }
  }
}
```

단, 실제 런타임과 문서/로그에는 raw secret을 다시 노출하지 않는다.

#### platform managed credential

platform key는 `model_engine` 배포 환경의 secret store 또는 env에서만 공급한다.

예:

- `TOWA_PLATFORM_PROVIDER_NANOBANANA_API_KEY`
- `TOWA_PLATFORM_PROVIDER_OPENAI_API_KEY`

규칙:

- `service_engine` DB에 저장하지 않는다.
- `artifact registry`에 저장하지 않는다.
- `stage_report`에 raw value를 남기지 않는다.
- 가능하면 env 직접 참조보다 secret manager adapter를 우선한다.

#### session credential

`user_personal_session`은 디스크 저장 없이 메모리에서만 유지한다.

규칙:

- session exchange 또는 direct local input으로 받은 뒤 `model_engine` 메모리에만 둔다.
- job 종료 또는 session 만료 시 폐기한다.
- crash dump나 debug log에 남기지 않는다.

### 13.4 Credential Binding Contract

orchestrator는 stage 실행 전에 raw secret을 바로 stage JSON에 싣지 않고 `credential_binding`으로 정규화한다.

예:

```json
{
  "provider": "nanobanana",
  "credential_source": "platform_managed",
  "credential_id": "platform/nanobanana/default",
  "credential_version": "2026-03-27",
  "billing_mode": "platform_credit"
}
```

`credential_binding` 필수 필드:

- `provider`
- `credential_source`
- `credential_id`
- `credential_version`
- `billing_mode`

규칙:

- `credential_id`는 logical identifier이지 secret value가 아니다.
- `credential_version`은 rotation 추적용이다.
- 같은 pipeline 안에서는 같은 binding snapshot을 유지한다.
- stage는 binding metadata를 보고 어떤 provider adapter를 쓸지 결정한다.

### 13.5 Secret Injection

실제 secret 전달은 orchestrator가 담당한다.

v1 규칙:

- stage IPC JSON에는 secret 금지
- subprocess stage에는 env injection 사용
- 향후 remote worker나 queue transport에서는 secure side-channel 또는 secret fetch token 사용

subprocess env 예시:

- `TOWA_STAGE_PROVIDER_NAME=nanobanana`
- `TOWA_STAGE_CREDENTIAL_SOURCE=platform_managed`
- `TOWA_STAGE_CREDENTIAL_ID=platform/nanobanana/default`
- `TOWA_STAGE_CREDENTIAL_VERSION=2026-03-27`
- `TOWA_STAGE_SECRET_API_KEY=<raw secret>`

규칙:

- env name은 stage 공통 규약을 따른다.
- secret env는 child process scope에만 주입한다.
- parent orchestrator는 필요 이상 오래 secret을 보관하지 않는다.
- stage process는 secret env를 다시 stdout/stderr로 출력하면 안 된다.

### 13.6 Rotation Policy

rotation은 source별로 다르게 처리한다.

#### platform managed

- 새 job 시작 시 최신 active version을 resolve한다.
- 실행 중인 pipeline은 시작 시점에 resolve한 version을 고정 사용한다.
- 즉, rotation은 기본적으로 new-job boundary에서 반영한다.
- provider auth failure가 발생하면 orchestrator는 idempotent stage에 한해 1회 fresh resolve 후 재시도할 수 있다.

#### local persisted

- credential 파일 변경은 새 job부터 반영한다.
- 현재 실행 중인 pipeline에는 자동 반영하지 않는다.

#### session credential

- session credential은 session 또는 job lifetime과 함께 폐기된다.
- rotation 개념보다 재입력이 우선이다.

### 13.7 Billing Mode와 우선순위

external provider stage는 아래 billing mode 중 하나를 가진다.

- `platform_credit`
- `user_direct`
- `none`

우선순위:

1. stage request의 명시 override
2. pipeline/job level의 명시 override
3. mode 기본값
4. fallback

기본값:

- local mode: `user_direct` 우선
- SaaS mode: `platform_credit` 우선

fallback 규칙:

- local에서 personal key가 없고 platform session도 없으면 external-provider stage는 실패
- SaaS에서 platform credential이 없으면 external-provider stage는 실패
- `none` stage는 credential resolution을 시도하지 않는다

즉, local은 실수로 credit을 태우지 않도록 personal key 우선, SaaS는 플랫폼 제품 경험을 위해 credit 우선으로 둔다.

### 13.8 Stage Report 및 Logging 규칙

`stage_report.provider`에는 아래만 남긴다.

- `name`
- `credential_source`
- `credential_id`
- `credential_version`
- `billing_mode`

남기면 안 되는 것:

- raw API key
- bearer token
- provider secret 원문
- secret hash의 원문 재구성 가능 값

logging 규칙:

- credential load 성공/실패는 provider/source/id 수준까지만 기록
- auth 실패 로그에도 secret literal 금지
- traceback에 secret이 섞일 가능성이 있는 예외 문자열은 redaction 후 기록

### 13.9 현재 프로젝트 기준 결론

현재 프로젝트 기준으로는 아래를 고정한다.

- `service_engine`은 credit authority이고 provider secret authority가 아니다.
- `model_engine`은 provider credential을 직접 사용하지만, raw secret을 IR/patch/artifact에 넣지 않는다.
- local persisted credential 기본 경로는 `~/.config/towa/model_engine/credentials.json`이다.
- subprocess IPC에서는 secret을 JSON이 아니라 child env로 주입한다.
- pipeline은 job 시작 시 resolve한 credential binding snapshot을 고정 사용한다.
- `inpaint` 같은 external-provider stage는 local에서 `user_direct`, SaaS에서 `platform_credit`를 기본값으로 한다.

## 14. Model Merge Strategy

이 섹션은 다양한 built-in model과 custom model이 `model_engine`에 안정적으로 병합되기 위한 규칙을 정의한다.

핵심 원칙:

- pipeline은 model이 아니라 `stage capability` 기준으로 정의한다.
- model 다양성은 stage 뒤의 adapter와 manifest에서 흡수한다.
- custom model은 입력 포트는 유연하게 둘 수 있지만, 출력 계약은 built-in model과 동일해야 한다.
- orchestrator는 개별 모델 구현을 알지 않고, `registry + selector + manifest`를 통해 모델을 선택한다.

### 14.1 Stage Capability 우선

`text_detection`, `ocr`, `inpaint`, `translation`, `typesetting`, `postprocess`는 모델 이름이 아니라 capability 이름이다.

예:

- `text_detection`
  - CRAFT
  - YOLO-text
  - custom detector

- `inpaint`
  - 나노바나나 API
  - local diffusion model
  - custom remote service

즉 파이프라인은 stage graph를 유지하고, 개별 모델은 같은 capability를 만족하는 구현체로만 취급한다.

### 14.2 Model Manifest

모든 모델 구현체는 `StageManifest`를 가져야 한다.

최소 필드:

- `model_id`
- `adapter_id`
- `stage_kind`
- `input_contract_version`
- `output_contract_version`
- `required_artifact_kinds`
- `produced_artifact_kinds`
- `supported_modes`
- `allowed_credential_sources`
- `billing_modes`
- `resource_profile`
- `custom_model`
- `priority`

규칙:

- manifest 없이는 registry에 등록할 수 없다.
- 같은 `stage_kind`에 여러 manifest가 존재할 수 있다.
- selector는 request와 manifest를 비교해 실행 가능한 후보만 고른다.

### 14.3 Adapter Interface

모델 구현체는 직접 orchestrator에 연결되지 않고 adapter를 통해 연결된다.

adapter 책임:

- stage request를 해당 모델 입력 포맷으로 변환
- artifact를 resolve해 모델 입력 준비
- 모델 실행
- 결과를 canonical patch/artifact/report로 변환

즉 adapter는 provider/model-specific translation 계층이다.

### 14.4 Registry와 Selector

registry는 등록과 조회를 담당하고, selector는 실제 실행 후보를 고른다.

selector는 최소한 아래를 기준으로 필터링해야 한다.

- `stage_kind`
- `input_contract_version`
- `output_contract_version`
- `runtime mode`
- `required_artifact_kinds`
- `allowed_credential_sources`
- `preferred_model_id` override

기본 선택 규칙:

1. 명시된 `preferred_model_id`
2. 호환되는 후보 중 `priority`가 가장 높은 것
3. 동률이면 built-in보다 custom을 우선하지 않고, manifest priority로만 결정

즉 custom model은 “자동 특혜”가 아니라 “명시 선택 또는 높은 priority”로만 선택된다.

### 14.5 출력 계약 고정

어떤 모델이든 출력은 아래 계약을 벗어나면 안 된다.

- patch
- artifact ref
- stage_report

모델별 자유 출력은 금지한다.

권장:

- 새로운 의미론이 필요하면 patch op를 함부로 늘리지 말고 artifact kind를 먼저 확장한다.
- patch op는 닫고, artifact type은 열어둔다.

### 14.6 Contract Test

모든 adapter는 모델별 테스트보다 먼저 capability contract test를 통과해야 한다.

예:

- `text_detection contract test`
- `inpaint contract test`
- `translation contract test`

즉 “CRAFT 테스트”보다 “text_detection contract test”가 우선이다.

### 14.7 현재 프로젝트 기준 결론

현재 프로젝트 기준으로는 아래를 고정한다.

- stage는 capability 단위로 유지한다.
- 모델 구현체는 `manifest + adapter`로만 합류한다.
- selector는 request compatibility로만 모델을 고른다.
- custom model도 built-in과 같은 patch/artifact/report 계약을 지켜야 한다.
- 향후 실제 CRAFT, 나노바나나, 사용자 custom model은 모두 같은 registry 계층에 등록한다.

### 14.8 Runtime Isolation Strategy

custom model이 늘어날수록 가장 큰 문제는 capability contract보다 runtime 충돌이다.

대표 사례:

- 서로 다른 `torch` 버전
- 서로 다른 `transformers` 버전
- CUDA / cuDNN ABI 차이
- Python minor version 차이
- OpenCV / NumPy / system package 충돌

따라서 앞으로는 아래를 기본 원칙으로 삼는다.

- pipeline은 capability 기준으로 유지한다.
- 모델은 manifest로 고르되, 실제 실행은 가능하면 격리된 runtime worker에서 수행한다.
- stage 경계는 `StageRequest/StageResponse + artifact`로만 넘긴다.
- in-memory object 공유를 전제로 여러 모델을 한 프로세스에 함께 올리지 않는다.

권장 backend 계층:

- `inprocess`
  - built-in의 가벼운 pure-Python 또는 이미 검증된 최소 모델만 허용
- `http_api`
  - 가장 보수적이고 안전한 기본 선택지
- `subprocess_ipc`
  - 같은 머신의 별도 Python 환경 또는 별도 launcher에서 실행
- `container_worker`
  - GPU/CUDA/torch 계열 충돌을 가장 강하게 분리하는 방식
  - 현재 baseline adapter가 구현되어 있다.

권장 runtime family 예:

- `craft-py310-cpu`
- `manga-ocr-py310-cpu`
- `gemini-http-light`
- `custom-translation-cu124`
- `diffusion-cu121`

정책:

- custom model은 `shared-runtime-safe`가 명확히 검증되지 않으면 같은 프로세스 실행을 기본값으로 잡지 않는다.
- 모델마다 이미지 1개씩 만드는 대신, ABI와 의존성이 같은 것끼리 runtime family를 묶는다.
- "모델을 플러그인으로 import"하는 것보다 "runtime worker를 호출"하는 쪽을 기본 설계로 본다.
- 현재 `container_worker` baseline은 `docker run --rm -i + stdin/stdout JSON IPC + workspace/cache mount` 방식으로 동작한다.

### 14.9 Stage Migration Policy

모든 stage를 무조건 같은 방식으로 분리하지는 않는다. 기준은 "모델 의존성 충돌 가능성"과 "실행 성격"이다.

worker 또는 remote backend로 우선 보내는 대상:

- `text_detection`
  - CRAFT 같은 모델 의존성이 무겁고 Python/runtime 제약이 크다.
  - 장기 기본값은 `container_worker`.
- `ocr`
  - `manga-ocr`, PaddleOCR 등은 torch/transformers 충돌 가능성이 있다.
  - 장기 기본값은 `container_worker`.
- `translation`
  - 외부 API 계열은 `http_api`, 로컬 대형 모델은 `container_worker`.
  - 예: Vertex/OpenAI-compatible proxy는 `http_api` 계열, 로컬 대형 모델은 `container_worker`.
- `inpaint`
  - 외부 API 계열은 `http_api`, 로컬 diffusion 계열은 `container_worker`.

in-process로 남겨도 되는 대상:

- `mask_or_erase_planning`
  - rule-based stage이고 dependency 충돌 위험이 작다.
  - 당분간 `inprocess` 유지.

조건부 대상:

- `typesetting`
  - 초기 pure-Python/layout 단계는 `inprocess` 가능
  - 폰트/graphics/runtime stack이 무거워지면 `container_worker`로 이동
- `postprocess`
  - 단순 후처리는 `inprocess`
  - upscaler/diffusion 같은 모델이 붙으면 `container_worker`

즉 장기 방향은 "모든 모델 stage는 worker 또는 remote backend로, 순수 계획/조합 stage만 in-process로" 가져간다.

## 15. SaaS / Local 공통 규칙

SaaS와 local의 차이는 인증/정산 레이어에만 있다.

- local: 서비스 엔진 없이 실행 가능
- SaaS: 작업 전 hold, 성공 시 capture, 실패 시 release

하지만 내부 stage graph와 IR 계약은 두 모드에서 동일해야 한다.

즉 실행 모드가 달라도 아래는 바뀌지 않는다.

- orchestrator 호출 방식
- stage 입출력
- Bitmappery 기반 IR
- artifact ref 구조

## 16. 현재 결론

코드 확인 결과, Bitmappery는 이미 다음 구조를 갖고 있다.

- 문서 중심 모델
- 레이어 중심 직렬화
- 압축 blob 저장 포맷
- 단계적 렌더 파이프라인
- worker 기반 비동기 처리

따라서 `model_engine`은 이 개념을 그대로 계승하되, 내부 실행에서는 아래로 구체화한다.

- Bitmappery의 `Document/Layer` 의미론을 canonical IR로 채택
- `.bpy` 저장 포맷은 UI 저장/호환용으로만 취급
- stage 간 전달은 `document_ir + artifact_refs`
- 큰 비트맵은 외부 전달 매체로 분리
- custom model도 같은 출력 계약을 따름

이 문서에 반하는 구현은 도입하지 않는다.

## 17. Container Strategy

컨테이너는 역할별로 분리한다.

- `Dockerfile`
  - 기본 개발/테스트 이미지
  - 공통 계약층, orchestrator, IPC, adapter 테스트를 빠르게 재현하는 용도
  - 무거운 로컬 추론 의존성은 넣지 않는다

- `Dockerfile.inference`
  - 로컬 추론 이미지
  - CRAFT 같은 built-in 모델 의존성을 담는다
  - 이후 OCR/local model/GPU 런타임도 이 계열에서 확장한다
  - 단, 모든 custom model을 여기에 계속 합치지 않고 runtime family별 이미지로 분화하는 것을 우선한다

- `docker-compose.runtime.yml`
  - runtime family별 worker image를 정리하는 초안 파일
  - orchestrator와 worker 이미지를 한꺼번에 관리할 때 기준으로 사용한다

의존성 파일도 같은 원칙으로 분리한다.

- `requirements-base.txt`
  - 공통 런타임과 lightweight adapter용

- `requirements-craft.txt`
  - base 위에 CRAFT text detection 의존성을 추가

즉 기본 개발 환경은 가볍게 유지하고, 실제 로컬 추론은 별도 inference 이미지로 확장한다.

장기 방향:

- CPU/GPU/torch/CUDA 조합이 다른 모델은 별도 runtime image로 분리한다.
- custom model 기본 통합 방식은 "같은 이미지에 계속 의존성을 추가"가 아니라 "맞는 runtime family에 배치"다.

현재 pipeline sample translation backend:

- `openai_compatible`
  - 기본 방식
  - LM Studio, Ollama OpenAI-compatible endpoint, custom proxy를 대상으로 한다.
- `vertex`
  - Vertex Gemini 번역 adapter를 명시 선택할 때 사용한다.

## 18. Built-in Text Detection

첫 built-in `text_detection` 구현체는 CRAFT로 고정한다.

- model id: `builtin.craft.text_detection`
- stage capability: `text_detection`
- 출력 artifact kind: `text_regions`
- artifact media type: `application/json`

CRAFT raw output은 다음 stage에 직접 넘기지 않는다.

- `polys` / `boxes` 같은 provider raw 결과를 정규화한다.
- 정규화 결과는 `text_regions` artifact로 저장한다.
- orchestrator/document 쪽에는 `set_stage_meta(text_detection)` patch로 요약만 남긴다.

현재 구현 범위:

- 입력 bitmap은 `file://` artifact를 사용한다.
- 결과 `text_regions`는 workspace 아래 JSON artifact로 기록한다.
- 샘플 실행은 `scripts/run_craft_sample.py`를 사용한다.

권장 `stage_config`:

- `input_artifact_ref`
- `text_threshold`
- `link_threshold`
- `low_text`
- `cuda`

## 19. Built-in Inpaint Strategy

첫 built-in `inpaint` 구현체는 나노바나나 API를 기준으로 설계한다.

핵심 원칙:

- 나노바나나는 "텍스트를 지운 원본처럼 보이는 배경 복원"에 사용한다.
- 하지만 전체 페이지를 통째로 다시 생성하지 않는다.
- `text_regions`에 해당하는 부분만 잘라서 요청하고, 결과는 다시 원래 위치에 합성한다.
- 이 작업은 항상 `inpainting layer`에만 적용한다.
- 원본 입력 레이어는 직접 수정하지 않는다.

### 19.1 왜 crop 기반으로 처리하는가

전체 페이지를 한 번에 inpaint하면 아래 문제가 커진다.

- 원본 그림 손실이 커진다.
- 텍스트 주변과 무관한 배경도 같이 흔들린다.
- provider 변동성이 페이지 전체에 퍼진다.
- 재시도 시 비용이 커진다.

따라서 기본 전략은 `text_regions -> crop -> inpaint -> composite`다.

### 19.2 Layer 규칙

`inpaint` stage는 문서의 원본 그림 레이어를 직접 덮어쓰지 않는다.

권장 레이어 구조:

- 원본 페이지 레이어
- `inpainting layer`
- 이후 식자용 텍스트 레이어

규칙:

- `inpainting layer`의 `source_ref`만 `inpaint` stage가 갱신한다.
- 원본 레이어의 `source_ref`는 보존한다.
- 결과적으로 UI에서는 원본과 인페인팅 결과를 분리해서 토글/검토할 수 있어야 한다.
- inpaint 결과는 원본 페이지와 병합된 단일 bitmap으로 보존하지 않는다.
- 항상 "새로운 inpainting layer 결과물"로 유지하고, 이후 전송도 레이어 단위로 한다.

### 19.3 Stage 분리

`inpaint` 앞에는 `mask_or_erase_planning` stage를 둔다.

역할 분리:

- `text_detection`
  - CRAFT가 `text_regions`를 만든다.

- `mask_or_erase_planning`
  - `text_regions`를 정리한다.
  - crop box, padding, merge group, erase mask를 계산한다.
  - 나노바나나 합성 기준 단위를 만든다.

- `inpaint`
  - planner가 만든 task를 실제 provider 호출로 실행한다.
  - 원본 페이지 전체를 provider에 1회 전달한다.
  - provider가 돌려준 전체 결과 이미지에서 planner mask 영역만 `inpainting layer`용 비트맵으로 합성한다.

즉 `mask_or_erase_planning`은 모델보다 "inpaint 전처리 planner"에 가깝다.

### 19.4 mask_or_erase_planning 출력 계약

planner stage는 최소한 아래 artifact kind를 만들 수 있어야 한다.

- `erase_regions`
  - crop 단위 작업 리스트
- `erase_mask`
  - 로컬 `inpainting layer` 합성용 mask bitmap
- `inpaint_tasks`
  - provider 호출 단위 메타데이터

`inpaint_tasks` 예시 필드:

- `task_id`
- `source_artifact_ref`
- `text_region_refs`
- `crop_bbox`
- `expanded_bbox`
- `mask_artifact_ref`
- `target_layer_id`
- `composite_mode`
- `provider_params`

v1에서는 planner를 규칙 기반으로 시작한다.

### 19.5 Inpaint 요청 방식

나노바나나 API에는 planner mask를 보내지 않고, 원본 페이지 전체 이미지를 한 번만 넘긴다.

입력:

- 원본 페이지 bitmap
- provider prompt 또는 erase instruction
- stage/provider config

출력:

- 텍스트가 제거된 전체 페이지 result bitmap

그 다음 orchestrator 또는 `inpaint` stage 내부 합성기가 아래를 수행한다.

- planner가 만든 erase mask들을 하나의 합성 mask로 합친다.
- provider가 돌려준 전체 페이지 결과에서 mask 영역만 "새로운 inpainting layer canvas"에만 반영한다.
- 최종 결과는 새 `inpainting layer` artifact ref로 저장한다.
- 원본 페이지 bitmap과는 병합하지 않는다.
- 문서에는 `replace_source_ref` 또는 `add_layer`로 새 인페인팅 레이어 결과만 반영한다.

현재 built-in adapter는 Vertex AI 경유 호출을 기준으로 한다.

- provider name: `nanobanana`
- runtime library: `google-genai`
- authentication: Vertex AI express mode API key 또는 동일 형식의 provider key를 credential binding으로 주입
- raw key는 코드, patch, artifact, stage_report에 남기지 않는다

### 19.6 Inpainting Layer 전용 적용 규칙

이 규칙은 강제한다.

- `inpaint` stage는 `target_layer_id`가 `inpainting layer`가 아니면 실행하면 안 된다.
- planner가 만든 task에도 `target_layer_id`를 명시한다.
- 원본 레이어, OCR overlay, typesetting layer에는 inpaint를 적용하지 않는다.
- provider output은 항상 독립 `inpainting layer` 결과로 들고 있어야 한다.

즉 inpaint는 "문서를 직접 파괴하는 stage"가 아니라 "인페인팅 전용 레이어를 갱신하는 stage"다.

### 19.7 Failure 및 Snapshot 규칙

나노바나나 같은 외부 provider stage는 다음 규칙을 따른다.

- provider가 멈추거나 timeout/abort로 끝나면 `failed`로 간주한다.
- 이 경우 현재 transaction 경로 아래의 입력 페이지, mask, task snapshot, 이미 생성된 결과물은 보존할 수 있다.
- 기본 정책은 "실패 + snapshot 보존"이며, 성공으로 간주되는 `partial` 처리로 올리지 않는다.

즉 운영상 재현과 디버깅을 우선하고, 묵시적 성공 처리로 넘기지 않는다.

### 19.8 v1 구현 결론

현재 v1 방향은 아래로 고정한다.

- `text_detection`은 CRAFT
- `mask_or_erase_planning`은 규칙 기반
- `inpaint`는 나노바나나 API
- `text_regions`를 그대로 provider에 넘기지 않고 planner task로 변환
- provider에는 원본 페이지 전체를 1회 전달한다
- provider 결과는 전체 페이지 단위로 받고, planner mask 영역만 새 `inpainting layer` 결과물로 유지
- 원본 그림 손실 최소화가 기본 목표
- provider hang/timeout은 `failed + snapshot 보존`
- local file artifact는 transaction 경로 아래 저장

현재 구현 범위:

- 규칙 기반 `mask_or_erase_planning` stage가 `erase_mask`와 `inpaint_tasks`를 만든다.
- built-in `inpaint` adapter가 Vertex AI 경유 나노바나나 호출 형식을 따른다.
- 나노바나나 prompt는 기본 프롬프트를 내장하되 stage config로 override 가능하다.
- 실제 provider 호출은 `google-genai` 런타임이 준비된 환경에서 수행한다.

권장 `stage_config`:

- `inpaint_tasks_ref`
- `prompt`
- `model_name`

권장 planner `stage_config`:

- `input_artifact_ref`
- `text_regions_artifact_ref`
- `padding`
- `target_layer_id`

## 20. Built-in Translation Strategy

현재 built-in `translation` adapter는 두 경로를 지원한다.

- 기본 로컬/개발 경로: OpenAI-compatible `/v1/chat/completions`
  - 기본 base URL: `http://127.0.0.1:1234/v1`
  - Docker Compose 기본 base URL: `http://host.docker.internal:1234/v1`
  - 주 사용 대상: LM Studio, Ollama OpenAI-compatible endpoint, custom proxy
  - provider name: `openai_compatible` (API key가 필요한 proxy일 때만 사용)
- Vertex 경로:
  - provider name: `translation_provider`
  - runtime library: `google-genai`
  - authentication: Vertex AI express mode API key 또는 동일 형식의 provider key를 credential binding으로 주입
- raw key는 코드, patch, artifact, stage_report에 남기지 않는다

입력 규칙:

- 입력은 `DocumentIR.text_blocks`다.
- `translation` stage는 OCR이 만든 `source_lang_text`를 읽고 `translated_text`만 채운다.
- geometry, reading order, writing mode, region ref는 번역 stage에서 바꾸지 않는다.

출력 규칙:

- canonical artifact kind: `translated_text_blocks`
- canonical patch: `replace_text_blocks`
- stage meta key: `translation`

기본 구현 결론:

- built-in `translation` 기본 샘플 경로는 OpenAI-compatible adapter를 사용한다.
- OpenAI-compatible 기본 모델 이름은 `local-model`이다.
- Vertex 경로의 기본 모델 이름은 `gemini-3.1-flash-lite-preview`다.
- 응답은 JSON으로 강제하고, `block_id -> translated_text` 매핑으로 다시 병합한다.
- `block_id`가 빠진 응답은 입력 순서 fallback을 허용하되 warning을 남긴다.
- 일부 block이 비면 stage는 `partial`로 기록할 수 있다.

현재 보완된 점:

- OCR 결과는 block별 호출이 아니라 page block 전체를 모아 한 번의 LLM 호출로 번역한다.
- OpenAI-compatible backend는 LM Studio, Ollama OpenAI-compatible endpoint, custom proxy를 같은 contract로 받는다.
- local runtime 값은 `env > .runtime/runtime_config.json > default` 우선순위로 해석한다.
- OCR stage가 `style_hint.ocr_status=needs_review`, `ocr_warnings`, density/area/text length를 남기므로, 번역 전후 분석 기준점이 생겼다.

현재 남아 있는 보완 항목:

- provider별 strict structured output 강제 강화
- fenced code block, prefix/suffix 설명문 등을 복구하는 JSON repair path 추가
- `block_id` 누락 시 positional fallback 의존도 축소 또는 제거
- OCR `needs_review`/warning 정보를 번역 prompt에 전달하는 경로 추가
- block 수가 많은 페이지용 chunking 정책
- timeout, `429`, `5xx`, local warm-up 지연에 대한 retry/backoff
- glossary / term map / 이름 고정 번역 규칙
- provider별 응답 shape 편차에 대한 compatibility 보강

권장 `stage_config`:

- `provider`
- `base_url`
- `model_name`
- `source_language`
- `target_language`
- `temperature`
