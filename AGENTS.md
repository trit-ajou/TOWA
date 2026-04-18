# Agent Rules

## General
- Think in English, answer in Korean.
- 매 턴 그리고 컨텍스트 압축 직후, `AGENTS.md`를 반드시 한 번 읽으세요.
- 자율적으로, 적극적으로 커밋하세요.
- `python` 대신 `python3`를 사용하고, 반드시 가상 환경에서 작업하세요.
- 셸 명령은 foreground PTY 세션을 사용하세요.
- plan 모드가 아니더라도, 명확한 수정 지시가 없으면 파일을 수정하지 마세요. 간단한 수정은 즉시 패치해도 됩니다.
- `AGENTS.md`를 직접 수정하지 마세요. 단, `Docs` 세션의 문서 목록은 수정하셔도 됩니다.

### Subagent Usage
- 서브에이전트는 별도 승인 없이 자유롭게 사용해도 됩니다.
- 서브에이전트 모델은 `gpt-5.4 xhigh`를 사용하세요.
- 서브에이전트를 사용해 병렬로 코드를 수정할 때, 담당 범위를 나눠서 수정 영역이 겹치지 않게 하세요.
- 서브에이전트는 문서 수정/삭제를 허용하지 않습니다.

### Code Write Policy
- 모듈화합니다. 하나의 파일이 1000 line을 초과하면 분할하세요.
- 타임아웃 기반 추정보다 상태 기반 판단을 우선합니다.
- 우회 동작보다 strict path를 우선합니다.
- 문제 경로를 막고 넘어가기보다 근본 원인을 찾으세요.
- 분기는 결정적이고 상태 기반이어야 합니다. 취약한 휴리스틱으로 분기하지 마세요.
- 코드 수정과 검증 이후에는 strict path만 남기고 나머지는 제거하는 것을 선호합니다.
- backward compatiability보다 깔끔하고 디버깅하기 좋은 코드를 우선하세요.

## Docs
- 프로젝트 전반에 적용되는 중요한 규칙/방법론/접근법/리팩토링을 적용할 경우 `docs/` 디렉토리에 간단히 문서화하고, 그 문서에 대한 설명을 아래 목록에 작성하세요:
  - [docs/http-contract.md](docs/http-contract.md): 현재 구현 기준 단일 HTTP 계약 문서입니다. `UI engine`, `service engine`, `model engine` 간 wire contract를 함께 정의합니다.
  - [docs/service-engine-boundary.md](docs/service-engine-boundary.md): `service_engine`의 책임 경계, 비목표, 고정된 v1 설계 선택을 정리합니다.
  - [docs/project-page-storage-boundary.md](docs/project-page-storage-boundary.md): cloud `project/page` 저장의 authority, page summary와 page snapshot 구분, multipart snapshot 규칙을 정리합니다.
  - [docs/ui-model-abstract-boundary.md](docs/ui-model-abstract-boundary.md): `UI engine`과 `model engine` 사이에서 이번 단계에 고정하는 추상 경계와 의도적으로 미루는 세부 wire shape를 정리합니다.
  - [docs/boundary-open-questions.md](docs/boundary-open-questions.md): v1 boundary를 구현하기 전에 정해야 하는 미결 질문과 합의 필요 항목을 추적합니다.

### 계획 적용 시 문서 작성 요령
- 계획을 적용하는 턴을 시작할 때는 전체 계획을 **그대로** `임시 계획 문서`로 기록합니다.
- 컨텍스트 압축 직후, `임시 계획 문서`를 반드시 한 번 읽으세요(존재한다면).
- 계획 적용 완료 시 `임시 계획 문서`는 삭제합니다.
- 간단한 수정은 위 절차를 따르지 않고 즉시 패치해도 괜찮습니다.

### 오류 발생 시 문서 작성 요령
- 검증 중 오류나 예외가 발생했을 때 다음과 같은 절차를 따릅니다:
  1. 현재 진행 중인 task overall을 문서화하여 `임시 계획 문서`를 작성합니다. `임시 계획 문서`가 존재한다면 생략합니다.
  2. 오류의 원인을 파악합니다. 원인 파악에 필요하다면 코드를 수정해도 됩니다.
  3. 해당 오류에 대해 `임시 오류 문서`를 작성합니다.
  4. 워크플로우의 전체적인 철학과 AGENTS.md의 방향성을 파악하고, 이를 `임시 오류 문서`에 업데이트합니다.
  5. 오류 수정 계획을 세우고, 이를 `임시 오류 문서`에 업데이트합니다.
  6. 코드를 수정하고 검증합니다. 문제가 고쳐졌다면 `임시 오류 문서`는 삭제하고 `임시 계획 문서`에 따라 계속합니다. 새로운 오류나 예외가 발생할 경우 `임시 오류 문서`를 업데이트하고, 같은 절차를 통해 문제를 해결합니다.
- 간단한 수정은 위 절차를 따르지 않고 즉시 패치해도 괜찮습니다.
- 컨텍스트 압축 직후, `임시 오류 문서`를 반드시 한 번 읽으세요(존재한다면).

## Workspace
- 이 프로젝트는 만화 번역을 위한 통합 워크스테이션 with AI 개발 프로젝트입니다.
- UI engine, model engine, service engine으로 나눕니다.
- `service_engine` 브랜치에서는 각 엔진의 통신 레이어와 service engine을 담당합니다. UI engine과 model engine의 세부 구현은 건드리지 않습니다.
- `ui_engine` 브랜치에서는 UI engine의 세부 구현을 담당합니다.
- `model_engine` 브랜치에서는 model engine의 세부 구현을 담당합니다.
- 빌드와 테스트 모두 Docker를 사용합니다.

