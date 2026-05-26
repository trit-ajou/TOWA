# Service Engine

FastAPI 기반 `service_engine` 초안입니다.

문서:

- 현재 wire contract: [../docs/http-contract.md](../docs/http-contract.md)
- 현재 경계/비목표: [../docs/service-engine-boundary.md](../docs/service-engine-boundary.md)
- project/page storage boundary: [../docs/project-page-storage-boundary.md](../docs/project-page-storage-boundary.md)
- UI/model 추상 경계: [../docs/ui-model-abstract-boundary.md](../docs/ui-model-abstract-boundary.md)

현재 구현 범위:

- `POST /auth/dev/login`
- `GET /auth/me`
- `POST /usage/jobs`
- `POST /usage/jobs/{job_id}/capture`
- `POST /usage/jobs/{job_id}/release`
- `GET /usage/jobs/{job_id}`
- `GET /api/v1/folders`
- `POST /api/v1/folders`
- `PATCH /api/v1/folders/{folder_id}`
- `DELETE /api/v1/folders/{folder_id}`
- `POST /api/v1/folders/{folder_id}/restore`
- `GET /api/v1/trash`
- `POST /api/v1/projects`
- `GET /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `PATCH /api/v1/projects/{project_id}`
- `DELETE /api/v1/projects/{project_id}`
- `POST /api/v1/projects/{project_id}/restore`
- `GET /api/v1/projects/{project_id}/pages`
- `POST /api/v1/projects/{project_id}/pages`
- `GET /api/v1/pages/{page_id}/snapshot`
- `PUT /api/v1/pages/{page_id}/snapshot`
- `DELETE /api/v1/pages/{page_id}`
- `GET /api/v1/pages/{page_id}/thumbnail`

합의된 v1 target boundary:

- cloud `folder/project` metadata persistence
- cloud `page summary` 조회
- cloud `page snapshot` save/load/delete

## Python Environment

공식 개발 경로는 로컬 `venv`가 아니라 Docker입니다.

루트 `docker-compose.yml`은 전체 엔진 통합 실행용이고, `service_engine/docker-compose.dev.yml`은 `service_engine` 단독 개발용입니다.

### 1. 개발 서버 시작

```bash
cd service_engine
docker compose -f docker-compose.dev.yml up --build service-engine-dev
```

서버는 `http://localhost:8000`에서 열리고, 코드 변경은 bind mount + `uvicorn --reload`로 즉시 반영됩니다.

### 2. 테스트 실행

```bash
cd service_engine
docker compose -f docker-compose.dev.yml run --rm service-engine-test
```

이 경로는 테스트 전용 PostgreSQL을 함께 사용하므로 `@pytest.mark.postgres` 테스트도 skip되지 않습니다.

### 3. 로그 확인

```bash
cd service_engine
docker compose -f docker-compose.dev.yml logs -f service-engine-dev
```

### 4. 종료 및 정리

```bash
cd service_engine
docker compose -f docker-compose.dev.yml down -v
```

## Dev CLI

다른 engine과 merge 전에 `service_engine` 단독으로 상태를 준비할 수 있도록 dev CLI를 제공한다.

### Seed User

```bash
cd service_engine
docker compose -f docker-compose.dev.yml run --rm service-engine-dev \
  python3 -m app.cli.dev_admin seed-user \
  --email user@example.com \
  --nickname tester \
  --initial-balance 1000
```

### Grant Credits

```bash
cd service_engine
docker compose -f docker-compose.dev.yml run --rm service-engine-dev \
  python3 -m app.cli.dev_admin grant-credits \
  --email user@example.com \
  --units 500
```

### Reset Credits

```bash
cd service_engine
docker compose -f docker-compose.dev.yml run --rm service-engine-dev \
  python3 -m app.cli.dev_admin reset-credits \
  --email user@example.com \
  --balance 1000
```

`reset-credits`는 held credit이 남아 있으면 거부한다.

## Notes

- 로컬 `venv`는 공식 개발 경로가 아니며 필요하지 않습니다.
- 루트 `docker compose up --build`는 전체 엔진 통합 실행용입니다.
- `service-engine-test` compose 서비스가 `TEST_DATABASE_URL`을 자동으로 설정합니다.
