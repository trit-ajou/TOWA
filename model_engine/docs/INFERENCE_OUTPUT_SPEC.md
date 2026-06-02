# Model Inference Output Spec

이 문서는 현재 구현 기준으로 `model_engine`이 추론을 실행한 뒤 외부 개발자에게 어떤 결과물을 돌려주는지 정리한다.

범위:

- `UI engine -> model_engine`의 `/v1/jobs` 생성과 조회 응답
- job 내부 stage가 생성하는 `document_patch`, `artifacts`, `stage_reports`
- 현재 built-in operation인 `detect`, `translate`, `inpaint`의 결과 형태

비범위:

- `service_engine`의 인증, usage, credit 정산 상세
- UI의 최종 page snapshot 저장 형식
- Bitmappery `.bpy` 저장 포맷

## 1. 전체 흐름

현재 `model_engine`은 비동기 job API로 동작한다.

1. UI가 `POST /v1/jobs`로 job을 생성한다.
2. model은 즉시 `job_id`, `pipeline_id`, `status_url`을 반환한다.
3. background thread가 operation별 stage pipeline을 실행한다.
4. UI가 `GET /v1/jobs/{job_id}`로 상태와 결과를 poll 한다.
5. terminal 상태가 되면 UI는 `document_patch`를 현재 page state에 병합한다.

중요한 원칙:

- model은 최종 page authority가 아니다.
- model의 merge 대상 결과는 `document_patch`다.
- `document`는 현재 migration/debug compatibility 용도이며 UI가 authoritative result로 간주하면 안 된다.
- 큰 결과물은 JSON 본문에 직접 넣지 않고 `artifacts` descriptor로 참조한다.

## 2. Job Create Output

요청:

```http
POST /v1/jobs
```

현재 create 입력은 두 경로를 지원한다.

- 권장 경로: `multipart/form-data`
  - `metadata`
  - `primary_bitmap`
- 전환기 compatibility 경로: `application/json`

create 응답은 두 입력 경로 모두 동일하다.

```json
{
  "job_id": "job_123",
  "pipeline_id": "pipe_123",
  "status": "queued",
  "operation_kind": "detect",
  "request_ref": "project/proj-1/page/001",
  "status_url": "/v1/jobs/job_123"
}
```

필드 의미:

- `job_id`: job 조회용 식별자
- `pipeline_id`: 내부 stage run과 artifact ref prefix에 사용되는 pipeline 식별자
- `status`: 생성 직후 보통 `queued`
- `operation_kind`: 요청한 operation
- `request_ref`: UI/service가 같은 page 또는 작업 대상을 추적하기 위한 opaque ref
- `status_url`: poll path

현재 API schema에는 `pipeline`도 타입상 남아 있지만, 실제 구현의 `SUPPORTED_OPERATIONS`는 `detect`, `translate`, `inpaint`만 허용한다.

## 3. Job Poll Output

요청:

```http
GET /v1/jobs/{job_id}
```

응답 기본 형태:

```json
{
  "job_id": "job_123",
  "pipeline_id": "pipe_123",
  "status": "succeeded",
  "operation_kind": "translate",
  "request_ref": "project/proj-1/page/001",
  "document": {},
  "document_patch": {
    "patches": []
  },
  "artifacts": {},
  "stage_reports": [],
  "error": null
}
```

### 3.1 status

허용값:

- `queued`
- `running`
- `succeeded`
- `failed`
- `partial`

Terminal 상태:

- `succeeded`
- `failed`
- `partial`

현재 stage 실행 결과와 job 상태 매핑:

- 모든 stage가 `succeeded`: job `succeeded`
- 하나라도 stage가 `failed`: job `failed`
- 하나라도 stage가 `partial`이고 실패가 없음: job `partial`
- billing finalization 실패가 붙으면 성공 job도 `partial`로 내려갈 수 있다

## 4. document_patch

`document_patch`가 UI merge의 핵심 결과다.

형태:

```json
{
  "patches": [
    {
      "op": "replace_text_blocks",
      "target": {},
      "payload": {
        "text_blocks": []
      }
    }
  ]
}
```

각 patch는 `model_engine.contracts.patches.PatchOperation`의 JSON 표현이다.

현재 구현된 patch op:

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

현재 built-in inference path에서 주로 나오는 op:

