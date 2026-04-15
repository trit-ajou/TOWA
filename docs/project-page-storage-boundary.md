# Project/Page Storage Boundary v1

cloud 모드의 `project/page` 저장 경계를 정리한다.
핵심 원칙은 `service_engine`이 cloud persistence authority를 가지되, page 내부 편집 semantics는 해석하지 않는다는 점이다.

## Summary

- 저장 authority:
  - standalone: `UI engine` 내부 IndexedDB
  - cloud: `service_engine`
- logical 저장 단위:
  - project metadata
  - page summary
  - full page snapshot
- `page summary`와 `page snapshot`은 분리한다
- page save는 `full replace + last-write-wins`다

## Logical Model

### Project

project는 library와 project view에 필요한 메타데이터다.

- `id`
- `name`
- `source_lang`
- `target_lang`
- `page_count`
- `status`
- `folder`
- `config`
- `created_at`
- `updated_at`

규칙:

- `config`는 service 기준 opaque JSON이다
- `page_count`는 서버가 pages 수를 기준으로 계산하는 read-only 필드다

### Page Summary

project view용 lightweight 목록이다.

- `id`
- `project_id`
- `index`
- `status`
- `thumbnail_url`
- `updated_at`

규칙:

- 페이지 목록 조회는 summary만 반환한다
- full `textBlocks`, original image, layer blob은 포함하지 않는다

### Full Page Snapshot

편집 진입과 저장의 authoritative unit이다.

구성:

- JSON metadata
  - page id/project_id/index/status
  - `textBlocks`
- binary
  - `original_image`
  - `layer_blob`
  - `thumbnail`

`TextBlock` 규칙:

- `bbox`는 `{ x, y, width, height }`
- `textBlocks`는 구조화된 JSON으로 저장한다
- source of truth와 bitmappery text layer sync 정책은 이 문서 범위 밖이다

`layer_blob` 규칙:

- bitmappery `DocumentFactory.toBlob()` 결과를 opaque binary로 저장한다
- service는 blob 내부를 해석하지 않는다

`original_image` 규칙:

- immutable asset가 아니다
- 현재 page snapshot의 일부이며 교체 가능하다

## Transport

### Save

`POST /api/v1/projects/{project_id}/pages`
`PUT /api/v1/pages/{page_id}/snapshot`

요청 형식:

- `Content-Type: multipart/form-data`

part names:

- `metadata`
- `original_image`
- `layer_blob`
- `thumbnail`

원칙:

- create/save 모두 complete snapshot을 보낸다
- partial page update는 지원하지 않는다

### Load

`GET /api/v1/pages/{page_id}/snapshot`

응답 형식:

- `Content-Type: multipart/mixed`

part names는 save와 동일하다.

## Ownership Boundaries

`service_engine`이 하는 일:

- auth/session 검사
- project/page ownership 검사
- snapshot 저장/조회
- page summary 생성

`service_engine`이 하지 않는 일:

- bitmappery document 파싱
- text layer sync
- AI 결과 merge
- export 포맷 생성

`UI engine`이 하는 일:

- page snapshot 생성/직렬화
- page snapshot 복원
- AI 결과를 현재 page state에 적용
- auto-save, page switch flush, reconnect 재시도

## Standalone / Cloud Alignment

standalone과 cloud는 같은 logical 모델을 공유한다.

- 둘 다 project metadata, page summary, full page snapshot이라는 같은 개념을 쓴다
- 차이는 backing store뿐이다
  - standalone: IndexedDB
  - cloud: service API

즉, `FileAdapter`는 저장 위치만 다르고 같은 logical page snapshot을 다뤄야 한다.
