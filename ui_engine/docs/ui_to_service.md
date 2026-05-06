# UI Engine → Service Engine: 파일 저장 API 명세

UI 엔진이 cloud 모드에서 사용하는 파일 저장/조회 API 명세.

> **상태**: 7주차에 SDK 측 구현 완료 (`towa-app/src/backend/`). service_engine 측 실 구현/통합 테스트 진행 중.

---

## 0. SDK 구조 (구현 완료)

### `AppBackend` 인터페이스 (`towa-app/src/backend/contracts.ts`)

```typescript
interface AppBackend {
  auth: AuthBackend         // 인증 (devLogin, getCurrentUser, logout)
  aiJobs: AiJobsBackend     // AI 작업 (createJob, getJob)
  files: FilesBackend       // 파일 저장 — 이 문서의 범위
}
```

### `FilesBackend` 인터페이스

```typescript
interface FilesBackend {
  // 프로젝트 CRUD
  listProjects(options): Promise<ProjectDto[]>
  getProject(projectId, options): Promise<ProjectDto>
  createProject(input, options): Promise<ProjectDto>
  updateProject(projectId, patch, options): Promise<ProjectDto>
  deleteProject(projectId, options): Promise<void>

  // 페이지 요약 목록 (썸네일 URL 포함)
  listPageSummaries(projectId, options): Promise<PageSummaryDto[]>

  // 페이지 snapshot CRUD (multipart)
  createPage(projectId, snapshot, options): Promise<PageSummaryDto>
  savePageSnapshot(pageId, snapshot, options): Promise<PageSummaryDto>
  getPageSnapshot(pageId, options): Promise<PageSnapshotPayload>
  deletePage(pageId, options): Promise<void>

  // 썸네일 (bearer-authed binary fetch)
  getPageThumbnail(pageId, options): Promise<Blob>
}
```

### snapshot 중심 설계

페이지 데이터(메타데이터 + 원본 이미지 + 레이어 blob + 썸네일)를 **snapshot 단위로 묶어서 multipart 한 번에** 처리한다. 초기 설계에서는 이미지/레이어/썸네일을 각각 별도 PUT으로 보낼 계획이었지만, 7주차 리팩터링에서 다음 이유로 통합:

- 페이지 저장이 원자적 (4파트가 모두 일관된 상태로 저장됨)
- 네트워크 왕복 1회로 감소
- 부분 실패 처리가 단순 (전체 저장 or 전체 실패)

### 구현 (`real.ts` / `emulated.ts`)

- `real.ts`: 실제 HTTP 호출. `buildSnapshotMultipart()` 헬퍼가 4파트 FormData를 구성, `parseMultipartMixed()`가 응답 파싱
- `emulated.ts`: 메모리 기반 stub (테스트/개발용)
- `requestJson()`, `requestBlob()`, `requestMultipart()` 등 공통 유틸리티

---

## 1. 배경

### 현재 상태

| 모드 | 저장소 | 상태 |
|------|--------|------|
| standalone | 브라우저 IndexedDB | **구현 완료** |
| cloud | 서버 DB/스토리지 | **서버 API + SDK 확장 필요** |

UI 엔진은 `FileAdapter` 인터페이스로 저장소를 추상화함.
standalone 모드는 `LocalFileAdapter` (IndexedDB)로 동작 중.
cloud 모드는 `CloudFileAdapter` (SDK의 `FilesBackend` 호출)를 만들면 되는데, 서버 API와 SDK 확장이 둘 다 필요.

### 아키텍처

```
UI (브라우저)
  ├── usePageLoader (bitmappery 캔버스 ↔ FileAdapter 연결)
  ├── useAutoSave (편집 후 30초 debounce 저장)
  ├── FileAdapter 인터페이스
  │     ├── LocalFileAdapter (IndexedDB) ← standalone, 구현 완료
  │     └── CloudFileAdapter             ← cloud, 아래 API 필요
  └── AppBackend (기존 SDK)
        ├── auth (구현 완료)
        ├── aiJobs (구현 완료)
        └── files (미구현 — 이 문서의 범위)
```

---

## 2. 데이터 모델

UI가 저장/조회하는 데이터는 3종류:

### 메타데이터 (JSON)

