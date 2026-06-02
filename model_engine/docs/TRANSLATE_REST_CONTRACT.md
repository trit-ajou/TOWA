# Translate REST Contract

## Intent

`translate`는 더 이상 text detection이나 OCR을 실행하지 않는다. 번역은 사용자가 먼저 실행한 `detect` 결과의 `document.text_blocks`를 입력으로 받아 LLM 번역만 수행한다.

이 계약의 목적은 detect 단계에서 이미 확인된 text box와 원문 OCR을 보존하고, translate 클릭 시 낮은 품질의 재검출/재OCR로 text box가 새로 만들어지는 문제를 막는 것이다.

## UI Flow

1. UI calls `operation_kind="detect"` with the page bitmap.
2. Model-engine returns `replace_text_blocks` containing text boxes and Japanese `source_lang_text`.
3. UI applies or stores those text blocks as the current page `document.text_blocks`.
4. UI calls `operation_kind="translate"` with those existing `document.text_blocks`.
5. Model-engine runs only the `translation` stage and returns the same block geometry with `translated_text` filled.

## Request

Recommended request form for translate is JSON or multipart metadata-only. A bitmap is not required.

```http
POST /v1/jobs
Content-Type: application/json
Authorization: Bearer <session_key>  # cloud only
```

```json
{
  "schema_version": "v1",
  "idempotency_key": "project:proj-1:page:001:op:translate:v:1",
  "operation_kind": "translate",
  "request_ref": "project/proj-1/page/001",
  "document": {
    "id": "doc_page_001",
    "name": "page-001",
    "width": 800,
    "height": 1200,
    "layers": [],
    "text_blocks": [
      {
        "block_id": "block_0001",
        "source_lang_text": "こんにちは",
        "translated_text": "",
        "polygon": [],
        "bbox": { "x": 120, "y": 80, "width": 160, "height": 70 },
        "reading_order": 1,
        "writing_mode": "vertical",
        "source_region_ref": "region_0001"
      }
    ],
    "stage_meta": {}
  },
  "artifacts": {},
  "runtime_context": {
    "mode": "saas",
    "workspace_uri": "workspace://project/proj-1/page/001",
    "requested_by": "user@example.com",
    "target_regions": [],
    "selected_layer_ids": []
  }
}
```

Multipart is also accepted for UI consistency:

```http
POST /v1/jobs
Content-Type: multipart/form-data
```

Required part:

- `metadata`: JSON payload shown above

Optional part:

- `primary_bitmap`: ignored by translate. Do not send it unless the existing UI transport cannot avoid it.

## Required Text Block Fields

Each translatable block should include:

- `block_id`: stable id from detect. Translation output is merged by this id.
- `source_lang_text`: Japanese OCR text. At least one text block must have non-empty `source_lang_text`.
- `bbox` / `polygon`: geometry from detect. Translation does not recompute or change geometry.
- `writing_mode`, `reading_order`, `source_region_ref`: preserved metadata.

If no text block has non-empty `source_lang_text`, model-engine fails the `translation` stage with `translation_invalid_output`.

## Response

The response patch still uses `replace_text_blocks`, but it is not a new detection result. It is the same block set with `translated_text` populated.

```json
{
  "document_patch": {
    "patches": [
      {
        "op": "replace_text_blocks",
        "payload": {
          "text_blocks": [
            {
              "block_id": "block_0001",
              "source_lang_text": "こんにちは",
              "translated_text": "안녕하세요",
              "bbox": { "x": 120, "y": 80, "width": 160, "height": 70 },
              "polygon": [],
              "reading_order": 1,
              "writing_mode": "vertical",
              "source_region_ref": "region_0001"
            }
          ]
        }
      },
      {
        "op": "set_stage_meta",
        "payload": {
          "key": "translation",
          "value": {
            "engine": "openai_compatible_translation",
            "translated_count": 1,
            "missing_count": 0
          }
        }
      }
    ]
  },
  "stage_reports": [
    {
      "stage_name": "translation",
      "status": "succeeded",
      "metrics": {
        "source_block_count": 1,
        "translated_count": 1,
        "missing_count": 0
      }
    }
  ]
}
```

## Non-Goals

- `translate` does not create text boxes.
- `translate` does not run CRAFT.
- `translate` does not run manga OCR.
- `translate` does not alter bbox, polygon, reading order, or writing mode.
