# Changelog

작업 단위 완료 시 기록. KST 기준.

---

## 2026-03-22

## 2026-03-23

### 17:07 — Deployment Mode cloud/standalone UI 분기
- 설정 추론 탭: standalone 전용으로 변경 (서버 주소, API 키, 동시 요청 등)
- cloud용 모델 선택 탭 추가 (텍스트 검출/번역/인페인팅 모델 + 플랜 표시)
- 상단바 유저 메뉴: cloud 모드에서 로그인/로그아웃 표시
- 로그인 모달 추가 (이메일/비밀번호 + 로그인 상태 유지)

### 16:58 — Deployment Mode 시스템 + 라이트 테마
- config/deployment.ts: DeploymentMode 타입 + reactive 모드 전환
- composables/useDeploymentMode.ts: isCloud/isStandalone/filterByMode 유틸
- 설정 모달 탭에 mode 필드 적용: 계정(cloud), 모델 연결(standalone)
- 디버그 탭 추가: 런타임에서 cloud/standalone 전환 가능
- 라이트 테마 구현: CSS 변수 기반 dark/light 전환, 설정에서 즉시 반영

### 11:29 — 테마 변경 + 더미 데이터 개선
- 색상 테마 커스텀 (accent #9569B4 보라, pink #e84a8a, green #4ade80)
- 배경/서페이스 톤을 보라빛 다크로 통일 (#0f0d18, #1a1726, #2a2540)
- 더미 프로젝트 8개로 확장: 원피스/주술회전/블루록/나혼렙/킹덤/전독시/요츠바랑/단편
- 현실적 데이터: 제목에 화수+부제, 페이지 수 다양화(8~180p), 폴더 분산
- 폴더 아이콘 색상을 accent(보라)로 통일

### 02:32 — 편집 화면 재설계 + 페이지 상태 단순화
- 페이지 상태: 5단계(pending~reviewed) → 4단계(waiting/ai-processing/in-progress/done)
- 편집 화면(역자 모드): 좌측 PageSidePanel(접기/펼기) + DualCanvasView(한쪽/두쪽 전환) + TranslationPanel(텍스트 전용)
- 한쪽보기: 원본/작업본 좌우 분할 / 두쪽보기: 만화 2페이지 펼침
- 상세 편집(식자 모드): PageSidePanel + bitmappery placeholder
- 프로젝트 홈: 페이지 상태 필터 칩 추가, hover 버튼 크기 통일
- PageStrip/EditorCanvas 삭제, PageSidePanel/DualCanvasView/TranslationPanel 신규
- editor store: pagePanelCollapsed, canvasViewMode 추가

### 00:13 — 프로젝트 홈 대시보드 + 상태 필터 이동 + 상단바 정리
- 프로젝트 홈 탭: 대시보드(이어하기 버튼, 진행률 바, 마지막 작업 페이지) + 페이지 그리드
- 레이아웃 전환: 상/하 또는 좌/우 배치 토글 버튼
- 상태 필터: 사이드바에서 메인 화면 우상단 가로 칩으로 이동
- 상단바: TOWA 로고(홈 버튼) + 홈 > 경로 구조, 구분자 `/` → `>` 변경

### 15:40 — 카드 UI 통일 + 폴더 미리보기 개선
- 새 프로젝트 버튼 크기를 프로젝트/폴더 카드와 동일하게 통일
- 프로젝트 카드: 하단 정보 영역 축소 (이름만 한 줄), 언어/페이지수/상태를 이미지 위 오버레이
- 폴더 카드: 직속 하위 항목(폴더+프로젝트) 미리보기, 2x2 고정 그리드, 하위 폴더는 폴더 아이콘으로 표시
- 폴더 미리보기 로직: 하위 폴더 프로젝트가 아닌 직속 자식만 표시 (파일시스템 원칙)

### 15:33 — 폴더 탐색 로직 수정 + 경로 UI 통일
- 폴더 필터링: 하위 폴더 프로젝트가 상위에서 안 보이도록 exact match로 변경
- 폴더 카드: 프로젝트 카드와 동일 크기, 내부에 하위 항목 썸네일 4개 미리보기
- 경로 표시: 라이브러리/프로젝트 모두 상단바에 통일 (ChevronRight 구분자)
- 더미 데이터: 주간연재 직속 프로젝트(킹덤) 추가하여 폴더 구조 검증

### 15:24 — UI 디테일 개선 (환경설정, 사이드바 정리, 폴더/프로젝트 분리)
- 환경설정 모달 추가 (일반/추론/외관 3탭, placeholder 항목 채움)
- 사이드바 순서 변경: 검색 → 최근 프로젝트 → 폴더 트리 → 상태 필터
- 폴더 트리: 섹션 헤더 제거, "전체"를 루트 노드로 통합, divider로 섹션 구분
- 메인 화면: 폴더 카드를 compact 가로 행으로 분리, 프로젝트 그리드와 크기 불일치 해소
- FolderCard를 가로 pill 스타일로 변경

### 14:30 — 라이브러리 UI 개선 (폴더 탐색, 사이드바, 유저 프로필)
- 메인 화면: Windows 탐색기 스타일 폴더 카드 + 프로젝트 카드 혼합 표시
- 사이드바: 폴더 트리 (2단계, 접기/펼치기 토글) + 상태 필터 + 최근 편집 섹션
- 상단바: 폴더 경로 클릭 시 해당 폴더로 이동, 유저 프로필/환경설정 dropdown 추가
- library store 신규: 폴더 트리, 현재 경로, 상태 필터 관리
- projects store: byFolder getter, recentlyEdited getter 추가
- 더미 데이터: folder를 계층 경로로 변경 (주간연재/점프, 웹툰/네이버 등)
- FolderCard 컴포넌트 신규, folder.ts 타입 신규

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
