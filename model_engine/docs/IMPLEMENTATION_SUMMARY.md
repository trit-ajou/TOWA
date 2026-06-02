# model_engine Implementation Summary

이 문서는 현재 `model_engine`에 실제로 구현된 사항만 빠르게 정리한 요약본이다.
설계 초안, 추후 검토 항목, 환경 삽질 이력은 제외하고 "지금 동작하는 것"만 적는다.

## 1. 현재 구현 완료 범위

현재 `model_engine`은 아래 범위를 구현했다.

- Bitmappery 의미론 기반 canonical IR
- 고정 patch 계약과 patch 적용기
- artifact registry와 transaction-scoped file storage
- stage request/response/report 계약
- 순차 orchestrator
- subprocess IPC stage 실행
- credential binding / local-SaaS key resolution
- model manifest / adapter / registry 기반 모델 병합 구조
- custom model loader
  - `python_callable`
  - `http_api`
- built-in `text_detection=CRAFT`
- 규칙 기반 `mask_or_erase_planning`
- built-in `inpaint=nanobanana`
- placeholder `job API`
  - `POST /v1/jobs`
  - `GET /v1/jobs/{job_id}`
  - in-memory job lifecycle
  - swappable executor interface
- `service_engine` 연동 smoke billing
  - `saas` 모드 hold/capture/release
  - CORS 허용

## 2. 현재 동작하는 built-in pipeline

현재 기본 샘플 파이프라인은 아래 순서로 동작한다.

1. `text_detection`
2. `mask_or_erase_planning`
3. `inpaint`

세부 역할은 다음과 같다.

- `text_detection`
  - CRAFT가 원본 페이지에서 텍스트 영역을 검출한다.
  - 결과는 `text_regions` artifact로 저장된다.

- `mask_or_erase_planning`
  - `text_regions`를 바탕으로 erase mask와 `inpaint_tasks`를 만든다.
  - 이 mask는 provider에 보내는 입력이 아니라 로컬 합성 기준 마스크다.

- `inpaint`
  - 나노바나나 provider에는 원본 페이지 전체 이미지를 1회 전달한다.
  - provider가 돌려준 전체 결과 이미지에서 planner mask 영역만 취해
    새 `inpainting layer` bitmap으로 합성한다.
  - 원본 페이지 bitmap은 수정하지 않는다.

## 3. 현재 결과물 구조

현재 파이프라인 결과는 transaction 경로 아래에 정리된다.

- 기준 경로
  - `{workspace}/transactions/{pipeline_id}/{stage_name}/{stage_run_id}/`

대표 산출물은 다음과 같다.

- CRAFT 결과
  - `.../text_detection/..._text_regions.json`

- planner 결과
  - `.../mask_or_erase_planning/..._inpaint_tasks.json`
  - `.../mask_or_erase_planning/..._mask_0001.png`

- inpaint 결과
  - `.../inpaint/..._provider_output.png`
  - `.../inpaint/..._inpainting.png`

실패 시에는 아래도 남는다.

- `.../inpaint/..._partial_inpainting.png`
- `.../inpaint/..._failure_snapshot.json`

## 4. 현재 inpaint 결과 의미

현재 `inpaint` stage는 결과를 원본과 병합하지 않는다.

- provider가 만든 전체 페이지 결과는 `provider_output_bitmap` artifact로 남긴다.
- 최종 반영본은 mask 영역만 취한 `inpainting_layer_bitmap` artifact다.
- 문서에는 `layer_inpainting` 레이어만 추가하거나 갱신한다.

즉 비교 가능한 비트맵은 세 가지다.

- 원본 입력 페이지
- provider 전체 출력 페이지
- 최종 `inpainting layer`

## 5. 실행 경로

현재 기본 실행 경로는 Docker Compose 기준이다.

- CRAFT preload
  - `docker compose -f docker-compose.inference.yml run --rm craft-preload`

- CRAFT sample
  - `docker compose -f docker-compose.inference.yml run --rm craft-sample`

- inpaint sample
  - `docker compose -f docker-compose.inference.yml run --rm inpaint-sample`

## 6. Placeholder Job API

현재 통신 smoke 목적의 placeholder job API가 추가되어 있다.

- `POST /v1/jobs`
- `GET /v1/jobs/{job_id}`

의도는 다음과 같다.

- `UI engine`과 실제 HTTP contract를 먼저 맞춘다.
- 내부 실행부는 placeholder로 두되, 나중에 실제 orchestrator로 교체하기 쉽게 만든다.

현재 구현 포인트:

- `JobExecutor` 인터페이스를 두고 기본 구현은 `PlaceholderJobExecutor`를 사용한다.
- job 저장소는 in-memory다.
- lifecycle은 `queued -> running -> succeeded|failed|partial`이다.
- operation별 placeholder stage는 아래처럼 고정했다.
  - `detect` -> `text_detection`, `ocr`
  - `inpaint` -> `text_detection`, `mask_or_erase_planning`, `inpaint`
  - `translate` -> `translation` (`document.text_blocks`에 선행 detect/OCR 결과가 들어와야 함)
  - `pipeline` -> 현재 `422 model_validation_error`
- placeholder 결과는 문서와 artifact shape를 최대한 유지하고, `stage_reports`와 상태 전이만 채운다.

## 7. Service Billing 연동 메모

`runtime_context.mode=saas`인 경우 `model_engine`은 실제 `service_engine` billing API를 호출한다.

순서는 아래와 같다.

1. `POST /usage/jobs`
2. 성공 시 `POST /usage/jobs/{job_id}/capture`
3. 실패 시 `POST /usage/jobs/{job_id}/release`

현재 `service_engine` usage enum은 `mask|translate|inpaint`만 받는다.
그래서 `model_engine`의 `detect` 작업은 service billing 호출 시 임시로 `mask`로 매핑한다.

이 매핑은 2026-03-29 라이브 smoke test에서 실제 `422`를 확인한 뒤 반영한 런타임 호환 규칙이다.
service 쪽 public enum이 바뀌면 이 임시 매핑은 제거 가능하다.

## 8. 테스트 상태

현재 검증 상태:

- `python3 -m unittest discover -s model_engine/tests -v`
- `python3 -m unittest model_engine.tests.test_job_api -v`
- 총 `32` tests passed

주요 검증 항목:

- IR patch 적용
- artifact lifecycle
- credential resolution
- orchestrator 순차 실행
- IPC stage 실행
- model registry / custom model 로딩
- CRAFT `text_regions` 생성
- planner mask/task 생성
- nanobanana 전체 페이지 출력 + 로컬 mask 합성
- provider output resize normalization
- failure snapshot 보존
- placeholder job lifecycle
- `saas` billing capture/release
- CORS preflight
- `detect -> mask` billing 매핑

추가 live smoke 결과:

- `service_engine` dev login 후 `saas detect` job을 생성하면 `queued -> succeeded`까지 완료된다.
- 실제 credit은 `1000 -> 995`로 차감되는 것을 확인했다.
- `local translate`도 `queued -> succeeded`로 완료된다.

## 9. 아직 미구현인 범위

현재 아직 남아 있는 주요 항목은 아래다.

- OCR stage
- translation stage
- typesetting stage
- postprocess stage
- durable artifact backend
- UI 컴포넌트 실제 wiring
- provider별 운영 정책 고도화