- `set_stage_meta`
- `replace_text_blocks`
- `add_layer`
- `replace_source_ref`

UI 우선 대응 권장 op:

- `replace_text_blocks`
- `append_text_blocks`
- `replace_source_ref`
- `add_layer`
- `set_stage_meta`

### 4.1 set_stage_meta

stage별 실행 결과 요약을 `document.stage_meta`에 기록한다.

예:

```json
{
  "op": "set_stage_meta",
  "target": {},
  "payload": {
    "key": "text_detection",
    "value": {
      "engine": "craft",
      "artifact_ref": "artifact://pipe_123/text_detection/pipe_123-text_detection-1/text_regions",
      "region_count": 12
    }
  }
}
```

UI는 이 값을 사용자 표시, 디버그, 재실행 판단에 사용할 수 있다. 저장 authority로 다루지는 않는다.

### 4.2 replace_text_blocks

OCR 또는 번역 결과로 `document.text_blocks` 전체를 교체한다.

예:

```json
{
  "op": "replace_text_blocks",
  "target": {},
  "payload": {
    "text_blocks": [
      {
        "block_id": "ocr_0001",
        "source_lang_text": "こんにちは",
        "translated_text": "안녕하세요",
        "polygon": [{"x": 10.0, "y": 20.0}],
        "bbox": {"x": 10.0, "y": 20.0, "width": 100.0, "height": 40.0},
        "reading_order": 1,
        "writing_mode": "vertical",
        "style_hint": {},
        "font_hint": {}
      }
    ]
  }
}
```

OCR stage는 `source_lang_text`를 채우고, translation stage는 기존 text block에 `translated_text`를 채운 새 배열을 반환한다.

### 4.3 add_layer

inpaint 결과를 담을 target layer가 없을 때 새 graphic layer를 추가한다.

예:

```json
{
  "op": "add_layer",
  "target": {},
  "payload": {
    "layer": {
      "id": "layer_inpainting",
      "name": "Inpainting Layer",
      "type": "graphic",
      "left": 0,
      "top": 0,
      "width": 1200,
      "height": 1600,
      "visible": true,
      "transparent": true,
      "source_ref": "artifact://pipe_123/inpaint/pipe_123-inpaint-3/inpainting_bitmap",
      "props": {
        "role": "inpainting_layer"
      }
    }
  }
}
```

`source_ref`는 반드시 같은 응답의 `artifacts` map에서 찾아야 한다.

### 4.4 replace_source_ref

이미 target layer가 있을 때 해당 layer의 bitmap source만 교체한다.

예:

```json
{
  "op": "replace_source_ref",
  "target": {
    "layer_id": "layer_inpainting"
  },
  "payload": {
    "source_ref": "artifact://pipe_123/inpaint/pipe_123-inpaint-3/inpainting_bitmap"
  }
}
```

## 5. artifacts

`artifacts`는 array가 아니라 map이다.

형태:

```json
{
  "artifact://pipe_123/text_detection/run/text_regions": {
    "artifact_ref": "artifact://pipe_123/text_detection/run/text_regions",
    "kind": "text_regions",
    "media_type": "application/json",
    "uri": "file:///tmp/towa_model_job_upload_xxx/text_regions.json",
    "width": 1200,
    "height": 1600,
    "byte_size": 1234,
    "checksum": null,
    "version": 1,
    "producer_stage": "text_detection",
    "status": "ready",
    "metadata": {}
  }
}
```

Descriptor 필드:

- `artifact_ref`: patch와 stage report에서 참조하는 stable key
- `kind`: artifact 의미
- `media_type`: binary 또는 JSON payload media type
- `uri`: 현재 구현에서는 주로 `file://...`
- `width`, `height`: bitmap 또는 image-derived artifact의 크기
- `byte_size`: 파일 크기
- `checksum`: 있으면 `sha256:<hex>` 형식
- `version`: 같은 논리 artifact의 버전
- `producer_stage`: artifact를 만든 stage
- `status`: `pending`, `ready`, `failed`, `released`, `orphaned`
- `metadata`: stage별 보조 정보

주의:

- UI는 `file://` URI를 브라우저에서 직접 fetch할 수 없을 수 있다.
- 현재 output contract의 핵심은 artifact descriptor와 ref 관계다.
- 원격 object storage 또는 artifact download endpoint는 아직 별도 합의가 필요하다.

## 6. stage_reports

