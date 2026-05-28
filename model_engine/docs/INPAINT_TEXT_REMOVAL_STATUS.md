# Inpaint Text Removal Status

## 현재 결론

현재 `inpaint` API job은 `text_detection -> mask_or_erase_planning -> inpaint` 3단계로 실행한다.

중요한 구분은 아래와 같다.

- provider i2i 호출에는 각 텍스트 박스 crop이나 mask를 따로 보내지 않는다.
- provider i2i 호출에는 원본 페이지 bitmap 1장을 통째로 보낸다.
- 텍스트 박스별 `inpaint_tasks`와 mask는 model-engine 내부 합성에만 사용한다.
- UI로 넘기는 최종 `inpainting_layer_bitmap`은 각 텍스트 region mask 영역만 불투명하고, 나머지는 투명한 PNG layer다.

즉 "각 텍스트 박스별로만 넘긴다"는 말은 provider 요청 기준으로는 아니다. UI에 붙는 최종 inpainting layer 기준으로는 맞다.

## 현재 요청/합성 흐름

1. `text_detection`
   - CRAFT로 페이지 전체에서 텍스트 region을 검출한다.
   - 현재 라이브 샘플 기준 region은 38개였다.

2. `mask_or_erase_planning`
   - 각 text region마다 `erase_mask` artifact와 `inpaint_tasks` entry를 만든다.
   - task 단위에는 `expanded_bbox`, `mask_artifact_ref`, `source_artifact_ref`, `target_layer_id`가 들어간다.

3. `inpaint`
   - Mindlogic/Imagen provider에는 원본 페이지 bitmap 1장만 보낸다.
   - provider에는 mask guide를 보내지 않는다.
   - provider raw output은 `provider_output_bitmap`으로 별도 보존한다.
   - UI용 `inpainting_layer_bitmap`은 provider raw output을 그대로 쓰지 않고, 내부 mask로 잘라낸 투명 layer로 만든다.

## 현재 설정

- provider: `mindlogic`
- model: `imagen-3.0-capability-001`
- endpoint: `/v1/api/google/models/edit-image`
- provider call mode: `full_page_single_call`
- provider reference image count: `1`
- provider mask guide: `no`
- UI composite mode: `mask_artifact`
- UI output mask dilation: `2px`
- local cleanup: `opencv_inpaint`

## 왜 local cleanup을 추가했나

라이브 샘플을 직접 확인했을 때, provider raw output은 큰 말풍선 텍스트는 지웠지만 휴대폰 화면 안의 작은 글자와 일부 효과음/손글씨를 그대로 복사했다.

그래서 mask 기반 inpaint 경로에서는 provider raw output을 보존한 뒤, UI용 합성 전에 CRAFT text mask를 OpenCV Telea inpaint로 한 번 더 정리한다.

이 cleanup은 provider raw artifact에는 적용하지 않는다. 최종 UI layer를 만들 때만 적용한다.

## 왜 expanded bbox를 기본으로 쓰지 않나

`expanded_bbox`는 원본 글자를 확실히 덮는 데는 유리하지만, 휴대폰 화면처럼 텍스트 주변에 실제 그림 정보가 많은 영역까지 과하게 덮었다.

현재 기본값은 `mask_artifact + output_mask_dilate_radius=2`다. 이 방식은 텍스트 획 주변만 좁게 덮어서 "오직 글자만 지우기" 목표에 더 가깝다.

## 라이브 확인 결과

비교 이미지:

- `model_engine/.runtime/live_inpaint_visual_check_final/comparison_grid.png`

관측값:

- `text_detection.region_count = 38`
- `mask_or_erase_planning.task_count = 38`
- `inpaint.composite_mask_mode = mask_artifact`
- `inpaint.output_mask_dilate_radius = 2`
- `inpaint.local_text_cleanup = opencv_inpaint`
- `inpaint.cleanup_mask_pixel_count = 131007`
- UI final layer alpha nonzero ratio는 약 `0.089`였다.

결과 품질:

- 큰 말풍선 글자는 대부분 제거됐다.
- provider가 복사하던 작은 글자도 local cleanup 이후 대부분 제거됐다.
- 다만 복잡한 배경 위의 작은 글자 영역에는 약간의 번짐이 남는다.
- UI에 넘기는 layer는 전체 페이지가 아니라 텍스트 mask 주변만 불투명하다.

## 관련 파일

- `model_engine/api/jobs.py`
  - API `inpaint` stage wiring과 `output_mask_mode`, `output_mask_dilate_radius` 설정.
- `model_engine/builtin_models/nanobanana_inpaint.py`
  - Mindlogic/Nanobanana provider 호출, provider raw artifact 저장, local cleanup, 최종 transparent layer 합성.
- `model_engine/stages/mask_or_erase_planning.py`
  - text region별 `erase_mask`와 `inpaint_tasks` 생성.
- `model_engine/tests/test_job_executor.py`
  - API inpaint가 detection/planning/inpaint를 타고 masked transparent layer를 만드는지 검증.
