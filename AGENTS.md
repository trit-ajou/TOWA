# Agent Rules

## Workspace
- 이 프로젝트는 만화 번역을 위한 통합 워크스테이션 with AI 개발 프로젝트입니다.
- UI engine, model engine, service engine으로 나눕니다. 작업에 앞서 현재 브랜치를 파악하세요.
- `service_engine` 브랜치에서는 각 엔진의 통신 레이어와 service engine을 담당합니다. UI engine과 model engine의 세부 구현은 건드리지 않습니다.
- `ui_engine` 브랜치에서는 UI engine의 세부 구현을 담당합니다.
- `model_engine` 브랜치에서는 model engine의 세부 구현을 담당합니다.
- 빌드와 테스트 모두 Docker를 사용합니다.

## Docs
- 프로젝트 전반에 적용되는 중요한 규칙/방법론/접근법/리팩토링을 적용할 경우 `docs/` 디렉토리에 간단히 문서화하고, 그 문서에 대한 설명을 아래 목록에 작성하세요:
  - [docs/http-contract.md](docs/http-contract.md): 현재 구현 기준 단일 HTTP 계약 문서입니다. `UI engine`, `service engine`, `model engine` 간 wire contract를 함께 정의합니다.
  - [docs/service-engine-boundary.md](docs/service-engine-boundary.md): `service_engine`의 책임 경계, 비목표, 고정된 v1 설계 선택을 정리합니다.
  - [docs/project-page-storage-boundary.md](docs/project-page-storage-boundary.md): cloud `project/page` 저장의 authority, page summary와 page snapshot 구분, multipart snapshot 규칙을 정리합니다.
  - [docs/ui-model-abstract-boundary.md](docs/ui-model-abstract-boundary.md): `UI engine`과 `model engine` 사이에서 이번 단계에 고정하는 추상 경계와 의도적으로 미루는 세부 wire shape를 정리합니다.
  - [docs/boundary-open-questions.md](docs/boundary-open-questions.md): v1 boundary를 구현하기 전에 정해야 하는 미결 질문과 합의 필요 항목을 추적합니다.
