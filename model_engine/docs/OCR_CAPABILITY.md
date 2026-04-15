# OCR Capability Spec

이 문서는 `model_engine`의 `ocr` capability가 따라야 하는 공통 규격을 정의한다.

목표는 특정 OCR 모델 하나를 붙이는 것이 아니라,

- `manga-ocr`
- `PaddleOCR`
- 외부 OCR API

를 같은 capability 계약 안에 넣을 수 있게 하는 것이다.

이 문서는 구현체 선택보다 먼저 적용되는 capability-level 계약이다.

## 1. 설계 원칙

OCR capability는 아래 원칙을 따른다.

- `ocr`는 모델 이름이 아니라 stage capability 이름이다.
- concrete model 차이는 `manifest + adapter_config`에서만 흡수한다.
- local/cloud 차이는 bootstrap과 credential source에서만 처리하고, stage 입출력 계약은 유지한다.
- OCR 원문과 중간 산출물은 `model_engine` 내부에 남기고 `service_engine`으로 보내지 않는다.
- OCR stage는 가능한 한 detection과 분리한다.

즉 v1 기준 기본 graph는 아래를 전제한다.

- `text_detection`
  - 텍스트 영역 검출
  - canonical output: `text_regions`

- `ocr`
  - 검출된 영역 인식
  - canonical output: `text_blocks`

## 2. Capability Identity

- `stage_kind`: `ocr`
- canonical stage name: `ocr`

권장 `model_id` 예:

- `builtin.manga_ocr.recognizer`
- `custom.paddleocr.recognizer`
- `remote.vision_api.ocr`

## 3. Input Contract

OCR stage는 아래 artifact를 입력으로 요구한다.

- 필수:
  - `bitmap`
  - `text_regions`

- optional:
  - `ocr_guidance`
  - `crop_bitmap_bundle`
  - 기존 `text_blocks`

의미:

- `bitmap`
  - 원본 페이지 또는 현재 OCR 대상 raster
- `text_regions`
  - detection stage가 정규화한 읽기 대상 영역 목록
- 기존 `text_blocks`
  - 재실행/부분 갱신 시 merge 판단에 사용할 수 있음

권장 `stage_config`:

- `input_artifact_ref`
- `text_regions_artifact_ref`
- `language_hint`
- `writing_mode_hint`
- `region_padding`
- `min_confidence`
- `merge_adjacent_regions`
- `preserve_existing_blocks`
- `region_limit`

규칙:

- OCR stage는 detection raw output을 직접 입력으로 받지 않는다.
- detection 결과는 반드시 `text_regions` 정규화 artifact를 거친다.
- `stage_config`는 JSON-serializable 이어야 한다.

## 4. Output Contract

OCR stage의 canonical semantic output은 `DocumentIR.text_blocks`다.

즉 어떤 OCR 구현체든 최종적으로는 `TextBlock` 집합으로 정규화돼야 한다.

최소 `TextBlock` 필드:

- `block_id`
- `source_lang_text`
- `polygon`
- `bbox`
- `reading_order`
- `source_region_ref`

권장 필드:

- `translated_text`
  - OCR 단계에서는 보통 빈 문자열
- `writing_mode`
- `speaker`
- `style_hint`
- `font_hint`

규칙:

- OCR stage는 원문 인식만 담당한다.
- 번역문은 `translation` stage가 채운다.
- block ordering은 가능한 한 `text_regions.reading_order`를 계승한다.
- OCR confidence는 `stage_report.metrics` 또는 artifact metadata에 둘 수 있지만 canonical `TextBlock` 필수 필드는 아니다.

## 5. Artifact Contract

OCR stage는 아래 artifact kind를 권장한다.

- `ocr_text_blocks`
  - media type: `application/json`
  - 의미: canonical `TextBlock` 목록의 직렬화 결과

- optional:
  - `ocr_debug_crops`
  - `ocr_raw_response`
  - `ocr_overlay_preview`

canonical artifact payload 예시:

```json
{
  "schema_version": "v1",
  "engine": "manga_ocr",
  "source_artifact_ref": "artifact://page",
  "text_regions_artifact_ref": "artifact://text_regions",
  "blocks": [
    {
      "block_id": "block_0001",
      "source_lang_text": "こんにちは",
      "translated_text": "",
      "polygon": [],
      "bbox": {"x": 10, "y": 20, "width": 80, "height": 24},
      "reading_order": 0,
      "speaker": null,
      "style_hint": {},
      "font_hint": {},
      "writing_mode": "vertical",
      "source_region_ref": "region_0001"
    }
  ],
  "metadata": {
    "recognized_count": 1,
    "empty_region_count": 0
  }
}
```

규칙:

- debug artifact는 provider/model-specific이어도 된다.
- canonical artifact는 capability-level schema를 따라야 한다.
- raw OCR provider 응답은 optional artifact로만 허용하고, 다음 stage의 직접 입력 계약으로 삼지 않는다.

## 6. Patch Contract

OCR stage가 문서에 반영하는 canonical mutation은 `text_blocks` 갱신이다.

권장 patch:

