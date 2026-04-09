# TODO

## 당장 할 일

- [x] Mermaid 조감도 작성 (전체 화면 흐름 + 각 화면 컴포넌트 배치)
- [x] towa-app Vue 3 프로젝트 초기화
- [x] HTML 프로토타입 (화면 ①②③) → Vue 컴포넌트로 구현 완료
- [x] bitmappery 기능 분석 + feature flag 시스템 구현
- [x] bitmappery 통합 설계 + 파일 시스템 설계 (Notion 등록 완료)
- [x] bitmappery → towa-app 통합 구현
  - [x] store namespace화 (bmp/ prefix)
  - [x] feature flag 동적화 (translator/typesetter 모드)
  - [x] CSS 격리 + 테마 매핑
  - [x] towa-app에 embed + 화면 ④ 렌더링 + 테스트 완료
- [ ] 파일 시스템 구현 (IndexedDB, FileAdapter, 더미 데이터 → 실제 저장)
- [x] 화면 ③에 translator 모드 캔버스 적용 (인스턴스 공유, 모드 전환)

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

## Agent 1 (v1): 전체 UI 프로토타입 + towa-app 초기화 ✅

완료. 화면 ①②③ Vue 컴포넌트 구현, deployment mode 시스템, 백엔드 어댑터 패턴.

---

## Agent 1 (v2): 파일 시스템 구현

### 목표
더미 데이터 기반 UI를 실제 동작하는 파일 시스템으로 전환. 프로젝트/페이지를 생성·저장·로드할 수 있도록 구현.

### 설계 문서
`design-file-system.md` 참조 (전체 아키텍처, 데이터 모델, 캐시 전략 등)

### 작업 내용

1. **FileAdapter 인터페이스 + LocalFileAdapter 구현**
   - `FileAdapter` 인터페이스 정의 (`loadPage`, `savePage`, `exportPage`, `updateThumbnail`)
   - `LocalFileAdapter`: IndexedDB 기반 구현
   - `useFileAdapter()` composable (deployment mode에 따라 구현체 선택)
   - CloudFileAdapter는 후순위 (서비스 엔진 연동 시 구현)

2. **IndexedDB 스키마 구축**
   - `towa-db`: projects, pages, page-images, page-layers, thumbnails, page-cache
   - 프로젝트/페이지 CRUD 연산

3. **기존 UI를 IndexedDB 연동으로 전환**
   - `store/modules/projects.ts`, `pages.ts` → IndexedDB 기반으로 교체
   - `data/dummy.ts` 더미 데이터 제거 (또는 초기 seed로 전환)
   - 화면 ① 프로젝트 생성 → 실제 IndexedDB 저장
   - 화면 ② 페이지 추가 (이미지 드래그앤드롭) → IndexedDB 저장
   - 화면 ②③ 썸네일 → IndexedDB에서 로드

4. **캐시 계층 구현**
   - 메모리 캐시 (Blob URL, 최근 2~3페이지)
   - IndexedDB 캐시 (LRU 방식)
   - 페이지 전환 시 직렬화 → 캐시 → 해제 → 로드 흐름

5. **자동 저장**
   - bitmappery history 변화 감지 → debounce 30초 → FileAdapter.savePage()
   - 페이지 전환 시 즉시 저장
   - dirty flag 관리

### 파일 범위
- `towa-app/src/` 내에서 작업
- 신규: `file-adapter/`, composable 등
- 수정: `store/modules/`, `data/`, 관련 컴포넌트

### 참고
- `design-file-system.md`의 데이터 모델, FileAdapter 인터페이스 정의 준수
- 단일 페이지 로드 원칙 (메모리 관리)
- bitmappery store는 `bmp/` namespace로 접근 (`store.getters['bmp/activeDocument']` 등)

---

## Agent 2: bitmappery 통합 + 상세 편집 뷰

### 목표
bitmappery를 towa-app에 직접 통합하여 화면 ③④의 캔버스 엔진으로 사용.

### 완료

1. **bitmappery 코드 분석 및 기능 분류** ✅
   - 전체 기능 목록 작성 (8개 카테고리, 46개 기능), Notion 등록
2. **Feature flag 시스템 구현** ✅
   - `towa-features.ts`에 46개 flag, 클라우드/GIF 비활성화, 빌드 검증
3. **통합 설계 + 파일 시스템 설계** ✅
   - `design-bitmappery-integration.md`, `design-file-system.md` 작성
   - Notion 설계 문서 DB에 등록 완료

4. **bitmappery → towa-app 통합 구현** ✅
   - Store namespace화, feature flag 동적화, CSS 격리, embed, 테스트 완료

5. **화면 ③ translator 모드 + 인스턴스 공유** ✅
   - ProjectView에 bitmappery 배치, ③↔④ 전환 시 캔버스 유지

### 후순위

6. **bitmappery UI 리디자인** (towa-app 디자인 시스템에 맞춤, 레이아웃 겹침 해결)
7. **레이어 그룹 기능 구현**
8. **AI 도구 진입점 추가** (인페인팅, 텍스트 검출)

### 참고
- 설계 문서: `design-bitmappery-integration.md`, `design-file-system.md`
- bitmappery 로컬 실행: `cd bitmappery && npm run dev`
- 비활성화 시 원본 코드 보존 (나중에 재활성화 가능)
- 커스터마이징 결과는 Notion 설계 문서 DB에 기록
