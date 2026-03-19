# Changelog

작업 단위 완료 시 기록. KST 기준.

---

## 2026-03-20

### 00:31 — bitmappery 기능 분석 + feature flag 시스템 구현
- bitmappery 전체 기능 카탈로그 작성 (8개 카테고리, 46개 기능)
- Notion 설계 문서 DB에 "bitmappery 기능 카탈로그" 추가 (기능 분류, 텍스트 gap 분석, embed 검토)
- `src/config/towa-features.ts` 신규 생성 — 개별 feature flag 46개 (카테고리별 그룹화)
- Cloud Storage 3종 + GIF export 비활성화 (flag false)
- 도구(toolbox), 메뉴(Document), 파일 형식(PSD/PDF) 모두 flag 제어 가능
- 변경 파일: towa-features.ts(신규), cloud-service-loader.ts, export-window.vue, toolbox.vue, header-menu.vue, file-types.ts
- 빌드 검증 통과

---

## 2026-03-19

### 00:00 — 프로젝트 문서 초기 구성
- towa_project_description.md 작성 (프로젝트 전체 설명, 3개 엔진 구조, AI 파이프라인, UI 흐름)
- README.md 작성 (이 디렉토리의 역할과 구조)
- CLAUDE.md 작성 (AI 세션 간 공유 컨텍스트, 기술 스택, 작업 방식)
- TODO.md 작성 (당장 할 일 + Future + 에이전트별 작업 배정)
- 모든 다이어그램을 Mermaid로 통일
- Notion 팀 workspace 연결 확인 및 기존 문서 검토
- Notion 설계 문서 DB에 "UI 화면 구성 및 흐름", "UI 엔진 프로젝트 구조 및 기술 기반" 추가

### 05:00 — UI 구조 개편 (피드백 반영)
- 네비게이션: 계층적 화면 전환 → 탭 기반(`홈 | 편집 | 상세 편집`) + keep-alive
- 상단바: breadcrumb 제거 → 홈 아이콘 + 폴더/프로젝트명 + 탭 + `...` dropdown
- HomeView → LibraryView 리네임, ProjectView를 탭 wrapper로 변경
- 사이드바: 태그 제거, 상태 필터 추가 (전체/진행중/완료/TODO)
- 프로젝트 생성 모달: 파일 드래그앤드롭 일괄 업로드 추가
- 프로젝트 홈: 페이지 hover 시 편집/상세편집 버튼, 선택 페이지 하이라이트
- PageNavigator(세로) → PageStrip(하단 가로) 교체
- Project 타입에 status/folder 추가, tags 제거

### 03:30 — towa-app 프로젝트 초기화 + 화면 ①②③ 구현
- towa-app/ Vue 3 + TypeScript + Vite + Tailwind CSS v4 프로젝트 scaffold
- Vuex 4 namespaced store (projects, pages, editor 모듈)
- 공통 컴포넌트: AppNavbar, BaseModal, BaseButton, BaseCard, SearchBar
- 화면 ① 홈: 프로젝트 라이브러리 (사이드바 + 카드 그리드 + 생성 모달)
- 화면 ② 프로젝트 보기: 페이지 썸네일 그리드 + status badge
- 화면 ③ 기본 편집: 3단 레이아웃 (페이지 네비 / 캔버스 / 텍스트 목록+레이어)
- 화면 ④ 상세 편집: bitmappery 통합 예정 placeholder
- 다크 테마, bitmappery 색상 체계 기반, 라우팅 4개 화면 전환 동작
- 더미 데이터: 4개 프로젝트, 5~8페이지씩, 텍스트 블록 + 레이어

### 01:45 — monorepo 이전 및 Git 초기화
- TOWA monorepo (trit-ajou/TOWA) clone
- towa_project_description.md → TOWA/README.md로 합침 (main push)
- towa_frontend/ 내용을 TOWA/ui_engine/으로 복사 (자주프 관련 파일 제외)
- CLAUDE.md: monorepo 경로 반영, Git 규칙 추가 (feature 브랜치, Co-authored-by 금지)
- feat/ui-engine-init 브랜치에 커밋 및 push
