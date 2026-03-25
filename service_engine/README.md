# Service Engine

FastAPI 기반 `service_engine` 초안입니다.

현재 범위:

- `POST /auth/dev/login`
- `GET /auth/me`
- `POST /usage/jobs`
- `POST /usage/jobs/{job_id}/capture`
- `POST /usage/jobs/{job_id}/release`
- `GET /usage/jobs/{job_id}`

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
python -m pip install -r requirements-dev.txt
```

### 4. 테스트 실행

```bash
pytest
```

### 5. 서버 실행

```bash
uvicorn app.main:app --reload
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

## Notes

- `.venv/`는 Git에 포함하지 않습니다.
- 시스템 Python이나 `~/.local` user site에 패키지를 설치하지 않는 것을 기준으로 합니다.
- PostgreSQL migration 테스트는 `TEST_DATABASE_URL`이 있어야 실행됩니다.

