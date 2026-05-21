# TOWA UI Engine — Project Plan

장기적인 개발 스콥과 주차별 계획. 팀원이 ui_engine 작업 흐름을 파악할 수 있도록 추적 대상.

---

## 완료 현황 (~ 10주차 후반, 2026-05-10 기준)

### 1~3주차: 설계 + 프로토타이핑
- [x] Mermaid 조감도 (전체 화면 흐름 + 컴포넌트 배치)
- [x] towa-app Vue 3 프로젝트 초기화
- [x] 화면 ①②③ Vue 컴포넌트 구현
- [x] deployment mode 시스템 (standalone/cloud)
- [x] 백엔드 어댑터 패턴 (auth + aiJobs)

### 4~5주차: bitmappery 통합
- [x] bitmappery 기능 분석 + feature flag 시스템 (46개 flag)
- [x] bitmappery → towa-app 통합 (store namespace, CSS 격리, 테마 매핑)
- [x] 화면 ③ translator 모드 + ④ typesetter 모드 캔버스 공유
- [x] flex + Teleport 레이아웃 (사이드 패널 + bitmappery 공존)
- [x] container query 기반 bitmappery 반응형 레이아웃

### 6주차: 파일 시스템
- [x] IndexedDB 스키마 + LocalFileAdapter
- [x] usePageLoader (로드/저장/전환 + 캐시 2계층)
- [x] useAutoSave (history 감지 → 30초 debounce)
- [x] 이미지 드래그앤드롭 페이지 추가
- [x] 더미 데이터 seed (원본 이미지 + bitmappery 문서 + 썸네일)
- [x] 썸네일 자동 갱신 (캔버스 캡처)
- [x] bitmappery 캔버스 재생성 버그 수정 (stale singleton)
- [x] 서비스 엔진 연동 명세 작성 (`docs/ui_to_service.md`)

### 7주차: Cloud 모드 연동
- [x] FilesBackend SDK (real: multipart HTTP, emulated: 메모리 stub)
- [x] FileAdapter snapshot 중심 인터페이스 리팩터링
- [x] CloudFileAdapter (backend.files.* 위임)
- [x] Vuex auth 모듈 (sessionKey/user/creditBalance, localStorage 복원)
- [x] LoginModal/AppNavbar/SettingsModal auth 스토어 연결
- [x] main.ts deployment mode 분기 (standalone: seed+IDB / cloud: 세션 복원→서버)
- [x] IDB DataCloneError 수정 (Vue reactive proxy → JSON sanitize)
- [x] ULID 기반 canonical ID 도입
- [x] Docker 빌드 환경 정비 (Dockerfile, vite resolver, layer_blob MIME 정규화)
- [x] zcanvas v5 pin (bitmappery 호환)

### 8주차 (04/21 ~ 04/27): CRUD 완성 + 중간보고서
- [x] 프로젝트 생성 플로우 완성 (CreateProjectModal → IndexedDB → 자동 이동)
- [x] 프로젝트 삭제 (카드 hover 버튼 + 확인 모달)
- [x] 페이지 삭제 (썸네일 hover 버튼 + 확인 모달)
- [x] Playwright E2E 테스트 (전체 흐름 검증)
- [x] 중간보고서 작성 (docx + pdf)
- [x] 주차별 연구노트 6개 (3~8주차)
- [x] main 머지 (`--no-ff` Merge ui_engine: Cloud mode integration and CRUD UI)

### 9주차 (04/28 ~ 05/04): AI 도구 연동 시작 + 설계 정비
- [x] AiToolbar 1차 wire-up (model_engine `/v1/jobs` 호출 + polling, placeholder 결과 status 표시)
- [x] `composables/useAppBackend.ts` 추가 + `main.ts`에서 backend provide
- [x] Credit 잔액 UI (AppNavbar) + AI job 종료 시 자동 갱신
- [x] 프로젝트 생성 시 페이지 업로드 누락 버그 fix (`utils/page-from-file.ts`로 공통화)
- [x] 설계 문서 갱신 (`design-file-system.md`, `ui_to_service.md`) + TODO/Project_Plan 정비

