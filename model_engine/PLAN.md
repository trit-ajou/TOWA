네. 지금 명세는 **핵심 아키텍처는 충분히 정리됐지만, 구현 착수 전에 반드시 더 박아야 하는 결정 항목이 아직 꽤 있습니다.**
즉, “방향은 확정”, “실행 규약은 일부 미확정” 상태로 보는 게 맞습니다.  

이미 확정된 축은 분명합니다.

* stage는 독립 process이고 orchestrator가 호출한다
* 내부 계약은 `document_ir + artifact_refs`
* 큰 비트맵은 외부 artifact로 분리한다
* custom stage는 입력은 유연, 출력 계약은 고정한다
* SaaS/local은 인증·정산만 다르고 내부 stage graph와 IR은 동일하다   

그 위에서, **지금 꼭 더 정해야 하는 것**을 우선순위 순으로 정리하면 아래입니다.

## 1. Stage graph 자체는 아직 덜 고정됐습니다

초기 문서에는 `bbox(detection) -> mask(segmentation) -> inpaint -> 번역`이라고 되어 있지만, 최근 정리문에는 `OCR / 텍스트 영역 감지 / 지우기 / 번역 / 식자 / 후처리`까지 확장되어 있습니다. 즉 “최소 4-stage”와 “실운영 full pipeline” 사이에 차이가 있습니다.  

그래서 먼저 아래를 고정해야 합니다.

* v1의 공식 stage 목록
* 각 stage의 선후관계
* 병렬 가능 stage와 반드시 직렬인 stage
* optional stage 여부

당장 주신 전제까지 반영하면, v1은 이렇게 못 박는 게 자연스럽습니다.

* `text_detection` = **CRAFT**
* `ocr` = 별도 확정 필요
* `mask/erase planning` = 확정 필요
* `inpaint` = **나노바나나 API**
* `translation` = 확정 필요
* `typesetting/layout` = 규칙 기반인지 모델 기반인지 확정 필요
* `postprocess` = 선택 stage 여부 확정 필요

즉 **CRAFT와 인페인팅은 정해졌지만, OCR/번역/식자 단계는 아직 스펙상 비어 있습니다.**

## 2. Detection과 OCR의 경계가 아직 불명확합니다

문서엔 `bbox(detection)`과 `OCR`가 둘 다 언급됩니다. 그런데 CRAFT는 보통 **텍스트 영역 검출**이지 텍스트 인식 자체는 아닙니다.
그래서 v1에서는 아래 둘 중 하나로 명확히 해야 합니다.

* **A안**: `CRAFT = text detection`, OCR은 별도 recognizer stage
* **B안**: detection+recognition을 하나의 composite stage로 묶음

지금 문서 방향상으론 **A안이 더 자연스럽습니다.** stage를 독립 process로 두고 patch/artifact 단위로 연결하는 구조이기 때문입니다. 

즉 정해야 하는 건:

* OCR 엔진이 무엇인지
* OCR 입력이 page raster인지 crop list인지
* OCR 출력이 plain text인지 text block 구조체인지
* 세로쓰기/말풍선 단위 grouping을 detection에서 할지 OCR 후처리에서 할지

## 3. Stage I/O schema는 개념만 있고 필드가 아직 덜 잠겼습니다

정리문에는 input에 `document`, `artifacts`, `runtime_context`, output에 `status`, `patches`, `stage_report`가 있다고 설명하지만, **정확한 JSON schema는 아직 확정본이 아닙니다.** 

반드시 더 정해야 하는 필드는 이겁니다.

입력:

* `job_id`
* `pipeline_id`
* `stage_name`
* `document`
* `artifacts`
* `stage_config`
* `runtime_context`
* `selected_layer_ids` 또는 `target_regions`
* `cancellation_token` 지원 여부

출력:

* `status`
* `patches`
* `new_artifacts`
* `stage_report`
* `snapshot` 허용 여부
* `partial_failure` 표현 방식

특히 **patch만 허용할지, snapshot 반환도 허용할지**는 꼭 못 박아야 합니다. 문서상 “patch 또는 새 문서 스냅샷”으로 열려 있어서, 구현 들어가면 금방 흔들립니다. 

제안은 이렇습니다.

* 기본: **patch-only**
* 예외: import/export 계열이나 대규모 normalization stage만 snapshot 허용

## 4. IR Patch op 집합이 아직 완전히 닫히지 않았습니다

현재는 `add_layer`, `replace_source_ref` 같은 예시만 있고, 실제 허용 op 목록은 안 닫혔습니다. 

이건 반드시 먼저 닫아야 합니다. 최소한 v1에서는 아래 정도가 필요합니다.

