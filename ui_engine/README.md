# ui_engine

TOWA (Translator's One-stop Workstation with AI)의 **UI 엔진** (프론트엔드).

## 디렉토리 구조

```
ui_engine/
├── towa-app/            # 메인 앱 (Vue 3). bitmappery를 캔버스 엔진으로 embed
├── bitmappery/          # bitmappery 클론 (상세 편집 뷰의 캔버스 엔진, 커스터마이징됨)
├── docs/                # 설계 문서
│   ├── design-bitmappery-integration.md
│   ├── design-file-system.md
│   └── ui_to_service.md
├── CLAUDE.md            # AI 세션 간 공유 컨텍스트
├── TODO.md              # 할 일 관리
└── CHANGELOG.md         # 작업 내역 (KST 기준)
```

## 기술 스택

- **Vue 3** + **TypeScript** + **Vuex 4** + **Vue Router**
- **Vite** (빌드)
- **zCanvas** (캔버스 렌더링, bitmappery 내부)
- **IndexedDB** (standalone 모드 로컬 저장)
- **Tailwind CSS** (스타일링)

## 로컬 실행

```bash
cd towa-app
npm install
npm run dev
# → http://localhost:5173/
```

## 화면 구성

1. **홈** — 프로젝트 라이브러리
2. **프로젝트 보기** — 페이지 썸네일 그리드, 대시보드
3. **편집** — 번역 작업 (텍스트 목록 + 캔버스 + 레이어, translator 모드)
4. **상세 편집** — 픽셀 편집 (bitmappery 전체 도구, typesetter 모드)
