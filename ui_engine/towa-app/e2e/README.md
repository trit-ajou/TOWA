# Playwright e2e — file-adapter sync (#39)

Covers the six categories from the issue's meta-instructions:

1. `01-entry-flow.spec.ts` — library → project → editor.
2. `02-page-cache.spec.ts` — page cache + prefetch DB materializes after entering the editor.
3. `03-save.spec.ts` — Ctrl+S wiring + dirty title behavior.
4. `04-cache-persistence.spec.ts` — TanStack Query IDB persister survives reload.
5. `05-auth-401.spec.ts` — expired session → /login?expired=1 + notice.
6. `06-user-isolation.spec.ts` — different users get distinct IDB namespaces.

## Prerequisites

These tests run against the cloud-mode app, so the **service_engine + db** stack
must be up first:

```sh
# from the monorepo root (TOWA/)
docker compose up -d db service-engine
```

The Vite dev server is started automatically by `playwright.config.ts`. Set
`E2E_NO_DEV_SERVER=1` if you already have one running.

## Running

```sh
cd ui_engine/towa-app
npx playwright install chromium    # one-time
npm run e2e
```

`npm run e2e:ui` opens the Playwright UI for inspection.

## Notes

- The dev-login flow in `helpers/auth.ts` posts to `POST /api/v1/auth/dev-login`.
  The service-engine dev mode auto-provisions accounts on demand.
- IDB inspection in tests uses `indexedDB.databases()` (Chromium supports this).
- Specs deliberately stop at structural checks — full canvas-render assertions
  require golden image fixtures that aren't part of #39's scope.
