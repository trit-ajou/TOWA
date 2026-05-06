# 서버 배포 가이드

서버는 `main` 브랜치를 항상 따라가는 인스턴스입니다. main에 머지 + push되면 5분 안에 자동 반영됩니다.

## 구조

```
[로컬] main에 머지 → push
            ↓
[GitHub] origin/main 업데이트
            ↓ (cron 5분 폴링)
[서버] git pull main + docker compose up -d --build
            ↓
[Cloudflare Tunnel] towa.live, api.towa.live, model.towa.live
            ↓
[외부 사용자]
```

## 1회 세팅 (서버에서)

서버에 SSH로 접속해서:

```bash
git clone git@github.com:trit-ajou/TOWA.git ~/TOWA
~/TOWA/deploy.sh
```

`deploy.sh`가 알아서:
- `.env`가 없으면 `.env.deploy`(repo에 commit된 cloud-mode 프리셋)에서 복사
- `docker compose up -d --build`로 첫 빌드 + 기동

이후 자동 배포 cron 등록 — `crontab -e` 실행 후 한 줄 추가:

```
*/5 * * * * ~/TOWA/deploy.sh >> ~/TOWA/deploy.log 2>&1
```

`.env` 값을 다르게 쓰고 싶으면 `.env`를 직접 수정. `.env.deploy`는 이후 다시 안 건드림.

## Cloudflare Tunnel 설정 (호스트에 cloudflared 이미 설치됨 가정)

Cloudflare Zero Trust 대시보드 → Networks → Tunnels → 사용 중인 터널 선택 → **Public Hostname** 탭에서:

| Subdomain | Domain | Service Type | URL |
|-----------|--------|--------------|-----|
| (비워둠) | towa.live | HTTP | `localhost:5173` |
| api | towa.live | HTTP | `localhost:8000` |
| model | towa.live | HTTP | `localhost:8100` |

DNS 레코드는 cloudflared가 자동 생성합니다.

## 운영

### 자동 배포 동작
- 5분마다 `deploy.sh` 실행
- `origin/main`이 로컬 `main`과 다르면 → `git pull` + `docker compose up -d --build`
- 변경 없으면 즉시 종료 (no-op)
- 로그: `~/TOWA/deploy.log`

### 수동 배포
```bash
cd ~/TOWA && ./deploy.sh
```

### 컨테이너 상태 확인
```bash
docker compose ps
docker compose logs -f ui-engine
```

### 트러블슈팅

**Vite가 "Blocked request" 에러로 차단**
→ `.env`의 `VITE_PUBLIC_HOST`가 비었거나 잘못됨. 도메인 채우고 재빌드.

**브라우저에서 백엔드 호출 실패 (CORS / Network)**
→ Cloudflare 대시보드에서 `api.towa.live`, `model.towa.live` ingress가 등록됐는지 확인.
→ `.env`의 `*_CORS_ALLOW_ORIGINS`에 `https://towa.live` 포함됐는지 확인.

**main에 push했는데 반영 안 됨**
→ `tail -50 ~/TOWA/deploy.log` 확인.
→ cron 동작 확인: `crontab -l`.

## 작업 흐름 (개발자 입장)

1. feature 브랜치 또는 ui_engine 브랜치에서 로컬 개발 (`npm run dev` 또는 docker compose)
2. 검증 끝나면 main에 머지 + push
3. 5분 내 서버 자동 반영
4. `https://towa.live`에서 확인