* `add_layer`
* `remove_layer`
* `update_layer_props`
* `replace_source_ref`
* `replace_mask_ref`
* `append_text_blocks`
* `replace_text_blocks`
* `set_filters`
* `set_selection`
* `set_stage_meta`

이걸 안 닫으면 custom stage가 제각각 patch를 만들게 됩니다.

## 5. Artifact registry 규약이 아직 운영 수준으로는 부족합니다

문서에는 artifact가 `artifact_ref -> uri` 매핑, checksum 검증, GC를 한다고 되어 있지만, 실제 구현에 필요한 운영 규칙은 더 있어야 합니다. 

추가 확정이 필요한 항목:

* `artifact_ref` 네이밍 규칙
* 로컬 URI와 SaaS URI 스킴
* checksum 알고리즘
* artifact immutability 여부
* TTL/GC 정책
* stage 실패 시 partial artifact 보존 규칙
* rollback 때 어떤 artifact를 폐기하는지
* temp artifact와 durable artifact 구분

특히 나노바나나 API를 쓰면 결과 이미지가 **외부 API 응답으로 생성**될 텐데, 그 결과를 내부에서 어떤 artifact로 표준화할지 미리 정해야 합니다.

권장:

* stage는 항상 **새 artifact_ref**만 발급
* orchestrator가 registry commit/cleanup 담당
* local은 `file://`, SaaS는 object storage URI를 기본 스킴으로 사용

추가로 v1에서 아래를 고정합니다.

* local file artifact는 transaction 단위 경로 아래 저장
* 기본 경로 형식은 `{workspace}/transactions/{pipeline_id}/{stage_name}/{stage_run_id}/`
* transaction 종료 전까지 산출물 정리는 orchestrator 책임

## 6. 나노바나나 API stage의 계약을 별도 정의해야 합니다

인페인팅 모델이 “내부 로컬 모델”이 아니라 “외부 API”로 정해졌으니, 이 stage는 일반 로컬 worker와 성격이 다릅니다. 엔진 간 구조 문서도 모델 엔진이 외부 API를 직접 호출하는 경로를 전제합니다.

그래서 따로 정해야 합니다.

* 입력 포맷: 원본 이미지, 마스크, 프롬프트, style config
* 동기 호출인지 비동기 polling인지
* timeout/retry 정책
* rate limit/429 처리
* provider 실패 시 `stage_report.error_code` 표준
* 결과가 base64인지 URL인지 바이너리인지
* provider 응답 메타데이터를 얼마나 보존할지

즉 **나노바나나 API adapter spec**이 필요합니다.

현재 v1에서 아래를 고정합니다.

* 나노바나나 결과는 원본과 병합하지 않고 새 `inpainting layer` 결과물로 유지
* 결과물 전송도 레이어 단위 기준으로 간다
* provider hang/timeout은 `failed`로 처리하고 snapshot은 남긴다

## 7. CRAFT stage 출력 포맷도 고정해야 합니다

CRAFT를 쓰기로 한 건 좋지만, CRAFT가 내는 raw 결과를 다음 stage가 그대로 먹게 하면 안 됩니다.
다음 중 어떤 표준 출력으로 변환할지 정해야 합니다.

* polygon list
* rotated bbox list
* line/block hierarchy
* bubble association 여부
* confidence thresholding 규칙

권장은 **raw detection 결과를 바로 넘기지 말고**, `text_regions`라는 정규화된 구조체로 patch나 stage artifact에 담는 겁니다.

예:

* `region_id`
* `polygon`
* `bbox`
* `confidence`
* `reading_order`
* `bubble_id?`

이걸 안 정하면 이후 OCR/번역/식자 단계가 흔들립니다.

추가로 v1 방향을 아래로 고정합니다.

* `text_regions`는 바로 provider에 넘기지 않음
* `mask_or_erase_planning`이 `text_regions -> crop task` 변환 담당
* 나노바나나 API는 crop 단위 inpaint만 수행
* 결과는 항상 `inpainting layer`에만 합성
* 원본 페이지 레이어는 직접 수정하지 않음

## 8. OCR/번역/식자용 text block schema가 아직 없습니다

UI는 기본 편집 화면에서 “원문/번역문 쌍 + 레이어 토글”을 다루게 되어 있습니다. 즉 모델 엔진도 text block을 단순 문자열이 아니라 **문서 내 객체**로 다뤄야 합니다. 

필요한 최소 스키마:

* `block_id`
* `source_lang_text`
* `translated_text`
* `polygon` / `bbox`
* `reading_order`
* `speaker` optional
* `style_hint`
* `font_hint`
* `writing_mode` horizontal/vertical
* `source_region_ref`

