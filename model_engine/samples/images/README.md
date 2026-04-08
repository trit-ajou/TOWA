# Sample Images

이 폴더는 `model_engine` 샘플 실행용 입력 이미지를 둔다.

현재 사용처:

- CRAFT 기반 `text_detection` 샘플 실행

권장:

- 포맷: PNG/JPG/WEBP
- 파일명 예시: `page01.png`

로컬 실행:

```bash
python3 model_engine/scripts/run_craft_sample.py --image model_engine/samples/dlsite/sample.jpg
```

도커 추론 이미지 실행 예:

```bash
cd model_engine
docker build -f Dockerfile.inference -t towa-model-engine-inference .
docker run --rm -v "$(pwd)/samples:/app/model_engine/samples" towa-model-engine-inference \
  python3 /app/model_engine/scripts/run_craft_sample.py \
  --image /app/model_engine/samples/dlsite/sample.jpg
```
