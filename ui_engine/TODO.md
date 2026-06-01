# TODO

장기 계획은 `Project_Plan.md` 참조 (gitignore 대상, 로컬 전용).

## 진행 중 / 다음 할 일

- [ ] **#57** 프로젝트 생성 시 일괄 AI 적용 (#39 인프라 위 후속 — active/background 분기, savePage 직접 호출 기반)
- [ ] **F3** 만화 번역 특화 UI/UX 재설계
- [ ] **F7** 페이지 export (PNG/ZIP)
- [ ] **F9** cloud 모드 통합 e2e 검증 (실 페이지 AI 사이클)
- [ ] **F11** LoginModal 세션 만료 overlay
- [ ] **F8** Electron 래핑
- [ ] Library 폴더 트리 서버 source 화 (하드코드 제거)
- [ ] Landing 실제 콘텐츠 (데모 영상, 사용 가이드)

## 이슈 / 버그

(현재 비어있음)

## 정리 필요 (eocodn 변경사항)

- [ ] 불필요한 bitmappery optional 의존성 정리 (`@aws-sdk/client-s3`, `dropbox`, `psd.js`, `gifshot`, `pdfjs-dist`, `tiny-script-loader`)
- [ ] `vue-select` v4 beta → stable 전환 또는 대안 검토
- [ ] zcanvas v5 다운그레이드 영향 확인

## 완료

- [x] 전체 UI 프로토타입 (화면 ①②③④)
- [x] bitmappery 통합 (store namespace, feature flag, CSS 격리, 모드 전환)
- [x] flex + Teleport 레이아웃
- [x] 파일 시스템 (IndexedDB, FileAdapter, 로드/저장/전환/캐시/자동저장)
- [x] 이미지 드래그앤드롭 페이지 추가 + 썸네일 갱신
- [x] 서비스 엔진 연동 명세 작성
- [x] Cloud 모드 어댑터 (FilesBackend SDK + CloudFileAdapter + auth 모듈)
- [x] 프로젝트 생성 플로우 완성 (생성 → IndexedDB 저장 → 프로젝트 페이지 자동 이동)
- [x] 프로젝트 삭제 (카드 hover 삭제 버튼 → 확인 모달 → 삭제 + 목록 갱신)
- [x] 페이지 삭제 (썸네일 hover 삭제 버튼 → 확인 모달 → 삭제 + 카운트 갱신)
- [x] 중간보고서 작성 (docx + 주차별 연구노트 6개)
- [x] main 머지 (`--no-ff Merge ui_engine: Cloud mode integration and CRUD UI`)
- [x] **F4** AI 도구 연동 (검출 → 지움 → 번역 → 식자) — model_engine API 호출 + result-applier로 textBlock + bitmappery layer 자동 적용 (9740931, 팀 작업)
- [x] Cloudflare tunnel 기반 서버 배포 인프라 (deploy.sh cron + .env.deploy + DEPLOY.md)
- [x] ui-engine 컨테이너 빌드 안정화 (Dockerfile npm install + lock 미포함 + deterministic 옵션)
- [x] package-lock.json 추적 해제 (cross-platform 충돌 방지)
- [x] Landing(`/`) / Login(`/login`) 풀페이지 + 라우터 가드 (`meta.requiresAuth` + `beforeEach` redirect to `/login?redirect=...`)
- [x] AppNavbar 로그인 메뉴 navigate + logout redirect
- [x] **U6 / B1** Bitmappery 백그라운드 단축키 가드 — `router/index.ts` beforeEach에서 `KeyboardService.setSuspended` 호출로 처리
- [x] **#22 일부** 편집 화면 UI 개편 — 새 toolbox/패널/AI 드롭다운, Hand(Space)/Zoom 도구, AI 진행 알림, FG/BG swap+X, 우클릭 브러쉬 옵션, Alt+클릭 스포이드, 비-커스텀 레이어 paint 가드 토스트 (Ctrl+T transform은 Project_Plan.md U7로 분리)
- [x] **U1** 페이지 전환 깜빡임 개선 — #39에서 PageTransitionOverlay (캔버스 영역 한정, 300ms delay)로 해결
- [x] **F5** TranslationPanel ↔ bitmappery 텍스트 레이어 양방향 동기화 — EditorTab에서 update/add/remove 핸들러로 bmp/updateLayer·addLayer·removeLayer 호출, layer 상태 ↔ TranslationPanel 양방향
- [x] **#39** FileAdapter sync 레이어 재구성 — TanStack Query 마이그레이션, 페이지 캐시(IDB + per-user namespace), prefetch, 자동저장/수동저장(Ctrl+S), per-page "저장 안 됨" 뱃지, AI 결과 적용 active/background 분기, 페이지 전환 즉시 저장, KeepAlive 제거(vuejs/core#8509), thumbnail viewport→doc snapshot. 자세한 내역은 CHANGELOG 참조