- `replace_text_blocks`
  - OCR stage가 관리하는 block 집합 전체를 교체

보조 patch:

- `append_text_blocks`
  - 실험용 또는 incremental merge에서만 제한적으로 사용
- `set_stage_meta`
  - OCR 엔진, artifact ref, 통계 기록

현재 코드 기준으로 `replace_text_blocks` patch는 구현되어 있다.

권장 규칙:

- OCR stage는 `replace_text_blocks`를 canonical mutation으로 사용한다.
- `append_text_blocks`는 실험용 또는 incremental merge에서만 제한적으로 사용한다.
- OCR stage는 `DocumentIR.text_blocks`의 authoritative producer로 본다.

## 7. Stage Report Contract

OCR stage는 공통적으로 아래 metrics를 남기는 것을 권장한다.

- `engine`
- `model_id`
- `language_hint`
- `region_count`
- `recognized_count`
- `empty_region_count`
- `avg_confidence`
- `writing_mode_detected`

권장 warning 예:

- `low_confidence_region_count>0`
- `ocr_region_clamped`
- `ocr_region_skipped`

공통 error code:

- `ocr_input_missing`
- `ocr_invalid_region`
- `ocr_provider_error`
- `ocr_timeout`
- `ocr_invalid_output`

## 8. Credential Policy

v1 기준 기본 정책:

- 기본 credential source: `none`
- local Python OCR:
  - `none`
- local GPU OCR:
  - `none`
- 외부 OCR API:
  - `user_personal_*` 또는 `platform_managed`

즉 `ocr` capability 자체는 credential 비필수 capability로 정의하고,
구체 구현체 manifest가 필요 시 source를 더 좁힌다.

예:

- `manga-ocr`
  - `allowed_credential_sources=["none"]`
- `PaddleOCR local`
  - `allowed_credential_sources=["none"]`
- remote OCR API
  - `allowed_credential_sources=["user_personal_persisted", "user_personal_session", "platform_managed"]`

## 9. Adapter Rules

OCR 구현체는 아래 두 종류로 붙는 것을 우선 지원한다.

- `python_callable`
  - 같은 Python runtime 안에서 직접 실행
  - `manga-ocr`, `PaddleOCR local`에 적합

- `http_api`
  - 원격 OCR 서버나 SaaS provider 래퍼

adapter 책임:

- `text_regions`를 읽고 OCR 대상 crop 단위를 준비
- provider/model 출력 문자열과 geometry를 canonical `TextBlock`으로 변환
- capability 공통 artifact와 stage report를 생성
- provider raw output을 canonical schema 밖으로 퍼뜨리지 않음

## 10. Region Handling Rules

OCR stage는 `text_regions`를 기준으로 crop 단위 인식을 수행하는 것을 기본값으로 본다.

기본 규칙:

- region별 crop을 만든다
- crop 결과를 해당 region의 `source_region_ref`에 묶는다
- `region_padding`은 선택적이다
- 인식 실패 region도 block을 억지로 만들지 않는다

병합 규칙:

- 기본은 region 1개 -> block 1개
- provider가 line grouping을 잘 지원하는 경우 adapter 내부에서 여러 region merge 가능
- 다만 merge 시에도 `source_region_ref` trace를 metadata 또는 별도 field로 보존하는 것이 좋다

v1 권장:

- 먼저 `1 region = 1 block`
- 이후 bubble grouping/vertical merge는 후속 단계에서 확장

## 11. Mode Compatibility

OCR capability는 local/cloud 모두 같은 contract를 사용한다.

다만 concrete manifest는 아래처럼 다를 수 있다.

- local-only OCR
  - `supported_modes=["local"]`
- local+saas OCR
  - `supported_modes=["local", "saas"]`

중요:

- mode에 따라 output schema가 달라지면 안 된다.
- OCR output의 canonical shape는 항상 동일해야 한다.

## 12. First Built-in Recommendation

첫 구현체를 무엇으로 넣든 아래 규칙은 유지한다.

- capability-level contract 먼저
- concrete provider는 adapter로만 분리
- raw response를 다음 stage 계약으로 쓰지 않음

현재 우선순위 추천:

1. `manga-ocr`
   - 일본어 만화 특화 local OCR
2. `PaddleOCR recognizer`
   - 다국어/운영 범용성 대비
3. remote OCR API adapter
   - managed runtime이 필요할 때

즉 `manga-ocr`는 `ocr` capability의 첫 built-in 구현체가 될 수 있지만,
capability 정의 자체를 대신하지는 않는다.

## 13. 구현 전 체크리스트

`manga-ocr`나 다른 OCR을 붙이기 전에 아래를 먼저 닫는다.

1. `ocr_text_blocks` canonical artifact schema 확정
2. OCR contract test 정의
3. `text_regions -> text_blocks` trace 보존 규칙 확정
4. low-confidence / empty result 처리 규칙 확정
5. 첫 built-in OCR 구현체 등록

이 다섯 가지를 먼저 닫아야,

- `manga-ocr`
- `PaddleOCR`
- 외부 OCR API

를 같은 capability 규격 아래 비교 가능하게 붙일 수 있다.
