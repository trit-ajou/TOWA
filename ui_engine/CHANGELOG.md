# Changelog

작업 단위 완료 시 기록. KST 기준.

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

### 01:45 — monorepo 이전 및 Git 초기화
- TOWA monorepo (trit-ajou/TOWA) clone
- towa_project_description.md → TOWA/README.md로 합침 (main push)
- towa_frontend/ 내용을 TOWA/ui_engine/으로 복사 (자주프 관련 파일 제외)
- CLAUDE.md: monorepo 경로 반영, Git 규칙 추가 (feature 브랜치, Co-authored-by 금지)
- feat/ui-engine-init 브랜치에 커밋 및 push
