# Git 워크플로우 규칙

## 브랜치 구조

```
main (중앙 허브)
├── ui_engine
├── feat/model_engine
└── feat/service_engine
```

- **main**: 항상 안정된 상태 유지. 각 엔진 브랜치의 merge 대상.
- **엔진 브랜치**: 각자의 엔진 디렉토리에서만 작업. 브랜치는 유지하면서 중간중간 main에 merge.

## 핵심 규칙

### 1. 브랜치 간 직접 merge 금지

```
❌ feat/service_engine ← feat/model_engine  (직접 merge)
✅ feat/model_engine → main → feat/service_engine이 main에서 pull
```

다른 엔진의 코드가 필요하면:
1. 해당 엔진이 먼저 main에 merge
2. 내 브랜치에서 `git pull origin main` 또는 `git merge main`으로 받아오기

### 2. `--no-ff` merge 사용

```bash
git merge --no-ff my_branch -m "Merge my_branch: 요약"
```

- fast-forward merge 금지. 항상 merge commit을 남길 것.
- 그래프에서 브랜치 분기/합류가 명확하게 보여야 함.

### 3. 커밋 메시지 형식

**일반 커밋:**
```
영어 제목 (현재형 동사로 시작, 간결하게)

- 변경사항 1
- 변경사항 2
- 변경사항 3
```

**Merge 커밋:**
```
Merge 브랜치명: 요약 (한 줄)

- 변경사항 1
- 변경사항 2
- 변경사항 3
```

예시:
```
Merge ui_engine: Add towa-app UI wireframe prototype

- Vue 3 + TypeScript + Vite + Tailwind CSS v4 scaffold
- Library / Project home / Editor / Detail editor views
- Dark/light theme, deployment mode system
```

**공통:**
- 제목은 영어, 현재형 동사 (Add, Fix, Refactor, Update 등)
- 본문은 변경사항을 list로 간결하게
- AI 관련 문구(Co-authored-by 등) 절대 포함 금지

### 4. 작업 디렉토리 범위

| 브랜치 | 작업 범위 | 금지 영역 |
|--------|----------|----------|
| ui_engine | `ui_engine/` | `model_engine/`, `service_engine/` |
| feat/model_engine | `model_engine/` | `ui_engine/`, `service_engine/` |
| feat/service_engine | `service_engine/` | `ui_engine/`, `model_engine/` |

- 공통 파일(README.md, 루트 설정 등) 수정 시 커밋 메시지에 명시
- 다른 엔진 디렉토리 수정 절대 금지

### 5. Main에 merge하는 흐름

```bash
# 1. 내 브랜치에서 최신 main 받기
git checkout my_branch
git pull origin main

# 2. conflict 있으면 해결 후 커밋

# 3. merge 전 diff 확인 (필수)
git diff main..my_branch --stat

# 4. main에서 merge
git checkout main
git pull origin main
git merge --no-ff my_branch -m "Merge my_branch: 요약

- 변경사항 1
- 변경사항 2"

# 5. push
git push origin main

# 6. 내 브랜치로 복귀
git checkout my_branch
```

### 6. 수시로 main pull

- 다른 팀원의 변경사항을 수시로 받아와서 conflict 최소화
- merge 직전이 아니라 작업 중간중간에 `git pull origin main`

## 금지 사항

- `git push --force` (main에 대해 절대 금지)
- 브랜치 간 직접 merge
- 다른 엔진 디렉토리 수정
- fast-forward merge (`--no-ff` 필수)
- merge 전 diff 확인 생략
