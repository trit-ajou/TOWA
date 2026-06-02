# UI Backend SDK

`src/backend` is the internal boundary between UI-facing code and engine-facing code.

Current responsibilities:

- define stable TS contracts for auth and AI job calls
- provide `real` adapters for `service_engine` and `model_engine`
- provide `emulated` adapters for isolated UI development
- expose `createAppBackend(...)` so UI code can depend on one interface

Recommended usage:

```ts
import { createAppBackend } from '@/backend'

const backend = createAppBackend()

const login = await backend.auth.devLogin({ email: 'user@example.com' })
const job = await backend.aiJobs.createJob(payload, { sessionKey: login.sessionKey })
```

Environment flags:

- `VITE_UI_BACKEND_MODE=real|emulated` — **master switch**. 기본 `real`. unset/공백이면 `real`.
- `VITE_UI_AUTH_BACKEND` / `VITE_UI_AI_BACKEND` / `VITE_UI_FILES_BACKEND` — per-domain override. **master가 `emulated`일 때만** 효과 있음.

Semantics (AND-gate):

| master | per-domain | result |
|---|---|---|
| real | (any) | **real** — `emulated` per-domain은 startup throw |
| emulated | (unset) | emulated |
| emulated | real | real (해당 도메인만 실제 엔진) |
| emulated | emulated | emulated |

`real`이면 어디서든 mock으로 빠질 수 없게 강제. `emulated`이면 master가 "어딘가 mock이 끼어 있다"는 표식이 되고, 개발 중에 일부 도메인만 골라서 실제 엔진과 붙여볼 수 있다.

일괄 토글: `./scripts/set-backend-mode.sh real|emulated` (repo root).

Notes:

- `real` auth는 `service_engine`, `real` aiJobs는 `model_engine`을 직접 호출한다.
- `emulated`도 `saas` job create/get에서 session-bound ownership과 idempotency mismatch를 재현한다.
- 잘못된 값(`real`/`emulated` 외)이 들어오면 startup에서 throw — typo로 silent fallback되는 일 없음.

Live smoke reference:

- 날짜: `2026-03-29`
- 검증 경로: `auth.devLogin -> auth.getCurrentUser -> aiJobs.createJob -> aiJobs.getJob`
- `real/real` 조합으로 실제 `service_engine`과 `model_engine`에 연결해 확인했다.
- cloud/`saas`의 `detect` 작업은 최종적으로 `succeeded`까지 갔고, service credit은 `1000 -> 995`로 줄었다.

Compatibility note:

- 현재 `service_engine` usage enum은 `mask|translate|inpaint`만 받는다.
- 그래서 `model_engine`은 billing 시 `detect`를 임시로 `mask`로 매핑한다.
- UI SDK는 여전히 외부 계약상 `operationKind: 'detect'`를 그대로 사용하면 된다.

API change note:

- `saas`의 `aiJobs.getJob(...)`는 create와 같은 session key로만 polling 가능하다.
- 같은 session scope에서 같은 `idempotencyKey`를 다른 payload로 재사용하면 `model_job_conflict`를 반환한다.
- `real` adapter는 network failure와 malformed JSON도 `BackendError`로 정규화한다.
