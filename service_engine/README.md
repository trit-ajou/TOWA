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
- `POST /api/v1/projects`
- `GET /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `PATCH /api/v1/projects/{project_id}`
- `DELETE /api/v1/projects/{project_id}`
- `GET /api/v1/projects/{project_id}/pages`
- `POST /api/v1/projects/{project_id}/pages`
- `GET /api/v1/pages/{page_id}/snapshot`
- `PUT /api/v1/pages/{page_id}/snapshot`
- `DELETE /api/v1/pages/{page_id}`
- `GET /api/v1/pages/{page_id}/thumbnail`

합의된 v1 target boundary:

- cloud `project` metadata persistence
- cloud `page summary` 조회
- cloud `page snapshot` save/load/delete

## Python Environment

의존성은 로컬 Python이 아니라 `service_engine/.venv`에만 설치해서 사용합니다.

### 1. 표준 venv 생성

```bash
cd service_engine
python3 -m venv .venv
```

### 2. venv 활성화

```bash
source .venv/bin/activate
```

### 3. 의존성 설치

```bash
python3 -m pip install -r requirements-dev.txt
```

### 4. 테스트 실행

```bash
python3 -m pytest
```

### 5. 서버 실행

```bash
python3 -m uvicorn app.main:app --reload
```

### 6. 마이그레이션 적용

```bash
.venv/bin/python -m app.cli.dev_admin migrate
```

## If `python3 -m venv` Fails

일부 환경에서는 `ensurepip`가 빠져 있어서 기본 `venv` 생성이 실패할 수 있습니다.
그 경우 아래 순서로 `pip` 없는 venv를 만든 뒤, `get-pip.py`로 venv 안에만 `pip`를 넣습니다.

```bash
cd service_engine
python3 -m venv --without-pip .venv
curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
.venv/bin/python /tmp/get-pip.py
.venv/bin/python -m pip install -r requirements-dev.txt
```

이후 명령은 아래처럼 `.venv` 기준으로 실행하면 됩니다.

```bash
.venv/bin/pytest
.venv/bin/uvicorn app.main:app --reload
```

## Dev CLI

다른 engine과 merge 전에 `service_engine` 단독으로 상태를 준비할 수 있도록 dev CLI를 제공한다.

### Seed User

```bash
.venv/bin/python -m app.cli.dev_admin seed-user \
  --email user@example.com \
  --nickname tester \
  --initial-balance 1000
```

### Grant Credits

```bash
.venv/bin/python -m app.cli.dev_admin grant-credits \
  --email user@example.com \
  --units 500
```

### Reset Credits

```bash
.venv/bin/python -m app.cli.dev_admin reset-credits \
  --email user@example.com \
  --balance 1000
```

`reset-credits`는 held credit이 남아 있으면 거부한다.

## Notes

- `.venv/`는 Git에 포함하지 않습니다.
- 시스템 Python이나 `~/.local` user site에 패키지를 설치하지 않는 것을 기준으로 합니다.
- PostgreSQL migration 테스트는 `TEST_DATABASE_URL`이 있어야 실행됩니다.