### 10주차 (05/05 ~ 05/11): AI 결과 자동 적용 + 서버 배포 인프라
- [x] **F4** AI 결과 자동 적용 완성 — `result-applier.ts`로 검출/지움/번역/식자 결과를 textBlock + bitmappery layer로 자동 추가; AiToolbar에서 성공 시 적용 / 실패 시 페이지 상태 롤백; `AiJobsBackend.getArtifact()` backend 추가 (팀 작업 `9740931`)
- [x] Cloudflare tunnel 기반 서버 배포 인프라 — `deploy.sh` (cron 5분 폴링 + `.env.deploy` 부트스트랩 + 컨테이너 상태 체크), `DEPLOY.md` 운영 가이드, 단일 도메인 분기 (`towa.live`/`api.towa.live`/`model.towa.live`)
- [x] ui-engine 컨테이너 빌드 안정화 — Dockerfile `npm install --legacy-peer-deps --no-audit --no-fund --maxsockets=1` + lock 미포함, vite `optimizeDeps.include: ['lz-string']`
- [x] `package-lock.json` 추적 해제 (cross-platform native binary 충돌 회피)
- [x] Landing(`/`) / Login(`/login`) 풀페이지 + 라우터 가드 (`meta.requiresAuth` + `beforeEach` redirect to `/login?redirect=...`) + manga panel × editorial brutalism 디자인 (Bricolage Grotesque + Pretendard 폰트, halftone/grain/marker 유틸)
- [x] AppNavbar logout redirect (팀 작업 `315330b`)
- [x] **F9 partial** Cloudflare `api.towa.live` / `model.towa.live` ingress 등록 (사용자 직접 완료)
- [ ] **U1** 페이지 전환 깜빡임 (로딩 오버레이) — 05/10~11 진행
- [ ] **U6 / B1** Bitmappery 백그라운드 단축키 비활성 가드 (`KeyboardService.setSuspended` 호출) — 05/10~11 진행
- [ ] **F5** TranslationPanel ↔ bitmappery 텍스트 레이어 양방향 동기화 — 05/10~11 진행 (UI 재배치는 11주차 F3와 함께)

---

## 남은 구현 사항

### 핵심 기능 (MVP)

| # | 항목 | 설명 | 의존성 |
|---|------|------|--------|
| ~~F1~~ | ~~프로젝트 생성 플로우~~ | **8주차 완료** | - |
| ~~F2~~ | ~~프로젝트/페이지 삭제~~ | **8주차 완료** | - |
| F3 | 만화 번역 특화 UI/UX 재설계 | bitmappery 원본 UI를 만화 번역 워크플로우에 맞게 재구성 (페이지 빠른 전환, 텍스트 블록 이동, 폰트 프리셋 등 우선 배치) | - |
| ~~F4~~ | ~~AI 도구 연동~~ | **9~10주차 완료** (9주차 wire-up, 10주차 result-applier로 결과 자동 적용) | - |
| F5 | TranslationPanel ↔ bitmappery 텍스트 레이어 연동 | 번역문 수정 → 캔버스 반영, 캔버스 텍스트 → 패널 동기화 | F3 |
| ~~F6~~ | ~~CloudFileAdapter~~ | **7주차 완료** | - |
| F7 | 페이지 export (PNG/ZIP) | 편집 결과 다운로드 | - |
| F8 | Electron 래핑 | UI 엔진을 데스크톱 앱으로 전환 (네트워크/메모리 병목 해소) | - |
| F9 | cloud 모드 통합 테스트 | 인프라/코드 완료 (10주차). 실 e2e 검증만 남음 (Cloudflare ingress 등록 + 실 페이지 검출/번역/식자 시연) | service_engine 운영 |
| F10 | eocodn 변경사항 정리 | 불필요한 bitmappery optional 의존성 제거 (`@aws-sdk/client-s3`, `dropbox`, `psd.js`, `gifshot`, `pdfjs-dist`, `tiny-script-loader`), `vue-select` v4 stable 전환 | - |
| F11 | LoginModal 세션 만료 overlay | 401 인터셉터 → 현재 화면 dim + LoginModal 띄움 (현재는 평상시 로그인은 `/login` 페이지로 분리됨) | - |

