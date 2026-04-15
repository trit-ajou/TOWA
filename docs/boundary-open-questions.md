# Boundary Open Questions v1

v1 boundary 문서에서 일부 전제는 이미 고정했고, 일부 항목은 의도적으로 미뤘다.
이 문서는 구현 전에 합의가 필요한 질문을 추적하는 backlog다.

관련 문서:

- [http-contract.md](http-contract.md)
- [service-engine-boundary.md](service-engine-boundary.md)
- [project-page-storage-boundary.md](project-page-storage-boundary.md)
- [ui-model-abstract-boundary.md](ui-model-abstract-boundary.md)

## Already Fixed

아래 항목은 현재 기준으로 다시 열지 않는다.

- cloud의 `project/page` 저장 authority는 `service_engine`이다
- page 저장 단위는 자산별 분해가 아니라 `full page snapshot`이다
- `page summary`와 `page snapshot`은 분리한다
- page save 정책은 `full replace + last-write-wins`다
- `original_image`는 immutable asset가 아니라 현재 page snapshot의 일부이며 교체 가능하다
- `UI engine <-> model engine` 상세 wire shape는 이번 단계에서 canonical contract로 고정하지 않는다
- `model engine -> service engine` 직접 통신 범위는 auth/usage다

## Storage And Project Questions

### 1. ID Authority

질문:

- `project.id`, `page.id`는 누가 생성하는가
- UI의 client-generated id를 표준으로 둘 것인가
- id format에 제약을 둘 것인가

왜 필요한가:

- create API의 validation과 conflict 처리 규칙이 여기서 결정된다

결정 필요 항목:

- authority: `UI engine` 또는 `service_engine`
- format: UUID, ULID, custom string 등

### 2. Page Ordering

질문:

- `page.index`는 삭제/삽입 시 재정렬하는가
- 중간 hole을 허용하는가
- drag reorder를 v1 범위에 넣는가

왜 필요한가:

- `GET /projects/{project_id}/pages` 정렬 규칙과 삭제 후 후처리가 달라진다

### 3. Project Status Semantics

질문:

- `project.status`는 사용자 편집값인가
- 아니면 page 상태들의 집계 결과인가

왜 필요한가:

- `PATCH /projects/{project_id}`에서 `status`를 writable로 둘지 결정해야 한다

### 4. Page Status Authority

질문:

- `page.status` 전이 authority는 누구인가
- UI가 상태를 계산해서 저장만 하는가
- service가 일부 validation을 하는가

왜 필요한가:

- page snapshot metadata validation 범위가 달라진다

## Snapshot Contract Questions

### 5. Complete Snapshot Strictness

질문:

- `POST /pages`, `PUT /snapshot`에서 `metadata`, `original_image`, `layer_blob`, `thumbnail` 네 part를 항상 모두 요구하는가
- 첫 저장 시 `layer_blob`이 아직 없으면 empty blob을 보내는가
- 아니면 layer-less snapshot을 허용하는가

왜 필요한가:

- multipart parser와 request validation을 strict path로 설계하려면 명확해야 한다

### 6. Thumbnail Fetch Contract

질문:

- `thumbnail_url`은 service proxy URL인가
- presigned/object URL인가
- 로그인 세션이 필요한 private URL인가

왜 필요한가:

- page list 응답 shape는 이미 잡았지만 thumbnail fetch 인증 모델은 아직 열려 있다

현재 문서 기본값:

- `thumbnail_url`은 fetch 가능한 opaque URL

### 7. Binary Storage Backend

질문:

- snapshot binary를 DB BLOB으로 저장하는가
- object storage에 두고 DB에는 metadata/path만 저장하는가

왜 필요한가:

- 이건 public contract보다 구현 전략 문제지만 migration, infra, size limit에 직접 영향이 있다

### 8. Upload Limits And Media Validation

질문:

