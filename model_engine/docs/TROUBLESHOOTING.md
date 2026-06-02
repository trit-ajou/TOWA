# model_engine Troubleshooting

이 문서는 `model_engine` 실행 중 실제로 관측한 문제와 조정 방법을 정리한다.
현재 핵심 대상은 `CRAFT -> manga-ocr -> translation` 경로다.

## Stage artifact dump

UI/API 경유 job에서 stage별 입력/출력 artifact를 직접 확인하려면 Docker 실행 전에 아래 값을 켠다.

```bash
TOWA_MODEL_ENGINE_STAGE_DUMP=1 docker compose up --build model-engine
```

생성 위치:

```bash
model_engine/.runtime/transactions/{pipeline_id}/{stage_name}/{stage_run_id}/stage_artifact_dump/
```

주요 파일:

- `stage_request.json`: stage에 들어간 document/artifact/config
- `stage_response.json`: stage가 반환한 patch/artifact/report
- `artifacts_before.json`, `artifacts_after.json`: stage 전후 artifact registry
- `document_after.json`: patch 적용 후 document
- `files/input/`, `files/output/`: `file://` artifact hardlink/copy

바이너리 복사를 끄려면 `TOWA_MODEL_ENGINE_STAGE_DUMP_COPY_FILES=0`을 함께 지정한다.
credential/session/token 계열 값은 dump JSON에서 redaction된다.

## 1. OCR 파이프라인: CRAFT + manga-ocr

### 1-1. 평가 대상

- Target pipeline: `text_detection`(CRAFT) -> `ocr`(manga-ocr)
- Test input: 일본어 만화 페이지
- 포함 케이스: 정식 말풍선, 스마트폰 UI 내 소형 텍스트, 손글씨/장식 텍스트
- 현재 상태: 정규 말풍선 OCR은 양호하지만, 소형 UI/손글씨/계정명 영역에서 환각 및 오인식이 발생할 수 있다.

### 1-2. OCR 단독 실행

Docker 기준:

```bash
cd model_engine
docker compose -f docker-compose.inference.yml run --build --rm ocr-sample
```

결과 위치:

```bash
model_engine/.runtime/transactions/pipe_ocr_sample/ocr/
```

OCR artifact 찾기:

```bash
find model_engine/.runtime/transactions/pipe_ocr_sample/ocr -name '*_ocr_text_blocks.json' -print
```

OCR 원문만 확인:

```bash
jq -r '.blocks[] | [.block_id, .source_region_ref, .source_lang_text] | @tsv' PATH_TO_OCR_TEXT_BLOCKS_JSON
```

품질 진단 필드 확인:

```bash
jq '.metadata' PATH_TO_OCR_TEXT_BLOCKS_JSON
```

블록별 튜닝값 확인:

```bash
jq -r '.blocks[] | [.block_id, .source_lang_text, (.style_hint.ocr_region_area_px // ""), (.style_hint.ocr_text_density_per_1000_px2 // ""), (.style_hint.ocr_text_length // ""), (.style_hint.ocr_status // ""), ((.style_hint.ocr_warnings // []) | join(","))] | @tsv' PATH_TO_OCR_TEXT_BLOCKS_JSON
```

## 2. 증상: manga-ocr 환각 텍스트

### 2-1. 관측된 현상

`manga-ocr`는 encoder-decoder 계열 OCR이기 때문에, 판독하기 어려운 crop에서도 그럴듯한 일본어를 생성할 수 있다.

관측 예시:

- 스마트폰 화면 내 극소형 텍스트에서 이미지와 무관한 장문 생성
- 계정명/기호 영역에서 원문 변형 후 임의 기호 추가
- 손글씨/장식 텍스트를 정규 문장처럼 오인식

대표적으로 아래와 같은 문자열이 정상 말풍선이 아닌 영역에서 생성되면 환각 의심으로 본다.

```text
オスクラスについては...
しまえのＡｍａｚｏｎ...
```

### 2-2. 현재 후처리 방식

환각 의심 블록은 기본적으로 삭제하지 않는다.
대신 `TextBlock.style_hint`에 검수 플래그를 남긴다.

예:

