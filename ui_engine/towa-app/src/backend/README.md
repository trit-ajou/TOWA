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

- `VITE_UI_AUTH_BACKEND=real|emulated`
- `VITE_UI_AI_BACKEND=real|emulated`

Notes:

- auth와 aiJobs는 독립적으로 `real` 또는 `emulated`를 고를 수 있다.
- 기본값은 둘 다 `emulated`다.
- `real` auth는 `service_engine`, `real` aiJobs는 `model_engine`을 직접 호출한다.

Live smoke reference:

- 날짜: `2026-03-29`
- 검증 경로: `auth.devLogin -> auth.getCurrentUser -> aiJobs.createJob -> aiJobs.getJob`
- `real/real` 조합으로 실제 `service_engine`과 `model_engine`에 연결해 확인했다.
- cloud/`saas`의 `detect` 작업은 최종적으로 `succeeded`까지 갔고, service credit은 `1000 -> 995`로 줄었다.

Compatibility note:

- 현재 `service_engine` usage enum은 `mask|translate|inpaint`만 받는다.
- 그래서 `model_engine`은 billing 시 `detect`를 임시로 `mask`로 매핑한다.
- UI SDK는 여전히 외부 계약상 `operationKind: 'detect'`를 그대로 사용하면 된다.
