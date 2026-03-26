# ui_engine

TOWA (Translator's One-stop Workstation with AI) 프로젝트의 **UI 엔진** (프론트엔드) 디렉토리.

## 이 디렉토리가 담고 있는 것

```
ui_engine/
├── bitmappery/      # bitmappery 원본 클론 (상세 편집 뷰의 캔버스 엔진)
├── CLAUDE.md        # AI 세션 간 공유 컨텍스트
├── TODO.md          # 할 일 관리
├── CHANGELOG.md     # 작업 내역 기록 (KST 기준)
└── (예정) towa-app/ # 메인 앱 (Vue 3). bitmappery를 컴포넌트로 embed
```

## 구조 개요

- **towa-app** (예정): TOWA 메인 앱. Vue 3 + Vue Router 기반. 홈 화면, 프로젝트 보기, 기본 편집 화면을 포함.
- **bitmappery**: 상세 편집 화면의 캔버스 엔진. bitmappery의 핵심 컴포넌트를 towa-app에 embed하여 사용.

## 기술 스택

- **Vue 3** + **TypeScript**
- **Vuex 4** (상태 관리, bitmappery에서 사용)
- **Vue Router** (화면 전환)
- **Vite** (빌드)
- **zCanvas** (캔버스 렌더링, bitmappery에서 사용)
- 1차: 웹앱 (브라우저 접속) / 2차: Electron 래핑 (추후)

## 로컬 실행

```bash
# bitmappery 단독 실행 (상세 편집 뷰 확인용)
cd bitmappery
npm install
npm run dev
# → http://localhost:5173/
```