`stage_reports`는 stage별 실행 보고서다.

형태:

```json
{
  "stage_name": "ocr",
  "stage_run_id": "pipe_123:ocr:2",
  "status": "succeeded",
  "input_refs": ["artifact://input/primary_bitmap"],
  "output_refs": ["artifact://pipe_123/ocr/pipe_123-ocr-2/ocr_text_blocks"],
  "warnings": [],
  "metrics": {
    "engine": "manga_ocr",
    "recognized_count": 12
  },
  "provider": null,
  "error_code": null,
  "error_message": null,
  "started_at": "2026-05-07T00:00:00+00:00",
  "finished_at": "2026-05-07T00:00:03+00:00"
}
```

UI 용도:

- 진행 상태 표시
- stage별 warning 표시
- 실패 stage 식별
- 디버그 패널

`provider`는 raw secret이 아니라 credential metadata만 담는다.

## 7. error

job이 실패하면 `error`에 요약 envelope이 들어간다.

예:

```json
{
  "code": "model_stage_failed",
  "message": "ocr failed",
  "retryable": false,
  "details": {
    "stage_name": "ocr"
  }
}
```

현재 executor 예외가 stage report로 정리되지 못하면 다음처럼 내려갈 수 있다.

```json
{
  "code": "model_stage_failed",
  "message": "Configured input_artifact_ref not found: artifact://input/primary_bitmap",
  "retryable": false,
  "details": {
    "operation_kind": "detect"
  }
}
```

billing finalization 실패가 별도로 붙는 경우, primary error의 `details.billing` 아래에 billing error가 포함된다.

## 8. Operation별 현재 결과

### 8.1 detect

Stage pipeline:

1. `text_detection`

출력:

- `document_patch.patches`
  - `set_stage_meta` with key `text_detection`
- `artifacts`
  - `kind=text_regions`
- `stage_reports`
  - `stage_name=text_detection`
  - metrics: `detector`, `region_count`, `input_artifact_ref`

대표 patch:

```json
{
  "op": "set_stage_meta",
  "target": {},
  "payload": {
    "key": "text_detection",
    "value": {
      "engine": "craft",
      "artifact_ref": "artifact://pipe_123/text_detection/run/text_regions",
      "region_count": 12
    }
  }
}
```

대표 artifact:

```json
{
  "artifact_ref": "artifact://pipe_123/text_detection/run/text_regions",
  "kind": "text_regions",
  "media_type": "application/json",
  "uri": "file:///.../text_regions.json",
  "producer_stage": "text_detection",
  "metadata": {
    "detector": "craft",
    "region_count": 12,
    "source_artifact_ref": "artifact://input/primary_bitmap"
  }
}
```

### 8.2 translate

Stage pipeline:

1. `translation`

입력:

- `document.text_blocks`
- 각 block은 선행 `detect` 결과에서 온 `source_lang_text`를 포함해야 한다.
- bitmap artifact는 필요하지 않다.

출력:

- `document_patch.patches`
  - `replace_text_blocks`
  - `set_stage_meta` with key `translation`
- `artifacts`
  - `kind=translated_text_blocks`
- `stage_reports`
  - `translation`

주의:

- `translate`는 CRAFT text detection을 다시 실행하지 않는다.
- `translate`는 manga OCR을 다시 실행하지 않는다.
- `translate` 응답의 `replace_text_blocks`는 새 bbox가 아니라 기존 block geometry에 `translated_text`만 채운 결과다.

Translate 요청의 `document.text_blocks` 예시:

```json
[
  {
    "block_id": "ocr_0001",
    "source_lang_text": "こんにちは",
    "translated_text": "",
    "bbox": {"x": 10.0, "y": 20.0, "width": 100.0, "height": 40.0},
    "writing_mode": "vertical",
    "reading_order": 1
  }
]
```

Translation 대표 patch:

```json
{
  "op": "replace_text_blocks",
  "target": {},
  "payload": {
    "text_blocks": [
      {
        "block_id": "ocr_0001",
        "source_lang_text": "こんにちは",
        "translated_text": "안녕하세요",
        "bbox": {"x": 10.0, "y": 20.0, "width": 100.0, "height": 40.0},
        "writing_mode": "vertical",
        "reading_order": 1
      }
    ]
  }
}
```

Translation status:

