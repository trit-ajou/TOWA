# TODO

## 당장 할 일

- [x] Mermaid 조감도 작성 (전체 화면 흐름 + 각 화면 컴포넌트 배치)
- [x] towa-app Vue 3 프로젝트 초기화
- [x] HTML 프로토타입 (화면 ①②③) → Vue 컴포넌트로 구현 완료
- [ ] bitmappery 커스터마이징 시작 (화면 ④)
  - [ ] 불필요한 기능 비활성화 목록 정리
  - [ ] 만화 번역에 필요한 UI 요소 파악
- [ ] bitmappery 컴포넌트를 towa-app에 embed하는 구조 설계

## Future

- [ ] 자체 프로젝트 파일 포맷 설계
- [ ] 백엔드 API placeholder 연동
- [ ] AI 도구 UI (인페인팅, 번역 호출)
- [ ] Electron 패키징
- [ ] 설정 페이지 (inference_mode, 서버 주소, API 키 등)
- [ ] PSD 등 외부 포맷 export
- [ ] 협업 기능
- [ ] 커뮤니티 기능 UI

---

# 에이전트별 작업 배정

## Agent 1: 전체 UI 프로토타입 + towa-app 초기화

### 목표
화면 ①②③의 레이아웃과 화면 전환을 실제로 동작하는 형태로 구현. 교수님 발표 + 팀 내부 리뷰에 쓸 수 있는 수준.

### 작업 내용

1. **towa-app Vue 3 프로젝트 초기화**
   - `towa_frontend/` 루트에 `towa-app/` 디렉토리 생성
   - Vue 3 + TypeScript + Vite + Vue Router 세팅
   - 기본 라우팅 구조 잡기: `/` (홈) → `/project/:id` (프로젝트 보기) → `/project/:id/edit/:pageId` (기본 편집) → `/project/:id/edit/:pageId/detail` (상세 편집 — placeholder)

2. **화면 ① 홈 화면 구현**
   - 사이드바: 검색 바, 폴더/태그 필터 (UI만, 기능은 placeholder)
   - 메인 영역: 프로젝트 카드 그리드 (더미 데이터로 썸네일 카드)
   - 프로젝트 생성 버튼 + 설정 모달 (초벌번역 config 포함)
   - 프로젝트 카드 클릭 시 화면 ②로 이동

3. **화면 ② 프로젝트 보기 화면 구현**
   - 상단 헤더: 프로젝트 제목, 설정 버튼, 뒤로가기
   - 메인 영역: 페이지 썸네일 그리드 (더미 만화 이미지)
   - 하단/상단: 페이지 추가, 일괄 작업 버튼 (UI만)
   - 페이지 썸네일 클릭 시 화면 ③으로 이동

4. **화면 ③ 기본 편집 화면 구현**
   - 3단 레이아웃: 좌(페이지 썸네일 네비) / 중앙(메인 캔버스 영역) / 우(텍스트 목록 패널)
   - 좌측 패널: 페이지 썸네일 리스트, 클릭 시 페이지 전환
   - 중앙: 이미지 표시 영역 (더미 이미지, 줌/팬은 placeholder)
   - 우측 패널: 텍스트 블록 목록 (원문/번역문 쌍 표시), 레이어 토글 버튼
   - AI 기능 호출 버튼 (인페인팅, 번역 — UI만, 실제 호출은 placeholder)
   - "상세 편집" 버튼 클릭 시 화면 ④로 이동 (일단 placeholder 페이지)

5. **공통 UI 요소**
   - 다크 테마 기본 (만화 편집 도구 특성상)
   - 상단 메뉴바 또는 네비게이션
   - 모달/팝업 기본 컴포넌트

