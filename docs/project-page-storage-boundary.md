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

### Folder

folder는 library tree의 server-side entity다.

- `id`
- `name`
- `parent_id`
- `path`
- `created_at`
- `updated_at`
- `deleted_at`

규칙:

- folder id는 service가 생성한 UUID다
- `path`는 표시용 derived field이며, UI 작업은 id 기준으로 수행한다
- 같은 부모 아래 같은 이름의 live folder는 허용하지 않는다
- trash 상태는 `deleted_at`으로 표현한다

### Project

project는 library와 project view에 필요한 메타데이터다.

- `id`
- `name`
- `thumbnail_url`
- `source_lang`
- `target_lang`
- `page_count`
- `status`
- `folder_id`
- `folder_path`
- `config`
- `created_at`
- `updated_at`
- `deleted_at`

규칙:

- `config`는 service 기준 opaque JSON이다
- `page_count`는 서버가 pages 수를 기준으로 계산하는 read-only 필드다
- `thumbnail_url`은 nullable opaque string이다
- root project는 `folder_id=null`, `folder_path=null`이다
- 대표 cover 선택 규칙은 `UI engine`이 결정하고, `service_engine`은 저장/반환만 한다

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
- `thumbnail_url`은 private service fetch URL이다

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
- page create는 append-only다
- 첫 저장도 `layer_blob`을 포함한 complete snapshot이어야 한다

### Load

`GET /api/v1/pages/{page_id}/snapshot`
`GET /api/v1/pages/{page_id}/thumbnail`

응답 형식:

- snapshot: `Content-Type: multipart/mixed`
- thumbnail: `Content-Type: image/webp`

part names는 save와 동일하다.

thumbnail fetch 규칙:

- `thumbnail_url`은 bearer 인증이 필요한 private service URL이다
- service는 저장/조회 시 thumbnail을 max width 512px, quality 80 기준 손실 WebP로 정규화한다
- `original_image`는 WebP 변환 없이 업로드 bytes를 그대로 보존한다
- 대표 project cover용 `project.thumbnail_url`은 별도 project metadata 필드다

## Ownership Boundaries

`service_engine`이 하는 일:

- auth/session 검사
- project/page ownership 검사
- folder tree CRUD, trash, restore, permanent delete
- snapshot 저장/조회
- page summary 생성
- page thumbnail binary 제공
- append-only page create 검증
- page delete 후 dense index 유지

`service_engine`이 하지 않는 일:

- bitmappery document 파싱
- text layer sync
- AI 결과 merge
- export 포맷 생성
- project cover 선택 규칙 결정
- project cover 깨짐 복구 자동화
- folder tree depth 제한 결정

`UI engine`이 하는 일:

- page snapshot 생성/직렬화
- page snapshot 복원
- AI 결과를 현재 page state에 적용
- auto-save, page switch flush, reconnect 재시도

## Standalone / Cloud Alignment

standalone과 cloud는 같은 logical 모델을 공유한다.

- 둘 다 folder entity, project metadata, page summary, full page snapshot이라는 같은 개념을 쓴다
- 차이는 backing store뿐이다
  - standalone: IndexedDB
  - cloud: service API

즉, `FileAdapter`는 저장 위치만 다르고 같은 logical page snapshot을 다뤄야 한다.

## Current v1 Notes

- `project.id`, `page.id`는 UI가 생성한 canonical ULID string을 사용한다
- `folder.id`는 service가 생성한 UUID string을 사용한다
- 기본 project/folder 조회는 live item만 반환하며, trash metadata는 `GET /api/v1/trash`에서 조회한다
- page create는 `metadata.page.index == current page_count + 1`일 때만 허용한다
- page delete는 hard delete이며 뒤 page들의 `index`를 당겨 항상 dense `1..N`을 유지한다
- snapshot binary backend는 현재 DB BLOB이다
- 허용 media type은 `image/jpeg`, `image/png`, `image/webp`, `application/octet-stream`이다
- storage GET은 `ETag`, `Last-Modified`, `Cache-Control: private, no-cache`를 제공하고 변경 없을 때 `304 Not Modified`를 반환한다
- JSON/text 응답은 Brotli/Zstd 압축 대상이며 snapshot multipart와 image 응답은 압축하지 않는다