- `original_image`, `thumbnail`의 허용 media type은 무엇인가
- 최대 업로드 크기는 얼마인가
- `layer_blob` 최대 크기 제한을 둘 것인가

왜 필요한가:

- 서버 보호와 오류 응답 규칙을 미리 정해야 한다

### 9. Delete Semantics

질문:

- page 삭제 후 `project.page_count`만 갱신하면 되는가
- 뒤 page들의 `index`를 당겨야 하는가
- soft delete가 필요한가

왜 필요한가:

- delete endpoint 구현과 project summary consistency에 영향이 있다

### 10. Snapshot Load Transport Final Check

질문:

- `GET /pages/{page_id}/snapshot` 응답을 정말 `multipart/mixed`로 갈 것인가
- 아니면 `metadata JSON + binary URL들` 구조로 단순화할 것인가

왜 필요한가:

- 브라우저 구현 난이도와 캐시 전략이 달라진다

현재 문서 기본값:

- `multipart/mixed`

## UI / Model Questions

### 11. Canonical UI/Model Contract Owner

질문:

- UI/model 상세 wire contract는 누가 최종 owner인가
- 합의 후 어느 문서에 canonical하게 기록할 것인가

왜 필요한가:

- 지금은 의도적으로 미뤘지만, 구현이 시작되면 계약 drift가 생기기 쉽다

권장:

- 합의 후 `docs/http-contract.md`에 canonical section을 추가하거나 별도 `docs/ui-model-contract.md`를 만든다

### 12. Job Input Shape

질문:

- model에 보내는 입력이 full page snapshot인가
- Document IR인가
- artifact reference 조합인가
- textBlocks와 layer_blob 중 어느 쪽이 AI 입력의 source of truth인가

왜 필요한가:

- detect, inpaint, translate의 request schema가 여기서 갈린다

### 13. Job Result Shape

질문:

- model 결과가 full page replacement인가
- patch set인가
- artifact set인가
- UI가 merge해야 할 최소 단위는 무엇인가

왜 필요한가:

- "AI 결과를 받은 뒤 최종 저장은 UI"라는 원칙은 고정됐지만, merge 단위는 아직 미정이다

### 14. Binary Handoff Method

질문:

- UI와 model 사이 바이너리를 직접 HTTP body로 주고받는가
- presigned URL을 쓰는가
- 별도 artifact store를 두는가

왜 필요한가:

- payload size, timeout, serverless 적합성이 크게 달라진다

### 15. Async Job Lifecycle

질문:

- job 생성 후 polling만 지원하는가
- cancel이 필요한가
- result retention TTL은 얼마인가

왜 필요한가:

- `/v1/jobs/{job_id}` persistence와 cleanup 정책이 필요하다

## UI Behavior Questions

### 16. Autosave Concurrency

질문:

- 같은 page에 연속 autosave가 들어오면 inflight 요청을 취소하는가
- 아니면 순차 queue를 유지하는가
- 최신 snapshot만 남기는 coalescing을 하는가

왜 필요한가:

- last-write-wins와 사용자 체감 안정성이 여기서 갈린다

### 17. Multi-Tab Policy

질문:

- 같은 사용자 멀티탭 동시 편집을 v1에서 허용하는가
- 허용한다면 정말 `last-write-wins`만으로 충분한가

왜 필요한가:

- conflict UX를 아예 생략할 수 있는지 결정해야 한다

### 18. Reconnect / Offline Replay Scope

질문:

- cloud에서 offline 동안 쌓인 save를 모두 replay하는가
- 마지막 snapshot 하나만 재전송하는가

왜 필요한가:

- UI 캐시 전략과 save queue 설계가 달라진다

## Suggested Decision Order

아래 순서로 정하면 구현 경로가 가장 빨리 닫힌다.

1. storage strictness
2. id authority
3. page ordering/delete semantics
4. thumbnail/auth fetch model
5. UI/model canonical doc owner
6. job input/result shape
7. binary handoff method
8. autosave/offline/multi-tab policy
