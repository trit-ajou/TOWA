# TODO

장기 계획은 `Project_Plan.md` 참조 (gitignore 대상, 로컬 전용).

## 중간보고서 전 마무리 (우선)

완료됨 — 아래 완료 섹션 참조

## 다음 할 일

- [ ] bitmappery UI 리디자인 (towa-app 디자인 시스템 맞춤)
- [ ] 페이지 전환 깜빡임 개선 (로딩 오버레이)
- [ ] AI 도구 연동 (detect → inpaint → translate, model_engine API)
- [ ] TranslationPanel ↔ bitmappery 텍스트 레이어 연동

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
- [x] 프로젝트 생성 플로우 완성 (생성 → IndexedDB 저장 → 프로젝트 페이지 자동 이동)
- [x] 프로젝트 삭제 (카드 hover 삭제 버튼 → 확인 모달 → 삭제 + 목록 갱신)
- [x] 페이지 삭제 (썸네일 hover 삭제 버튼 → 확인 모달 → 삭제 + 카운트 갱신)