```json
{
  "style_hint": {
    "ocr_text_density_per_1000_px2": 1.656,
    "ocr_region_area_px": 3622.5,
    "ocr_text_length": 18,
    "ocr_status": "needs_review",
    "ocr_warnings": ["high_text_density"]
  }
}
```

이 방식의 목적은 Human-in-the-loop UI에서 해당 블록만 강조 표시하는 것이다.
예를 들어 UI는 `style_hint.ocr_status == "needs_review"`인 블록에 빨간 박스나 경고 배지를 붙이면 된다.

### 2-3. 현재 기본 threshold

현재 OCR stage 기본값:

```text
region_padding = 12
merge_regions = true
merge_gap_px = 24
merge_min_overlap_ratio = 0.25
reading_order_mode = vertical_rtl
min_ocr_region_area_px = 160
min_ocr_region_area_ratio = 0.00015
max_text_density_per_1000_px2 = 1.5
small_region_long_text_area_px = 6000
small_region_long_text_area_ratio = 0.004
small_region_long_text_min_chars = 16
hallucination_action = mark
```

관련 파일:

- `model_engine/builtin_models/manga_ocr.py`
- `model_engine/api/jobs.py`
- `model_engine/scripts/run_ocr_sample.py`
- `model_engine/scripts/run_translation_sample.py`
- `model_engine/scripts/run_pipeline_sample.py`

### 2-4. threshold 튜닝 기준

OCR metadata에서 다음 값을 먼저 본다.

```text
needs_review_count
skipped_small_region_count
high_density_count
small_region_long_text_count
max_text_density_per_1000_px2
min_ocr_region_area_px
```

해석:

- `needs_review_count == 0`인데 환각 텍스트가 남아 있으면 `max_text_density_per_1000_px2`가 너무 높을 가능성이 크다.
- 이번 샘플에서는 관측된 `max_text_density_per_1000_px2`가 `1.656`이었고, 기존 threshold가 `30`이라 필터가 전혀 걸리지 않았다.
- 그래서 기본 density threshold를 `1.5`로 낮췄다.
- 정상 텍스트까지 너무 많이 `needs_review`로 잡히면 `1.6` 정도로 올린다.
- 환각 블록이 계속 통과하면 `1.4` 정도로 내린다.

면적 필터는 조심해서 조정한다.

- `min_ocr_region_area_px`를 크게 올리면 작은 효과음, 짧은 말풍선, 기호성 텍스트까지 사라질 수 있다.
- CRAFT region merge 후에는 작은 텍스트라도 bbox가 커질 수 있으므로, 면적만으로 환각을 잡기 어렵다.
- 현재는 면적 필터보다 `density`와 `small_region_long_text` 규칙을 우선 사용한다.

### 2-5. `hallucination_action`

기본값:

```text
hallucination_action = mark
```

동작:

- `mark`: 블록을 보존하고 `style_hint.ocr_status = "needs_review"`를 남긴다.
- `drop`: 환각 의심 블록을 OCR 결과에서 제거한다.

현재는 `mark`를 권장한다.
번역/식자 전 단계에서 버리면 사용자 검수 UI에서 복구할 수 없기 때문이다.

## 3. 증상: Reading Order 역전

### 3-1. 관측된 현상

일본어 만화 세로쓰기에서는 보통 오른쪽에서 왼쪽으로 읽는다.
기존 정렬이 좌측 -> 우측 또는 detector의 원래 order를 그대로 따르면 동일 컷 안 말풍선 순서가 뒤집힐 수 있다.

### 3-2. 현재 해결 방식

OCR stage에서 아래 설정을 사용한다.

```text
reading_order_mode = vertical_rtl
```

정렬 기준:

- x 중심 좌표 내림차순
- 같은 column 안에서는 y 좌표 오름차순
- 이후 block `reading_order`는 정렬된 순서대로 재부여

현재 샘플에서는 마지막 컷 왼쪽 말풍선이 오른쪽 텍스트 -> 중앙 텍스트 -> 왼쪽 텍스트 순서로 정렬되어 정상 동작을 확인했다.

## 4. 증상: OCR이 너무 느림

### 4-1. 주요 원인 후보

- 첫 실행 시 Hugging Face / Transformers model download 또는 cache warm-up
- region 수가 너무 많아 crop별 OCR 호출이 많아짐
- `MangaOcr()` 인스턴스를 crop마다 새로 만들면 모델 로딩 비용이 반복됨