**ProjectRecord**
```typescript
{
  id: string             // "proj-1"
  name: string           // "원피스 1122화"
  sourceLang: string     // "ja"
  targetLang: string     // "ko"
  pageCount: number      // 19
  status: "todo" | "in-progress" | "done"
  folder: string         // "주간연재/점프"
  config: {
    autoDetect: boolean
    autoInpaint: boolean
    autoTranslate: boolean
    inferenceMode: "local" | "cloud"
  }
  createdAt: string      // ISO-8601
  updatedAt: string
}
```

**PageRecord**
```typescript
{
  id: string             // "proj-1-page-1"
  projectId: string      // "proj-1"
  index: number          // 1 (페이지 순서)
  status: "waiting" | "ai-processing" | "in-progress" | "done"
  textBlocks: TextBlock[]  // 텍스트 검출/번역 결과 (아래 참고)
}
```

**TextBlock**
```typescript
{
  id: string
  pageId: string
  bbox: { x, y, width, height }
  original: string       // 원문
  translated: string     // 번역문
  font: string
  fontSize: number
  color: string
  status: "detected" | "translated" | "edited"
}
```

### 바이너리 데이터 (Blob)

| 종류 | key | 내용 | 크기 (대략) |
|------|-----|------|-------------|
| 원본 이미지 | pageId | 사용자가 업로드한 만화 원본 (PNG/JPEG) | 1~5MB |
| 레이어 데이터 | pageId | bitmappery 편집 상태 직렬화 (lz-string 압축된 Blob) | 1~10MB |
| 썸네일 | pageId | 페이지 미리보기 (200×300 PNG) | 10~50KB |

**레이어 데이터**는 bitmappery의 `DocumentFactory.toBlob()` 결과물.
모든 레이어, 필터, 변환 정보를 포함하며 `DocumentFactory.fromBlob()`으로 완전 복원 가능.
서버 입장에서는 **opaque blob** — 내용을 해석할 필요 없이 그대로 저장/반환하면 됨.

---

## 3. 필요한 API 목록

### 3.1 프로젝트 CRUD

```
GET    /api/v1/projects/           → ProjectRecord[]
POST   /api/v1/projects/           → ProjectRecord (생성)
GET    /api/v1/projects/:id        → ProjectRecord
PUT    /api/v1/projects/:id        → ProjectRecord (수정)
DELETE /api/v1/projects/:id        → 204 (프로젝트 + 하위 페이지 전체 삭제)
```

### 3.2 페이지 CRUD

```
GET    /api/v1/projects/:pid/pages/          → PageRecord[] (index 순 정렬)
POST   /api/v1/projects/:pid/pages/          → PageRecord (생성)
GET    /api/v1/pages/:id                     → PageRecord
PUT    /api/v1/pages/:id                     → PageRecord (메타 수정)
DELETE /api/v1/pages/:id                     → 204 (페이지 + 관련 바이너리 전체 삭제)
```

### 3.3 페이지 snapshot (multipart)

**페이지 생성 + 저장: multipart 요청 1회로 통합**

```
POST   /api/v1/projects/:pid/pages/snapshot  → PageSummaryDto (생성)
PUT    /api/v1/pages/:id/snapshot            → PageSummaryDto (저장)
```

요청 본문 (`multipart/form-data`):

| 파트 | Content-Type | 내용 |
|------|--------------|------|
| `metadata` | `application/json` | `{ page: { id, projectId, index, status, textBlocks } }` |
| `original_image` | `image/png` 또는 `image/jpeg` | 원본 만화 이미지 (1~5MB) |
| `layer_blob` | `application/octet-stream` | bitmappery `DocumentFactory.toBlob()` 결과 (opaque, 1~10MB) |
| `thumbnail` | `image/png` | 캔버스 축소본 (10~50KB) |

서버 응답: `PageSummaryDto` (id, projectId, index, status, thumbnailUrl)

**페이지 조회: multipart/mixed 응답**

```
GET    /api/v1/pages/:id/snapshot            → multipart/mixed (4파트)
```

응답은 위 4파트와 동일한 구조의 `multipart/mixed`. UI에서 `parseMultipartMixed()`가 분해해서 `PageSnapshotPayload`로 복원.

