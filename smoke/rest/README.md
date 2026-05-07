# REST Smoke

End-to-end REST smoke test for the Dockerized TOWA stack.

Run the stack and smoke runner:

```bash
VITE_UI_AUTH_BACKEND=real VITE_UI_AI_BACKEND=real docker compose up -d --build db service-engine model-engine ui-engine
docker compose --profile smoke run --rm --no-deps --build rest-smoke
```

The smoke runner executes inside Docker with host networking and calls the three engines
through their published localhost ports. It sends `Origin: http://localhost:5173` to validate
the UI-facing CORS path.
