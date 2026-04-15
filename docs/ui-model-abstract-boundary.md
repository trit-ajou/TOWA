# UI / Model Abstract Boundary v1

이번 단계에서는 `UI engine <-> model engine` 상세 wire shape를 고정하지 않는다.
대신 두 엔진이 반드시 지켜야 할 추상 invariant만 고정한다.

## Fixed Invariants

- `UI engine`이 `model engine`에 직접 AI 작업을 요청한다
- 모든 AI 작업은 비동기 job 흐름을 사용한다
- cloud에서는 UI가 session/auth context를 model에 전달한다
- `model engine -> service engine` 직접 통신 범위는 auth/usage다
- UI는 현재 메모리의 page state를 기준으로 AI 입력을 구성한다
- AI 결과를 받은 뒤 project/page에 최종 반영하고 저장하는 주체는 UI다

## Intentionally Deferred

아래 항목은 이번 단계의 canonical cross-engine contract로 고정하지 않는다.

- UI -> model request body shape
- model -> UI result body shape
- binary handoff 방식
- artifact URL/token 규약
- detect/inpaint/translate별 세부 payload/result schema

## Why It Stays Abstract

- 이 브랜치의 직접 책임은 `service_engine`과 통신 레이어다
- UI와 model의 내부 표현은 각 브랜치 구현에 더 강하게 묶여 있다
- 지금은 storage/usage/auth boundary를 먼저 고정하는 것이 우선이다

## Current Repo Note

현재 저장소에는 `/v1/jobs` 기반 generic envelope 구현이 있다.
하지만 그 shape 자체를 이번 storage boundary 작업의 canonical cross-engine contract로 승격하지는 않는다.

즉:

- 현재 구현은 참고 구현이다
- 이번 문서에서 고정하는 것은 위 invariant뿐이다