**디자인 의도**: `layer_blob`은 서버 입장에서 **opaque** — 내용을 해석할 필요 없이 그대로 저장/반환. snake_case 필드명으로 서버 컨벤션과 정렬.

---

## 4. 서버 구현 방향 제안

### 저장소 구조

서버 입장에서 가장 단순한 구현: **DB + 파일 시스템 (또는 object storage)**

```
PostgreSQL (메타데이터)
├── projects 테이블 (ProjectRecord 그대로)
└── pages 테이블 (PageRecord, textBlocks는 JSONB)

파일 시스템 또는 S3 (바이너리)
└── /storage/
    └── {page_id}/
        ├── original.png    (원본 이미지, 1~5MB)
        ├── layers.bin      (bitmappery Blob, 1~10MB, opaque)
        └── thumbnail.png   (미리보기, 10~50KB)
```

- 메타데이터는 DB (쿼리 가능)
- 바이너리는 파일 시스템 또는 S3 (용량 효율)
- `layers.bin`은 서버가 내용을 알 필요 없음 — PUT으로 받은 것을 GET으로 그대로 돌려주면 됨

### 동시성 고려

현재는 단일 사용자 시나리오. last-write-wins로 충분.
향후 협업 기능 추가 시 페이지 단위 잠금(lock) 또는 optimistic concurrency (ETag/If-Match) 도입.

### 인증 연결

기존 `session_key` 기반 인증을 그대로 사용:
```
Authorization: Bearer <session_key>
```

프로젝트/페이지는 사용자 소유. 다른 사용자의 데이터에는 접근 불가.

---

## 5. UI ↔ 서버 데이터 흐름

### 프로젝트 열기 (편집 진입)

```
1. GET  /api/v1/projects/:id                         → 프로젝트 메타
2. GET  /api/v1/projects/:id/pages                   → 페이지 요약 목록 (썸네일 URL 포함)
3. GET  /api/v1/pages/:current/snapshot              → 현재 페이지 4파트 (multipart/mixed)
```

썸네일은 별도 fetch 없이 page summary의 URL로 `<img>` 직접 로딩.

### 편집 중 자동 저장 (30초 debounce)

```
PUT  /api/v1/pages/:id/snapshot                      → multipart 4파트 (전체 갱신)
```

레이어/썸네일이 동시에 갱신되므로 정합성 유지.

### 페이지 전환

```
1. PUT  /api/v1/pages/:current/snapshot              → 이전 페이지 저장
2. GET  /api/v1/pages/:next/snapshot                 → 새 페이지 로드
```

### 새 페이지 추가 (이미지 드래그앤드롭)

```
1. POST /api/v1/projects/:pid/pages/snapshot         → 페이지 생성 + 4파트 동시 업로드
2. PUT  /api/v1/projects/:id                         → pageCount 갱신
```

snapshot 통합 덕분에 단계가 5번에서 2번으로 단순화.

---

## 6. 기존 계약과의 관계

| 문서 | 범위 | 이 문서와의 관계 |
|------|------|-----------------|
| `INTER_ENGINE_HTTP.md` | 엔진 간 통신 전체 | 이 문서는 "UI → Service" 파일 저장 부분을 구체화 |
| `service_engine/API_CONTRACT.md` | 인증 + 과금 | 이 문서의 API는 같은 인증 체계 위에 추가 |
| `design-file-system.md` | UI 내부 파일 시스템 설계 | 이 문서는 그 설계에서 서버에 요청하는 부분 |

`INTER_ENGINE_HTTP.md`에 "object storage 상세 설계 — 제외"로 되어있는 부분이 이 문서의 범위.

---

## 7. 우선순위

| 순위 | API | 이유 |
|------|-----|------|
| 1 | 프로젝트 CRUD + 페이지 CRUD | 기본 데이터 관리 |
| 2 | 이미지 PUT/GET + 레이어 PUT/GET | 편집 기능의 핵심 |
| 3 | 썸네일 PUT/GET | 미리보기 (없어도 편집은 가능) |
| 4 | export | 결과물 다운로드 (후순위) |

1~2번이 구현되면 `CloudFileAdapter`를 만들어서 cloud 모드 기본 동작 가능.
