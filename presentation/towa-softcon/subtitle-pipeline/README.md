# 발표영상 자막 파이프라인

하나의 발표 녹화 파일과 하나의 전체 대본 파일을 받아 자막이 입혀진 발표 영상을 만듭니다.

처리 순서:

1. `ffmpeg`로 발표영상에서 음성만 `audio.wav`로 추출
2. `faster-whisper`로 음성을 STT 처리하고 word timestamp 생성
3. STT word stream과 준비된 대본을 순서대로 정렬
4. `subtitles.srt`, `subtitles.ass`, `alignment.json` 생성
5. 옵션으로 원본 영상에 ASS 자막을 burn-in하여 `subtitled.mp4` 생성

## 대본 파일

대본은 실제로 말한 문장만 들어 있는 UTF-8 plain text 파일로 준비합니다.

```text
안녕하세요. 만화 번역을 위한 AI 통합 워크스테이션, TOWA를 소개하겠습니다.
만화 번역 식자 작업은 단순히 문장을 번역하는 작업에서 끝나지 않습니다.
원문 텍스트를 지우고, 지워진 배경을 자연스럽게 복원하고, 번역문을 말풍선 모양에 맞게 다시 배치해야 합니다.
```

빈 줄은 무시됩니다. 긴 줄은 `--max-caption-chars` 기준으로 자동 분할됩니다.

## 실행

저장소 루트에서 실행합니다.

```bash
docker compose -f presentation/towa-softcon/docker-compose.subtitles.yml build
docker compose -f presentation/towa-softcon/docker-compose.subtitles.yml run --rm subtitle-pipeline run \
  --video path/to/presentation-recording.mp4 \
  --script path/to/spoken-script.txt \
  --out-dir output/presentation-subtitles/towa-demo \
  --model small \
  --device cpu \
  --compute-type int8 \
  --burn-in
```

첫 실행에서는 Whisper 모델을 내려받기 때문에 시간이 걸릴 수 있습니다. 모델 캐시는 Docker volume에 유지됩니다.

## 산출물

`--out-dir` 아래에 다음 파일이 생성됩니다.

- `audio.wav`: 영상에서 추출한 16 kHz mono 음성
- `stt.json`: faster-whisper STT 결과
- `alignment.json`: 대본 자막별 STT 매칭 결과와 유사도
- `subtitles.srt`: 일반 자막 파일
- `subtitles.ass`: burn-in용 스타일 자막 파일
- `subtitled.mp4`: `--burn-in`을 준 경우 생성되는 자막 입힌 영상

이미 만들어진 `alignment.json`에서 자막 파일만 다시 만들 때는 다음 명령을 사용합니다.

```bash
docker compose -f presentation/towa-softcon/docker-compose.subtitles.yml run --rm subtitle-pipeline write-subtitles \
  --alignment output/presentation-subtitles/towa-demo/alignment.json \
  --srt output/presentation-subtitles/towa-demo/subtitles.srt \
  --ass output/presentation-subtitles/towa-demo/subtitles.ass
```

## 싱크 조정

- `--max-caption-chars`: 한 자막 줄의 최대 길이입니다. 기본값은 `34`입니다.
- `--min-similarity`: 대본과 STT 매칭 최소 유사도입니다. 기본값은 `0.42`입니다.
- `--max-skip-units`: 대본에 없는 짧은 삽입어를 넘길 수 있는 STT word 수입니다. 기본값은 `8`입니다.
- `--subtitle-offset-sec`: 전체 자막을 앞뒤로 미는 보정값입니다.
- `--caption-tail-sec`: 매칭된 음성 끝 뒤로 자막을 유지하는 시간입니다.

`alignment.json`에서 `similarity`가 낮은 자막이 있으면, 대본 문장과 실제 녹음 문장이 크게 다른 구간입니다. 이 경우 대본 파일을 실제 말한 문장에 맞게 다듬은 뒤 다시 실행하는 것이 가장 안정적입니다.