- 모든 block이 번역되면 stage `succeeded`, job `succeeded`
- 누락 번역이 있으면 translation stage `partial`, job `partial`

### 8.3 inpaint

Stage pipeline:

1. `text_detection`
2. `mask_or_erase_planning`
3. `inpaint`

출력:

- `document_patch.patches`
  - `set_stage_meta` with key `text_detection`
  - `set_stage_meta` with key `mask_or_erase_planning`
  - `add_layer` 또는 `replace_source_ref`
  - `set_stage_meta` with key `inpaint`
- `artifacts`
  - `kind=text_regions`
  - `kind=erase_mask`
  - `kind=inpaint_tasks`
  - `kind=bitmap` for provider output
  - `kind=bitmap` for inpainting layer bitmap
- `stage_reports`
  - `text_detection`, `mask_or_erase_planning`, `inpaint`

Planner 대표 artifact:

```json
{
  "artifact_ref": "artifact://pipe_123/mask_or_erase_planning/run/inpaint_tasks",
  "kind": "inpaint_tasks",
  "media_type": "application/json",
  "uri": "file:///.../inpaint_tasks.json",
  "producer_stage": "mask_or_erase_planning",
  "metadata": {
    "task_count": 12,
    "target_layer_id": "layer_inpainting",
    "source_artifact_ref": "artifact://input/primary_bitmap"
  }
}
```

Inpaint success patch:

```json
{
  "op": "replace_source_ref",
  "target": {
    "layer_id": "layer_inpainting"
  },
  "payload": {
    "source_ref": "artifact://pipe_123/inpaint/run/inpainting_bitmap"
  }
}
```

Target layer가 없으면 `replace_source_ref` 대신 `add_layer`가 나온다.

Inpaint provider 실패 시:

- stage status: `failed`
- job status: `failed`
- `document_patch.patches`: inpaint stage에서는 빈 배열
- `artifacts`
  - `kind=bitmap`, `status=failed`, metadata role `partial_inpainting_snapshot`
  - `kind=stage_snapshot`, metadata role `failure_snapshot`
- `stage_reports[-1].error_code`, `error_message`가 채워진다

## 9. TextBlock Shape

`replace_text_blocks`가 전달하는 block은 현재 `DocumentIR.TextBlock` 기반이다.

주요 필드:

```json
{
  "block_id": "ocr_0001",
  "source_lang_text": "こんにちは",
  "translated_text": "안녕하세요",
  "polygon": [{"x": 10.0, "y": 20.0}],
  "bbox": {"x": 10.0, "y": 20.0, "width": 100.0, "height": 40.0},
  "reading_order": 1,
  "speaker": null,
  "style_hint": {},
  "font_hint": {},
  "writing_mode": "vertical",
  "source_region_ref": "region_0001"
}
```

UI가 최소로 사용해야 하는 필드:

- `block_id`
- `source_lang_text`
- `translated_text`
- `bbox` 또는 `polygon`
- `reading_order`
- `writing_mode`

## 10. UI Merge 권장 순서

UI는 terminal poll 응답을 받으면 다음 순서로 처리한다.

1. `status`가 `failed`이면 `error`와 마지막 failed `stage_report`를 표시한다.
2. `status`가 `partial`이면 warning을 표시하되 적용 가능한 patch는 사용자 확인 후 적용할 수 있다.
3. `document_patch.patches`를 순서대로 현재 page state에 적용한다.
4. patch가 참조하는 `artifact_ref`를 `artifacts` map에서 resolve한다.
5. `document` 전체를 page state로 덮어쓰지 않는다.
6. 필요한 경우 UI가 최종 page snapshot을 별도 저장한다.

## 11. 현재 구현상 주의점

- UI real adapter는 아직 JSON create path를 사용한다. 목표 경로는 multipart `metadata + primary_bitmap`이다.
- Poll 응답에는 `document_patch`가 존재하지만, UI 타입과 merge path가 이를 완전히 쓰도록 보강되어야 한다.
- `pipeline` operation은 타입에 남아 있지만 현재 HTTP job에서는 지원하지 않는다.
- `file://` artifact URI는 local/server 내부 path다. browser 직접 접근용 public URL이 아니다.
- built-in CRAFT/OCR/inpaint는 현재 `file://` bitmap artifact를 기준으로 동작한다.
- `translate`와 `inpaint`는 provider credential과 runtime dependency가 필요하다.