### 4-2. 현재 해결 방식

- `MangaOcr()` 인스턴스를 stage config에 캐시해 OCR stage 내에서 1회만 생성한다.
- CRAFT region을 OCR 전에 merge해서 crop 수를 줄인다.
- 기본 padding을 `12px`로 두어 너무 타이트한 crop을 피한다.

관련 metadata:

```text
region_count
ocr_region_count
merged_region_count
max_source_regions_per_block
```

해석:

- `region_count == ocr_region_count`: merge가 거의 먹지 않은 상태다. `merge_gap_px`를 늘리거나 overlap 기준을 조정한다.
- `ocr_region_count`가 너무 작음: 서로 다른 말풍선까지 과하게 합쳐졌을 수 있다. `merge_gap_px`를 줄인다.
- 한두 글자 블록이 많음: 아직 over-segmentation일 가능성이 높다.

## 5. 번역 결과가 이상할 때

번역 결과만 보고 번역 모델 문제로 판단하지 않는다.
먼저 OCR artifact의 `source_lang_text`를 확인한다.

확인 순서:

1. `ocr-sample`만 실행한다.
2. `ocr_text_blocks.json`에서 `source_lang_text`를 원본 이미지와 대조한다.
3. OCR 원문이 깨졌으면 번역 모델이 아니라 detection/OCR/merge/후처리 문제로 본다.
4. OCR 원문이 정상인데 번역만 이상하면 OpenAI-compatible/Vertex translation adapter와 prompt를 본다.

번역은 현재 OCR block들을 모아서 한 번의 LLM 요청으로 처리한다.
즉 블록마다 LLM을 호출하는 구조는 아니다.

## 6. 현재까지 반영된 내용

- OCR stage에서 `MangaOcr()` recognizer를 region마다 새로 만들지 않고 stage 내에서 재사용한다.
- detection region을 OCR 전에 merge하고 기본 padding을 늘려 말풍선/문장 단위 crop 가능성을 높였다.
- 세로쓰기 일본어 만화 기준 `reading_order_mode=vertical_rtl` 정렬을 추가했다.
- density / area / small-region-long-text 규칙으로 환각 의심 OCR block을 `style_hint.ocr_status=needs_review`로 마킹한다.
- 모든 OCR block에 `ocr_text_density_per_1000_px2`, `ocr_region_area_px`, `ocr_text_length`를 남겨 threshold 튜닝 근거를 확보했다.
- translation backend 기본 경로를 OpenAI-compatible로 정리했고, LM Studio / Ollama / custom proxy를 같은 contract로 받도록 했다.
- translation은 선행 detect/OCR 결과의 page block 전체를 한 번의 LLM 요청으로 batch translation 한다.
- local 실행용 provider 설정은 `.runtime/runtime_config.json`으로 분리하고 Git ignore 상태로 유지한다.

## 7. 아직 해결해야 하는 내용

### OCR 쪽

- 실제 샘플 여러 장에서 `max_text_density_per_1000_px2`와 `ocr_region_area_px` 분포를 수집해 threshold를 더 안정화
- `needs_review` block만 crop debug image로 저장하는 옵션 추가
- `small_region_long_text` 규칙을 UI 텍스트 / 손글씨 / 효과음 기준으로 세분화
- `manga-ocr` 내부 logits 기반 confidence 또는 대체 quality score 조사
- merge 규칙을 단순 bbox 거리 기반에서 세로열 / 말풍선 단위에 더 맞게 조정
- UI에서 `style_hint.ocr_status == "needs_review"` block 강조 표시

### Translation / LLM 호출 쪽

- provider별 strict structured output 강제 강화
- fenced code block, prefix/suffix 설명문 등을 허용하는 JSON repair path 추가
- `block_id` 누락 시 positional fallback 의존도 축소 또는 제거
- OCR `needs_review`, `ocr_warnings`를 번역 prompt에 반영해 과도한 자연화 억제
- block 수가 많은 페이지용 chunking 정책 추가
- timeout, `429`, `5xx`, local warm-up 지연에 대한 retry/backoff 추가
- glossary / term map / 이름 고정 번역 규칙 추가
- provider별 응답 shape 편차 대응 보강
