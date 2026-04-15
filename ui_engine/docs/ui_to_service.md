# UI Engine → Service Engine: 파일 저장 API 요청 명세

UI 엔진에서 필요한 파일 저장/조회 API를 정리한 문서.
service_engine 팀이 이 API를 구현하면, UI 엔진은 `CloudFileAdapter`를 만들어서 즉시 연동 가능.

---

## 0. 현재 SDK 상태와 필요한 변경

### 현재 SDK가 제공하는 것 (`towa-app/src/backend/`)

```typescript
// backend/contracts.ts — AppBackend 인터페이스
interface AppBackend {
  auth: AuthBackend        // devLogin, getCurrentUser
  aiJobs: AiJobsBackend    // createJob, getJob
}
```

- `AuthBackend`: `POST /auth/dev/login`, `GET /auth/me`
- `AiJobsBackend`: `POST /v1/jobs`, `GET /v1/jobs/:id`
- `real.ts`에 실제 HTTP 호출 구현, `emulated.ts`에 더미 구현

### SDK에 없는 것 (이 문서에서 요청하는 것)

**파일 저장/조회 API가 전혀 없음.** 프로젝트 CRUD, 페이지 CRUD, 이미지/레이어/썸네일 바이너리 저장 — 전부 새로 필요.

### SDK 수정 방안

두 가지 선택지:

**A. `AppBackend`에 `files` 속성 추가 (권장)**
```typescript
// SDK 변경: AppBackend에 files 추가
interface AppBackend {
  auth: AuthBackend
  aiJobs: AiJobsBackend
  files: FilesBackend       // ← 새로 추가
}

interface FilesBackend {
  // 프로젝트 CRUD
  listProjects(): Promise<ProjectRecord[]>
  getProject(id: string): Promise<ProjectRecord>
  createProject(project: ProjectRecord): Promise<ProjectRecord>
  updateProject(id: string, project: ProjectRecord): Promise<ProjectRecord>
  deleteProject(id: string): Promise<void>

  // 페이지 CRUD
  listPages(projectId: string): Promise<PageRecord[]>
  getPage(pageId: string): Promise<PageRecord>
  createPage(projectId: string, page: PageRecord): Promise<PageRecord>
  updatePage(pageId: string, page: PageRecord): Promise<PageRecord>
  deletePage(pageId: string): Promise<void>

  // 바이너리
  getImage(pageId: string): Promise<Blob>
  putImage(pageId: string, blob: Blob): Promise<void>
  getLayers(pageId: string): Promise<Blob | null>
  putLayers(pageId: string, blob: Blob): Promise<void>
  getThumbnail(pageId: string): Promise<Blob | null>
  putThumbnail(pageId: string, blob: Blob): Promise<void>
}
```

이렇게 하면 기존 SDK 패턴(real/emulated 분리, `requestJson` 유틸리티)을 그대로 따를 수 있음.
UI 쪽에서는 `CloudFileAdapter`가 `AppBackend.files`를 호출하면 끝.

**B. FileAdapter를 SDK와 별개로 구현**

UI가 직접 fetch로 서버 API를 호출. SDK를 건드리지 않아도 되지만, 인증 헤더 처리나 에러 핸들링을 중복 구현해야 함.

→ **A 방안을 권장합니다.** 기존 패턴과 일관성 유지 + 인증/에러 처리 재사용.

### 바이너리 전송 관련 SDK 변경

현재 `real.ts`의 `requestJson()`은 JSON만 처리. 바이너리(Blob) 전송을 위해:
- `requestBlob(url, init)` 함수 추가 필요 (응답을 `response.blob()`으로 처리)
- PUT 시 `Content-Type: application/octet-stream` 또는 `image/png` 설정

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

### 3.3 바이너리 (원본 이미지)

```
GET    /api/v1/pages/:id/image               → Blob (image/png or image/jpeg)
PUT    /api/v1/pages/:id/image               → 204 (Content-Type: image/*)
```

- 페이지 생성 시 이미지도 함께 업로드 (또는 별도 PUT)
- GET은 원본 그대로 반환

### 3.4 바이너리 (레이어 데이터)

```
GET    /api/v1/pages/:id/layers              → Blob (application/octet-stream)
PUT    /api/v1/pages/:id/layers              → 204 (Content-Type: application/octet-stream)
```

- bitmappery 직렬화 Blob — 서버는 **opaque**로 취급 (해석 불필요, 그대로 저장/반환)
- 자동 저장 시 30초 debounce로 PUT 호출
- 페이지 전환 시에도 PUT 호출

### 3.5 바이너리 (썸네일)

```
GET    /api/v1/pages/:id/thumbnail           → Blob (image/png)
PUT    /api/v1/pages/:id/thumbnail           → 204 (Content-Type: image/png)
```

- UI가 캔버스 캡처 → 축소 → PNG Blob 생성 → PUT
- 목록/사이드 패널에서 미리보기용

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
1. GET /api/v1/projects/:id              → 프로젝트 메타
2. GET /api/v1/projects/:id/pages/       → 페이지 목록 + textBlocks
3. GET /api/v1/pages/:id/thumbnail       → 각 페이지 썸네일 (미리보기용)
4. GET /api/v1/pages/:id/layers          → 현재 페이지의 편집 상태
   → 없으면 GET /api/v1/pages/:id/image → 원본 이미지로 새 문서 생성
```

### 편집 중 자동 저장 (30초 debounce)

```
PUT /api/v1/pages/:id/layers             → bitmappery 직렬화 Blob
PUT /api/v1/pages/:id/thumbnail          → 캔버스 캡처 썸네일
```

### 페이지 전환

```
1. PUT (이전 페이지 저장)
2. GET (새 페이지 로드)
```

### 새 페이지 추가 (이미지 드래그앤드롭)

```
1. POST /api/v1/projects/:pid/pages/     → 페이지 메타 생성
2. PUT  /api/v1/pages/:id/image          → 원본 이미지 업로드
3. PUT  /api/v1/pages/:id/layers         → 초기 bitmappery 문서
4. PUT  /api/v1/pages/:id/thumbnail      → 썸네일
5. PUT  /api/v1/projects/:id             → pageCount 갱신
```

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
