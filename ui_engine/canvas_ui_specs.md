# 캔버스 도구 UX 작업 체크리스트

상세 편집 / 편집 캔버스의 도구별 스펙과 진행 상황. 항목 끝낼 때마다 [x] 표시.

---

## 0. UI 골격 (issue #22 진행분)

- [x] bitmappery `toolbox` / `tool-options-panel` / `layer-panel` / `header-menu` / 파일명 헤더 비활성화 (feature flag)
- [x] **CanvasToolbox** — 좌측 floating, w-10, drag 핸들로 위치 이동, 기본 좌측 하단
- [x] AI 단일 버튼 + 드롭다운 (텍스트 검출 / 인페인팅 / 번역)
- [x] FG/BG 색 swatch — 포토샵 스타일 50% 겹침 + swap 아이콘
- [x] **ToolOptionsPanel** — 우상단 (도구별 옵션, stub — 브러쉬 계열 size/opacity만)
- [x] **LayerPanel** — 우하단, 프리셋 그룹 + 접기/펼치기, 텍스트 레이어는 내용 표시
- [x] **RightPanelSplit** — 두 우측 패널 사이 resize 핸들, localStorage 영속화, 개별 스크롤
- [x] **PageSidePanel** 접기 버튼 우하단 floating
- [x] bitmappery `document-canvas` wrapper 높이 보정 (window 기준 → 부모 100%)
- [x] 캔버스 워크스페이스 컨테이너로 묶기 (AI 도구를 좌측 toolbox로 흡수, 상단 통합 바 폐기)
- [x] mock seed 레이어 12개 + original 1개로 확장

---

## 1. 캔버스 도구별 UX

### Zoom 도구 [Z]
> bitmappery 기본 줌은 부족. 포토샵식 클릭/드래그 줌 신규 구현.
> 구현: `ZoomToolHandler.vue` overlay (zoom 도구 active일 때만 캔버스 위 layer)
- [x] 좌클릭: 고정치 줌인 (level +5, ≈ ×1.25)
- [x] 우클릭: 고정치 줌아웃 (level −5, ≈ ×0.8) + contextmenu preventDefault
- [x] 드래그: 시작점에서 멀어지는 방향이면 줌인, 가까워지면 줌아웃 (DRAG_GAIN=0.15)
- [x] Wheel 줌: zoom 도구 active일 때 일반 휠 = 줌, deltaY < 0 → 줌인
- [x] 핀치 줌: 터치패드 핀치 (wheel + ctrlKey) 또는 ctrl/cmd + wheel — 도구 무관, 캔버스 영역에서 가로채 줌 적용 (브라우저 페이지 줌 방지)

### 화면 이동 [Hand / Space modifier]
> bitmappery `MOVE` 도구로 존재. Space modifier 동작 점검 필요.
- [ ] Hand 도구 선택 시 드래그로 viewport pan
- [ ] 어느 도구든 Space + 드래그로 임시 pan (modifier)

### 객체(레이어) 이동 [V] / DRAG
- [ ] 선택된 레이어를 드래그로 이동 (bitmappery 기본 동작 점검)

### 브러쉬 [B]
- [ ] 드로잉 (bitmappery 기본)
- [ ] 우클릭 시 브러쉬 크기·종류 팝업 (아래 "브러쉬 크기 조정" 참조)

### 도장 [S]
- [ ] 드로잉
- [ ] alt+클릭으로 소스 지점 지정 + 시각 표시
- [ ] sourceLayer 선택 UI (도구 옵션 패널)
- [ ] 우클릭 팝업

### 지우개 [E]
- [ ] 드로잉
- [ ] 우클릭 팝업

### 브러쉬 크기 조정 [우클릭 팝업]
> 브러쉬/도장/지우개 도구일 때, 캔버스 위 우클릭 위치 근처에 팝업.
- [ ] 도구별 브러쉬 정보 상태 유지 (브러쉬/도장/지우개 각각 size·type·opacity·thickness 분리)
- [ ] 우측 ToolOptionsPanel과 양방향 동기화

### 텍스트 도구 [T]
- [ ] 빈 영역 클릭 시 신규 텍스트 레이어 생성
- [ ] 기존 텍스트 레이어 클릭 시 선택
- [ ] 도구 옵션 패널에 폰트 / 크기 / lineHeight / 색

### 전경/배경색 스왑 [X]
- [ ] bitmappery store에 배경색 필드 추가
- [ ] X 단축키 / swap 아이콘 클릭으로 swap
- [x] swatch UI (CanvasToolbox)

### 배경색으로 추출 [Alt/Option + 클릭]
- [ ] 어느 도구든 alt+클릭 시 스포이드 동작 → 배경색 슬롯에 추출

### 사각 선택 [M]
- [ ] bitmappery 기본 동작 점검
- [ ] 선택 영역에서 Delete로 지우기 / 채우기 등 후속 액션

### 마법사 선택 [W]
- [ ] bitmappery 기본 동작 그대로 (점검만)

### 페인트 통 [G]
- [ ] bitmappery 기본 동작 그대로 (점검만)

### 화면 로테이션 [R]
> 캔버스 viewport만 회전 (레이어 회전 아님). bitmappery에 없는 기능 → 신규.
- [ ] viewport rotation state
- [ ] 드래그로 회전 / 0도 리셋 등

### 레이어 편집 [Ctrl+T]
- [ ] 선택된 레이어에 free transform (포토샵 동등)
- [ ] bitmappery `scale` / `rotate` 도구 활용 가능성 확인

---

## 2. 도구 옵션 패널 (도구별 상세)

> bitmappery에는 도구별 옵션 컴포넌트가 있었음. 우리 ToolOptionsPanel은 현재 brush 계열 size/opacity만 stub. 도구별로 채우기.

- [x] brush — size, opacity (그 외: type, strokes, thickness 미노출)
- [x] eraser — size, opacity (그 외: type, thickness 미노출)
- [ ] clone — size, opacity, sourceLayer, coords
- [ ] text — font, size, lineHeight, spacing, color
- [ ] selection — anti-alias, feather
- [ ] fill — tolerance
- [ ] wand — threshold
- [ ] zoom — level 표시
- [ ] rotate — angle
- [ ] scale — factor
- [ ] mirror — axis
- [ ] drag — (옵션 거의 없음, 빈 상태 OK)

---

## 3. 상위 캔버스 동작 (향후)

- [ ] 캔버스 위 줌 인디케이터 (좌하단 100% 표시 + 클릭 시 fit/100% 토글)
- [ ] grid/snap 토글
- [ ] 단축키 통합 (bitmappery keyboard-service와 우리 단축키 충돌 점검)
