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

## P2. Sync 아키텍처 (FileManager 추상화 + IndexedDB 캐싱)

### 배경
현재 CloudFileAdapter는 매 호출마다 backend 직행, IndexedDB 캐싱 안 함. 사용자 멘탈 모델("local 진실 + cloud sync")과 어긋남. Electron 래핑까지 고려하면 FileManager 추상화 필요.

### 목표 구조

```
[UI/Store]
     ↕
[IndexedDB]            ← 캐싱 레이어 (모드 무관)
     ↕
[Sync Layer]           ← IndexedDB ↔ FileManager
     ↕
[FileManager (인터페이스)]
     ├── CloudFileManager   (service_engine HTTP)
     └── LocalFileManager   (Electron 도입 시 native FS)
```

- IndexedDB는 캐시. 진실의 원천은 FileManager.
- 현재 `CloudFileAdapter` / `LocalFileAdapter` 양자택일 구조 폐기.
- DEPLOYMENT_MODE는 FileManager 구현체 선택만.

### Sync 정책 결정 묶음 (미정)

- **단위**: 프로젝트 메타는 일괄 pull, 페이지 binary는 lazy fetch 권장.
- **Push 시점**: 메타=즉시, 텍스트블록=debounce 500ms~1s, 페이지 binary=명시 save.
- **오프라인**: 1차에는 차단(재연결 표시).
- **첫 진입 UX**: 캐시 비어있으면 전량 fetch + 스플래시, 두 번째부터 캐시 즉시 표시 + 백그라운드 diff.
- **메타데이터(프로젝트 목록·폴더 트리)**: 앱 시작 시 1회 fetch + IndexedDB 캐싱. 본인 mutation 후 즉시 갱신.

### 미루는 이유
구현 큼. 현재 cloud-only + 매번 fetch로도 PoC 동작. 데모 후 성능·UX 이슈가 실체화되면 도입.

---

## P3. WebSocket/SSE 변경 알림

P1의 lock 옵션 중 "다른 디바이스 변경 즉시 반영"과, P2 sync 정책의 push 변형. service_engine에 WebSocket 서버 추가 필요. 우선순위 낮음.

---

## 의사결정 메모

- 2026-05-27: 위 P1·P2·P3 모두 PoC 이후로 보류. 우선 #21(폴더 시스템 UI)을 cloud-only + 매 fetch 구조 위에 그대로 구현. Sync·Lock은 데모 후 결정.
