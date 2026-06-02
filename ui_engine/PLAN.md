# PLAN — UI Engine 후속 작업 메모

PoC/데모 직접 영향이 적어 보류된 항목들. 본 데모 안정화 후 결정·이슈 발행.

---

## P1. 동시 세션 정책 (Lock vs 양방향 sync)

### 배경
ui_engine은 SPA라 디바이스·세션 간 통신 채널 없음. 한 프로젝트를 두 세션이 동시 편집하면 last-write-wins로 작업 손실 가능. 동시 편집 정책이 필요한 시점이 옴.

### 옵션 정리

| 방식 | 충돌 처리 | 구현 비용 | 협업 적합성 |
|---|---|---|---|
| **OT/CRDT 실시간 협업** | 자동 병합 | 매우 큼 (Figma 수준) | 매우 좋음 |
| **양방향 sync + LWW** | 마지막 저장이 이김 | 중간 (WebSocket 필요) | 보통 |
| **Lock + 단방향 sync** | 동시 점유 차단 | 작음 | 협업 X |
| **Lock + WebSocket 알림** | 동시 점유 차단 + 변경 broadcast | 중간 | 협업 X (read 푸시만) |

### 잠정 결론
- 만화 번역 도메인은 동시 협업 수요 낮음 → **Lock**이 자연스러움.
- "다른 디바이스 변경 즉시 반영" UX는 WebSocket 알림으로 lock과 병행 가능.
- 1차에는 lock도 sync도 미구현. **LWW 그대로 받아들임** (PoC 한정).

### 미루는 이유
구현량 큼. PoC/데모에선 1인 1세션이 거의 보장됨. 실사용 단계 진입 시 결정.

### Lock API 명세 (구현 보류, 메모용)

**테이블: `project_locks`**
| 컬럼 | 비고 |
|---|---|
| `project_id` | PK, FK |
| `lock_token` | 서버 발급, 매 acquire 새로 |
| `user_id` | 점유자 |
| `device_label` | UA 또는 사용자 입력 (다이얼로그 표시용) |
| `acquired_at` / `expires_at` | TTL 기반 만료 |

**API:**
```
POST   /api/v1/projects/{id}/lock                # acquire
POST   /api/v1/projects/{id}/lock?force=true     # force takeover
POST   /api/v1/projects/{id}/lock/heartbeat      # TTL 갱신
DELETE /api/v1/projects/{id}/lock                # release
GET    /api/v1/projects/{id}/lock                # 점유 상태 조회 (옵션)
```

**정책:**
- TTL 5분, heartbeat 권장 90초.
- 충돌 시 409 + `current_holder` (user_id, device_label, expires_at).
- mutation API에 `X-Lock-Token` 헤더 동봉, 서버가 검증 (만료/탈취 시 419).
- 본인의 다른 세션 force takeover 가능.

**비범위:**
- WebSocket 푸시 알림 (별도 항목)
- 협업/read-only 동시 접속

---

## P2. Sync 아키텍처 (FileManager 추상화 + IndexedDB 캐싱) — **#39로 1차 구현 완료**

### 배경
원래는 CloudFileAdapter가 매 호출마다 backend 직행, IndexedDB 캐싱 없음. 사용자 멘탈 모델("local 진실 + cloud sync")과 어긋나고 Electron 래핑까지 고려하면 추상화 필요.

### 현재 구조 (#39 적용 후)

```
[UI / Components]
     ↕
[TanStack Query]            ← 서버 상태 + IDB 영속화 (모드 무관)
     ↕  per-user namespace (towa-query-${userId}, towa-cache-${userId})
[useFileAdapter / use*]     ← composable layer (usePages, useProjects, usePageLoader, useAutoSave, ...)
     ↕
[FileAdapter 인터페이스]
     ├── CloudFileAdapter   (service_engine HTTP, multipart PUT)
     └── (예정) LocalFileAdapter   (Electron 도입 시 native FS)
```

- TanStack Query가 서버 상태 캐시 + IDB persister로 영속화. invalidate/refetch 흐름 일관.
- `pageBinaryCache` / `thumbnailCache`는 binary blob 전용 IDB store (memory 2-tier).
- 401 시 global handler가 `/login?expired=1`로 라우팅 (auth flow와 연동).
- DEPLOYMENT_MODE는 FileAdapter 구현체 선택만 (현재 cloud, Electron 도입 시 local 추가).

### Sync 정책 (#39에서 확정된 부분)

- **단위**: 프로젝트 메타는 일괄 pull (useProjects), 페이지 binary는 lazy fetch + 주변 페이지 prefetch (usePageBinaryPrefetch).
- **Push 시점**:
  - 페이지 binary/layer state: dirty → 30s debounce 자동저장 + 페이지 전환 즉시 + Ctrl+S 수동.
  - AI 결과: active 페이지면 markDirty → saveImmediately, background면 fileAdapter.savePageSnapshot 직접 호출.
  - 메타데이터: mutation 후 invalidateQueries로 refetch.
- **첫 진입 UX**: TanStack Query persistQueryClient가 IDB에서 캐시 hydration → 즉시 표시 + 백그라운드 refetch.
- **메타데이터(프로젝트 목록·폴더 트리)**: useQuery로 캐싱. 본인 mutation 후 setQueryData 직접 주입(404 race 회피) 또는 invalidate.

### 미정 (보류)

- **오프라인**: 현재 push 실패 시 1s/2s/4s exponential backoff 3회 retry. 본격 오프라인 모드(큐잉)는 미구현.
- **LocalFileManager**: Electron 도입 시 추가. 인터페이스는 이미 분리됨.
- **메타데이터 백그라운드 diff**: 현재는 staleness 기반 refetch. 본인 외 변경 즉시 반영은 P3 WebSocket과 묶임.

---

## P3. WebSocket/SSE 변경 알림

P1의 lock 옵션 중 "다른 디바이스 변경 즉시 반영"과, P2 sync 정책의 push 변형. service_engine에 WebSocket 서버 추가 필요. 우선순위 낮음.

---

## 의사결정 메모

- 2026-05-27: 위 P1·P2·P3 모두 PoC 이후로 보류. 우선 #21(폴더 시스템 UI)을 cloud-only + 매 fetch 구조 위에 그대로 구현. Sync·Lock은 데모 후 결정.
- 2026-06-02: P2 Sync 아키텍처를 #39 FileAdapter sync 레이어 재구성으로 1차 구현. TanStack Query + IDB persister + per-user namespace + 자동저장(30s debounce + 즉시 save + Ctrl+S). LocalFileManager·오프라인 큐·메타 백그라운드 diff는 보류 유지. P1/P3는 변경 없음.