6. **Deployment Mode 시스템 (`cloud` / `standalone`)**
   - `config/deployment.ts`에 deployment mode 정의
     ```ts
     type DeploymentMode = 'cloud' | 'standalone'
     const DEPLOYMENT_MODE: DeploymentMode = import.meta.env.VITE_DEPLOYMENT_MODE ?? 'standalone'
     ```
   - `useDeploymentMode()` composable 제공 (`isCloud`, `isStandalone` 등)
   - **탭/섹션 단위 제어**: 각 탭/섹션 정의에 `mode: 'all' | 'cloud' | 'standalone'` 필드 포함
     ```ts
     { id: 'account', label: '계정', mode: 'cloud' }
     { id: 'local-model', label: '모델 연결', mode: 'standalone' }
     { id: 'general', label: '일반', mode: 'all' }
     ```
   - 컴포넌트 내부 `v-if` 분기보다 탭/섹션 통째로 태그하는 방식 우선
   - **분기 기준**:
     - 서비스 엔진 통신이 필요한 기능 → `cloud` (당장은. 추후 standalone에서도 열릴 수 있음)
     - 로컬 모델 연결/설정 UI → `standalone`
     - 나머지 → `all`

### 참고
- CLAUDE.md와 towa_project_description.md의 화면 구성 참조
- **bitmappery의 기존 UI 스타일을 따르지 않음** — 독자적으로 깔끔하고 완성도 높은 디자인 추구
- 프로토타입이지만 **실제 개발에 바로 쓸 수 있는 품질**로 구현 (보여주기용 X)
- 더미 데이터로 UI 구현, 백엔드 연동 불필요 (단, 컴포넌트 구조/코드 품질은 프로덕션 수준)

---

## Agent 2: bitmappery 분석 + 디자인 통합 (상세 편집 뷰)

### 목표
bitmappery 코드를 분석하여 기능을 파악하고, 불필요한 기능을 비활성화한 뒤, **Agent 1이 만든 UI 디자인 시스템에 맞춰** bitmappery의 외형을 변형.

### 작업 내용

1. **bitmappery 코드 분석 및 기능 분류** ✅
   - 전체 기능 목록 작성 (8개 카테고리, 46개 개별 기능)
   - 만화 번역에 필요한 기능 / 불필요한 기능 / 판단 보류 기능으로 분류
   - 분류 결과를 Notion 설계 문서 DB에 기록 완료
   - 텍스트 gap 분석 + embed 검토 완료

2. **Feature flag 시스템 구현 + 불필요한 기능 비활성화** ✅
   - `src/config/towa-features.ts`에 46개 개별 feature flag 정의
   - 클라우드 연동 (Dropbox, Google Drive, S3) 비활성화
   - GIF 생성 기능 비활성화
   - PDF import, PSD import — flag 제어 가능 (현재 활성)
   - 도구, 메뉴, 파일 형식 모두 개별 flag로 on/off 가능
   - 빌드 검증 완료

3. **UI 변형 (Agent 1 디자인에 맞춤)**
   - Agent 1이 확립한 디자인 시스템(색상, 타이포, 컴포넌트 스타일)을 bitmappery에 적용
   - 불필요한 메뉴 항목 숨기기 (File 메뉴의 클라우드 관련 등)
   - 만화 번역에 자주 쓰는 도구를 쉽게 접근할 수 있도록 도구함 재배치 검토
   - towa-app의 나머지 화면과 이질감 없도록 통일

4. **만화 번역 특화 요소 파악**
   - 텍스트 레이어의 현재 기능 수준 확인 (폰트, 크기, 색상, 획 효과 등)
   - 레이어 패널이 "원본 + 인페인팅 + 텍스트 N개" 구조에 적합한지 검토
   - AI 도구를 어디에 어떻게 추가할 수 있을지 진입점 파악 (예: 도구함에 AI 지우개 추가)

5. **towa-app embed 가능성 검토**
   - bitmappery.vue를 독립 컴포넌트로 분리할 수 있는지 확인
   - Vuex store 충돌 없이 towa-app에 통합 가능한지 검토
   - 필요한 인터페이스 정의 (towa-app ↔ bitmappery 간 데이터 전달 방식)

### 참고
- bitmappery 로컬 실행: `cd bitmappery && npm run dev` → http://localhost:5173/
- 비활성화 시 원본 코드를 보존하는 방식으로 (나중에 다시 활성화 가능하도록)
- UI 변형은 Agent 1의 디자인이 확립된 후 진행 (그 전까지는 분석 + 비활성화에 집중)
- 커스터마이징 결과는 Notion 설계 문서 DB에 기록