이건 아직 문서에 직접 닫혀 있지 않습니다.

## 9. Selection/runtime-only 데이터 보존 규칙이 더 구체화돼야 합니다

현재는 “runtime-only selection은 IPC/persistence에서 최소화” 수준입니다. 맞는 방향이지만, 실제론 세 단계로 나눠야 합니다. 

* UI 왕복에 필요한 persistent selection
* stage chaining에만 필요한 transient selection
* stage 내부에서만 쓰고 폐기할 ephemeral cache

이걸 안 나누면 selection 데이터가 artifact registry에 섞여 들어가거나, 반대로 UI 복귀 시 필요한 정보가 사라집니다.

## 10. 실패 처리와 rollback 규칙이 아직 추상적입니다

문서엔 “rollback 또는 실패 상태 봉인”, “부분 산출물과 오류 메타데이터 반환”이 있지만, 어떤 경우 rollback하고 어떤 경우 partial commit할지는 안 정해져 있습니다. 

정해야 할 것:

* stage failure 시 전체 job fail인지
* optional stage failure는 경고만 남길지
* 이미 생성된 artifact의 보존/삭제
* UI에 중간 결과를 보여줄지
* SaaS에서 어느 시점에 capture/release 할지

특히 외부 API가 낀 인페인팅은 timeout/partial failure가 자주 생길 수 있어서 이 부분이 중요합니다.

현재 v1에서는 아래를 기본 규칙으로 고정합니다.

* 나노바나나가 멈추면 `partial`이 아니라 `failed`
* 대신 task/input/output snapshot은 transaction 경로 아래 보존 가능

## 11. Local/SaaS 공통 규칙은 좋지만, provider credential 모델은 더 정해야 합니다

문서상 local에서는 사용자 개인 API 키를 모델 엔진에 넣고, SaaS에서는 TOWA 서비스의 API 키를 모델 엔진이 사용합니다. 이 큰 방향은 분명합니다.

그런데 구현 레벨에서는 아래가 더 필요합니다.

* stage별 provider credential source
* local credential 저장 위치
* key rotation 시 반영 방식
* stage_report에 provider name/version 남길지
* personal API와 platform credit 혼용 시 우선순위

특히 “인페인팅은 나노바나나 API”로 정한 이상, 이 credential model은 빨리 박아야 합니다.

## 12. UI 반환 포맷도 아직 완전히 닫히지 않았습니다

엔진 간 문서엔 모델 엔진이 UI에 “결과 파일(자체 포맷)”을 반환한다고만 되어 있고, UI 문서도 “자체 포맷 사용, 상세 스펙은 추후 설계”라고 되어 있습니다.

즉 아직 미정입니다.

* UI로 반환하는 최종 포맷이 내부 canonical IR과 같은지
* export 시 `.bpy` 변환이 필요한지
* basic editor용 경량 포맷과 detail editor용 포맷이 같은지
* bitmappery embed 전/후 호환 방식

이건 model_engine과 UI_engine의 접점이라 조기에 정해야 합니다.

---

# 결론

지금 명세에서 **아직도 정확히 정해지지 않은 부분은 분명히 있습니다.**
하지만 비어 있는 부분은 “아키텍처를 다시 고민해야 하는 공백”이 아니라, **이제 구체 schema와 운영 규칙으로 닫아야 하는 공백**입니다. 

주신 전제를 반영하면, 현재 확정 가능한 것과 즉시 결정해야 할 것을 이렇게 나누면 됩니다.

## 이미 확정 가능

* 내부 IR은 `document_ir + artifact_refs`
* stage는 독립 process
* orchestrator가 실행/검증/수명주기 관리
* text detection은 **CRAFT**
* inpainting은 **나노바나나 API**
* local/SaaS는 내부 stage contract 동일

현재 이 확정 항목 중 이미 코드로 내려간 것:

* built-in `text_detection=CRAFT`
* 규칙 기반 `mask_or_erase_planning`
* built-in `inpaint=나노바나나(Vertex AI 경유)`
* crop 단위 inpaint 후 `inpainting layer` 합성

## 현재도 더 정해야 하는 것

* OCR 엔진과 OCR 출력 schema
* translation/typesetting/postprocess stage 정의
* Stage I/O JSON schema
* IR patch op 목록
* artifact registry lifecycle
* failure/rollback/capture-release 정책
* UI 반환용 최종 파일 포맷

제가 한 줄로 정리하면 이겁니다.

**지금은 “공통 계약층 + 첫 built-in stage 구현”까지 왔고, 다음 핵심은 OCR/번역/식자와 실제 provider smoke run을 닫는 단계입니다.**