### UI/UX 개선

| # | 항목 | 설명 |
|---|------|------|
| U1 | 페이지 전환 체크무늬 깜빡임 | 로딩 오버레이 또는 이전 캔버스 유지 |
| U2 | 설정 페이지 | inference_mode, 서버 주소, API 키 등 |
| U3 | 페이지 순서 변경 (드래그) | PageGrid/PageSidePanel에서 드래그로 순서 변경 |
| U4 | 키보드 단축키 통합 | bitmappery 단축키 + towa-app 단축키 충돌 해결 |
| U5 | 다국어 지원 (i18n) | 한국어/일본어/영어 UI |
| U6 | Bitmappery 백그라운드 단축키 비활성 가드 (B1) | bitmappery preload로 캔버스 비노출 화면(라이브러리/프로젝트 홈)에서도 키 입력이 KeyboardService에 전달됨 → `setSuspended(true)` 호출로 차단 |

### 장기 (post-MVP)

| # | 항목 | 설명 |
|---|------|------|
| L1 | 자체 프로젝트 파일 포맷 (.towa) | export/import용 아카이브 |
| L2 | PSD export | ag-psd 라이브러리로 레이어별 Canvas → PSD |
| L3 | Electron 패키징 | 데스크톱 앱 |
| L4 | 협업 기능 | 페이지 단위 잠금, 실시간 동기화 |
| L5 | 커뮤니티 기능 | 번역 프로젝트 공유/선점 |
| L6 | 워크플로우 플러그인 | ComfyUI 스타일 파이프라인 |

---

## 주차별 계획 (앞으로)

### 11주차 (05/12 ~ 05/18) — Bitmappery UX 재설계 + Panel 양방향

- [ ] **F3** 만화 번역 특화 UI/UX 재설계 — 도구 배치, 텍스트 블록 네비게이션, 폰트 프리셋
- [ ] **F5** TranslationPanel ↔ bitmappery 텍스트 레이어 양방향 동기화 (F3과 묶음)

### 12주차 (05/19 ~ 05/25) — Export + e2e 검증 + 부수 항목

- [ ] **F7** 페이지 export PNG/ZIP
- [ ] **F9** cloud e2e 시연 마감 (실 사용 시나리오 다회 검증)
- [ ] **U2** 설정 페이지 정리
- [ ] **F11** LoginModal 세션 만료 overlay (401 인터셉터 → 모달)

### 13주차 (05/26 ~ ) — Electron + 의존성 정리 + 마감

- [ ] **F8** Electron 래핑
- [ ] **F10** eocodn 의존성 정리
- [ ] Library 폴더 트리 서버 source 화 (현재 하드코드)
- [ ] Landing 실제 콘텐츠 추가 (데모/가이드)
- [ ] 통합 테스트 + 버그 수정

---

## 관련 문서

| 문서 | 위치 | 내용 |
|------|------|------|
| 설계: bitmappery 통합 | `docs/design-bitmappery-integration.md` | bitmappery 커스터마이징 방침, 통합 구조 |
| 설계: 파일 시스템 | `docs/design-file-system.md` | 데이터 모델, FileAdapter, 캐시, 자동 저장 |
| 서비스 엔진 연동 명세 | `docs/ui_to_service.md` | cloud 모드에 필요한 서버 API 목록 + SDK 변경 사항 |
| 엔진 간 HTTP 계약 | `../INTER_ENGINE_HTTP.md` | 전체 엔진 간 통신 규격 |
| TOWA 전체 개요 | `../README.md` | 프로젝트 전체 설명 |
